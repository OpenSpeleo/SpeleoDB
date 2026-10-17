# Background survey map generation

Survey source history is authoritative. GeoJSON is an optional derived artifact:
invalid coordinates, exporter failures, slow computation, broker outages, or
artifact-storage failures must not reject a source upload.

## Ordering and ownership

The upload endpoint first validates and saves the source files, successfully
commits **and pushes** them to the project's Git remote, and constructs its
`ProjectCommit` metadata. Only after that does it record a
`ProjectGeoJSONGeneration` for an eligible Ariane or Compass upload. The record
is in the request's SQL transaction. A `transaction.on_commit` callback queues
that specific generation as soon as SQL commits. A failed push, request
rollback, unchanged upload (HTTP 304), excluded project, or unrelated file
upload creates no new work.

The request never parses a survey for map generation, generates GeoJSON, or
uploads a map. It makes a bounded broker publication attempt after commit; an
unavailable broker leaves durable work for recovery. HTTP 200 means the source
was saved. Its existing response fields are preserved, with additive
`geojson_status`: `pending`, `skipped`, `not_requested`, or `unavailable` if
optional bookkeeping could not be recorded. Bookkeeping runs in a savepoint and
its exception is caught after that savepoint unwinds, so even an SQL error
cannot poison the source upload transaction. The project and pushed SHA are
logged for recovery. Core source-validation, Git, and source-metadata failures
retain existing error behavior.

Git and SQL are not a distributed transaction: a process exit after a successful
push but before SQL commit can still leave remote history ahead of metadata.
This change removes map processing from that vulnerable interval; it does not
claim to make Git and SQL commits atomic.

## Scheduling, execution, and publication

Uploads and administrative requests publish their specific generation directly
through `enqueue_geojson_generation` after commit, on the existing
`background_control` queue. There is no additional periodic scheduling task
between the upload and its generation. The existing worker consumes that queue;
execution delay depends on worker capacity, especially while long maintenance
jobs run. Do not assume the map is available when the upload response arrives.

`maintain_background_jobs` runs every 600 seconds and also calls
`recover_geojson_generations`. This bounded recovery pass retries due pending
records, replaces expired queue leases, reconciles expired executions, and
cleans abandoned work. A broker outage, process exit before the commit callback,
or lost worker can therefore delay recovery until the next maintenance pass.
Backoff values are minimum due times; the ten-minute cadence and worker capacity
can extend the actual wait. Normal successful publication does not wait for
Beat.

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
authenticated Git utilities, reads the recorded SHA, and streams source blobs
into files in its own disk workspace. Both normal generation and historical
regeneration use `GEOJSON_GENERATION_SCRATCH_DIR`, defaulting to
`/tmp/speleodb-geojson`. This path must use disk-backed container storage rather
than a memory filesystem. Size its available space for concurrent repository
mirrors and extracted survey files. No whole repository or source blob needs an
in-memory archive buffer.

Each task owns one private workspace containing its Git clone, extracted source
files and temporary Git authentication helper. Git handles close before the
workspace is removed on success, exceptions and soft timeouts. The worker never
provisions a repository or checks out, resets, or deletes the shared upload
working copy. A kernel file lock protects a live workspace; maintenance and the
next task on that host remove abandoned work after the cleanup grace period.
SIGKILL cannot run Python cleanup, so this later recovery is necessary. Cleanup
can only inspect the local worker filesystem; stopped workers need their disk
reclaimed or their service resumed to run a sweep. Ariane and Compass share the
same source-materialization helpers as historical regeneration.

The artifact service uploads an immutable object, then publishes its database
row and the job's ready state in the same transaction. Ownership and deadline
are checked under lock immediately before publication. A late worker cannot
publish after losing its token. Failed publication cleans up the unpublished
object where possible. Existing artifacts remain readable, and duplicate
successful processing never replaces an already generated artifact.

Before storage I/O, the worker durably journals its unique object key. A worker
hard kill therefore leaves recoverable cleanup work. Maintenance removes
unpublished, unreferenced objects after the execution deadline plus a
five-minute grace period, retaining failed deletions for another pass. The
journal is bounded by the execution-attempt limit. Manual retry waits for
remaining object cleanup. Cleanup rotates inspected journals to the end of its
bounded queue, so persistent deletion failures cannot starve later objects. A
generation's `updated_at` also reflects this cleanup activity. Scratch
workspaces are protected by kernel locks while their processes live. Cleanup
also recognizes token-named directories left by earlier releases, preserving
those associated with a live execution lease.

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
invoke that command. Both workflows now own disposable disk workspaces. See
[artifact revisions and retention](project-geojson-artifacts.md) for storage and
cache behavior.

`refresh_all_projects_geojson` is a short coordinator: it queues one
`refresh_project_geojson` child with `force_recompute=True` per eligible project
and returns the child task IDs and count. It never clones, converts, or waits
for the children. Each child rechecks project existence and exclusion, rebuilds
only that project's history, and cleans up its own workspace. A failed child
does not prevent other project messages from executing. A coordinator `SUCCESS`
means scheduling completed, not that all artifacts were regenerated. Inspect
child results and generation/artifact state separately. There is no automatic
retry of the whole batch; after a publication interruption, inspect already
queued children before issuing another coordinator.

This separation limits failure scope and temporary-file lifetime; it does not
reduce the survey solver's intrinsic memory requirements. The Compass sparse
solver currently constructs dense matrices during adjustment. A large survey can
still exceed worker memory even with a disk clone and one project per task.
Previously published maps remain available after such a failure. Investigate
solver memory or worker sizing before retrying that project.

A successful maintenance publication marks any existing generation record ready
in the artifact's transaction and revokes an active upload worker's ownership.
This clears obsolete failure diagnostics after a rebuild while retaining the
worker's unpublished-object journal for cleanup. Failed publication rolls back
both artifact and status changes.

Verification covers real push-before-record ordering, post-commit publication,
rollback without a broker message, idempotent direct requests, SQL savepoint
failure, exact-SHA source reads, duplicate and ambiguous delivery, timeouts and
lease recovery, stale-worker fencing, publication failures, retained artifacts,
permissions, and UI polling/escaping. Backend and frontend tests run inside the
existing application container. Real GitLab tests reuse the bounded
[canonical project pool](ci-gitlab-testing.md); generation-unit tests use local
repositories and storage.

## Activation and standalone releases

When replacing the former periodic scheduling workflow:

1. Disable the owned `project-geojson-dispatch` schedule while the old workers
   are still available. Let already queued messages for the retired task and
   existing all-project rebuilds finish. Inspect active, reserved and scheduled
   work; do not purge shared queues.
2. Deploy matching web, worker and Beat application code, applying outstanding
   GIS and survey migrations. Retired task names are deliberately not registered
   as compatibility aliases in the new worker.
3. Run `python manage.py install_background_schedules`. It idempotently deletes
   the obsolete owned schedule and sets `background-job-maintenance` to 600
   seconds, preserving unrelated operator schedules. Normal direct scheduling
   needs the web and worker; recovery and cleanup also need Beat.
4. Verify the generation and per-project rebuild tasks are registered, the
   maintenance interval is 600 seconds, and the retired schedule is absent.
   Submit one rebuild coordinator when required, then follow its individual
   child IDs and artifact revisions.

Generation remains on `background_control`; no additional queue or service is
required. A source commit does not perform this deployment or enqueue work in
production.

The monorepo uses its editable openspeleo-lib source. Standalone SpeleoDB must
adopt a published library release containing the aliased-field validation fix
and station diagnostics, updating its dependency and lock normally. Upload
isolation works independently of that release; the library change improves early
validation and the explanation shown for invalid coordinates.
