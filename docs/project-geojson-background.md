# Background survey map generation

Survey source history is authoritative. GeoJSON is an optional derived artifact:
invalid coordinates, exporter failures, slow computation, broker outages, or
artifact-storage failures must not reject a source upload.

## Ordering and ownership

The upload endpoint first validates and saves the source files, successfully
commits **and pushes** them to the project's Git remote, and constructs its
`ProjectCommit` metadata. Only after that does it record a
`ProjectGeoJSONGeneration` for an eligible Ariane or Compass upload. The record
is in the request's SQL transaction; a separate dispatcher cannot see it before
that transaction commits. A failed push, request rollback, unchanged upload
(HTTP 304), excluded project, or unrelated file upload creates no new work.

The request never parses a survey for map generation, generates GeoJSON, uploads
a map, or publishes a Celery message. HTTP 200 means the source was saved. Its
existing response fields are preserved, with additive `geojson_status`:
`pending`, `skipped`, `not_requested`, or `unavailable` if optional bookkeeping
could not be recorded. Bookkeeping runs in a savepoint and its exception is
caught after that savepoint unwinds, so even an SQL error cannot poison the
source upload transaction. The project and pushed SHA are logged for recovery.
Core source-validation, Git, and source-metadata failures retain existing error
behavior.

Git and SQL are not a distributed transaction: a process exit after a successful
push but before SQL commit can still leave remote history ahead of metadata.
This change removes map processing from that vulnerable interval; it does not
claim to make Git and SQL commits atomic.

## Dispatch, execution, and publication

`install_background_schedules` idempotently installs a 60-second dispatcher. It
publishes only committed pending records to the existing `background_control`
queue. The existing worker consumes that queue; execution delay depends on
worker capacity, especially while long maintenance jobs run. Do not assume the
map is available when the upload response arrives.

A generation record belongs to one immutable source SHA. Dispatch and execution
use UUID ownership tokens and expiring leases. Duplicated or stale messages are
ignored. Broker publication failures retain durable pending work with bounded
exponential backoff; ambiguous delivery cannot supersede a worker which already
claimed the token. Expired queued messages are republished and expired running
jobs recover through the same finite execution-attempt budget.

Defaults are three execution attempts for transient infrastructure failures, a
300-second soft task limit, and a 360-second hard limit. Invalid survey data is
terminal; empty surveys, absent usable anchors, and incomplete source bundles
are explained skips. Worker timeout exceptions remain visible to Celery.

The worker mirrors the existing remote through the shared read-only,
authenticated Git utilities, reads the recorded SHA, and materializes source
files in its own temporary directory. It neither provisions a repository nor
checks out, resets, or deletes the shared upload working copy. Ariane and
Compass use the same source-materialization helpers as historical regeneration.

The artifact service uploads an immutable object, then publishes its database
row and the job's ready state in the same transaction. Ownership and deadline
are checked under lock immediately before publication. A late worker cannot
publish after losing its token. Failed publication cleans up the unpublished
object where possible. Existing artifacts remain readable, and duplicate
successful processing never replaces an already generated artifact.

Before storage I/O, the worker durably journals its unique object key. A worker
hard kill therefore leaves recoverable cleanup work. The dispatcher removes
unpublished, unreferenced objects after the execution deadline plus a
five-minute grace period, retaining failed deletions for another pass. The
journal is bounded by the execution-attempt limit. Manual retry waits for
remaining object cleanup. Cleanup rotates inspected journals to the end of its
bounded queue, so persistent deletion failures cannot starve later objects. A
generation's `updated_at` also reflects this cleanup activity. Abandoned
token-named scratch directories receive the same grace period; directories owned
by a live execution are preserved.

Cleanup records belong to their source commit. Deleting that commit or project
also deletes its journal; an unpublished object left by a killed worker can then
require operator storage cleanup. This journal is not a bucket-wide orphan
inventory, and it does not replace the existing retired-artifact retention
policy.

Artifact selection uses source authored date, source-record creation date, and
source SHA as deterministic tie breakers. It does not use job completion time;
an older task finishing late cannot win an equal-authored-date race with a newer
recorded source. These are the existing source-ordering semantics with
deterministic ties, not a new Git ancestry reconstruction policy. Project
metadata, GIS-view collection authorization, and account archive selection share
that same ordering.

## Status and diagnostics

`GET /api/v2/projects/<project UUID>/geojson-status/` requires the existing
source read permission and returns a normal raw v2 JSON response:

- `state`: `pending`, `queued`, `running`, `ready`, `skipped`, `failed`, or
  `not_requested`.
- `source_commit_sha`: the latest recorded source revision, or null.
- `generation_commit_sha`: the latest requested survey-generation revision, or
  null. An unrelated later document upload must not hide that job.
- `geojson_commit_sha` and `geojson_revision`: the same selected available
  artifact, or null if none exists.
- `error_code`, `error`, and `updated_at`: bounded diagnostics and generation
  update time, or null where unavailable.

Status is read before artifact metadata so a response reporting ready cannot
capture an artifact snapshot from before that publication. The project page
polls active jobs every five seconds, pauses while hidden, and stops at terminal
states. It identifies retained maps from earlier revisions and separates upload
success from map failure. Diagnostic strings are rendered as text, never HTML.

The all-project GeoJSON metadata endpoint additionally returns
`geojson_commit_sha` alongside `geojson_file` and `geojson_revision`, all from
the same artifact. Source `latest_commit` retains its own meaning. Existing
clients can continue comparing artifact revisions to refresh maps even if the
source SHA has not changed since the previous metadata request.

Ariane coordinates come only from explicit `Latitude` and `Longitude` fields.
Comments never supply coordinates, UTM zones, or declination. Invalid coordinate
errors include station and field context supplied by openspeleo-lib's validation
notes. Unexpected errors receive generic public messages; detailed exceptions
remain in operator logs. The exporter never guesses coordinate corrections.

## Recovery and verification

Use the generation administration to inspect pending/failed/skipped work and
retry a terminal job. Administrators can also add a generation request for a
recorded commit when optional bookkeeping was unavailable. Retrying identical
invalid source will fail again; correct the source and upload a new revision.
Broker recovery normally needs no manual retry. Existing successful maps are
preserved throughout.

Historical exporter-driven replacements remain an explicit operation through
[the rebuild command](project-geojson-command.md). The upload worker does not
invoke that command or its shared-checkout lifecycle. See
[artifact revisions and retention](project-geojson-artifacts.md) for storage and
cache behavior.

A successful maintenance publication marks any existing generation record ready
in the artifact's transaction and revokes an active upload worker's ownership.
This clears obsolete failure diagnostics after a rebuild while retaining the
worker's unpublished-object journal for cleanup. Failed publication rolls back
both artifact and status changes.

Verification covers real push-before-record ordering, request rollback and SQL
savepoint failure, exact-SHA source reads, duplicate and ambiguous dispatch,
timeouts and lease recovery, stale-worker fencing, publication failures,
retained artifacts, permissions, and UI polling/escaping. Backend and frontend
tests run inside the existing application container. Real GitLab tests reuse the
bounded [canonical project pool](ci-gitlab-testing.md); generation-unit tests
use local repositories and storage.

## Activation and standalone releases

Apply the GIS and survey migrations, load the updated application and worker
code, then run `python manage.py install_background_schedules` with the existing
Celery worker and beat services enabled. Generation runs on
`background_control`; no additional queue or service is required. The dispatcher
schedule and database migration are required for pending jobs to progress.

The monorepo uses its editable openspeleo-lib source. Standalone SpeleoDB must
adopt a published library release containing the aliased-field validation fix
and station diagnostics, updating its dependency and lock normally. Upload
isolation works independently of that release; the library change improves early
validation and the explanation shown for invalid coordinates.
