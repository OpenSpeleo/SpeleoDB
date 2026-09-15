# Account exports and durable background jobs

## Intent and ownership

Account exports produce a ZIP containing full reachable Git history, the latest
stored project GeoJSON, GIS source/processed files, GPS GeoJSON/derived GPX, and
landmark collections. This is a portable data export, not a complete database
restore. Each populated project extracts into directly readable working files
and a `.git/` directory containing its full reachable history. Zero-commit
projects contain only a zero-byte file named `PROJECT IS EMPTY`.

Django owns user authorization, accepted requests, retries, and artifact expiry.
`django-celery-results` stores technical execution results in the application
PostgreSQL database. Redis delivers messages. Kanchi observes Celery events and
stores its own operational history in a separate database/user on the existing
PostgreSQL server. Cache and Celery share Redis, using logical databases 0 and 1
respectively, with AOF persistence and no eviction. Losing
Kanchi never loses an accepted request or prevents a download.

**Celery Beat owns all scheduling. Railway hosts continuously running services;
there are no Railway cron jobs or cron schedules.**

One Celery worker service consumes both `exports` and `background_control` with
concurrency one. Add replicas of that service when more capacity is needed;
keep Beat a singleton. Long exports can delay maintenance and notifications.
Expiry authorization is checked at download time independently of that delay.

## Lifecycle

Creation serializes on the requester row and enforces a conditional unique
constraint for active export jobs. The job and initial attempt commit before
message publication. A failed publish leaves the attempt dispatchable by the
one-minute maintenance sweep. Unclaimed messages can be republished after ten
minutes; duplicate deliveries are ignored without overwriting Celery results.

A worker atomically claims the current queued attempt using its expected Celery
task UUID. It records an execution deadline from `EXPORTS_HARD_TIME_LIMIT` and a unique artifact key
before touching storage. Progress and publication updates require ownership of
that current attempt. Old or replayed invocations cannot publish results.

Generation moves through queued, running, retry_wait, ready, partial, and failed.
The initial cycle has at most three attempts, separated by one and five minutes.
Manual retry starts another bounded cycle while preserving attempt history.
Maintenance reclaims interrupted attempts after the deadline plus five minutes.

Expiry and email delivery are independent of generation outcome. A partial
archive is a successfully completed Celery invocation whose business result
contains omissions; an email failure does not regenerate the archive.

## Permissions and source capture

At generation start the builder evaluates the existing centralized permission
querysets with minimum READ_ONLY, active resources, and project deduplication.
WEB_VIEWER project access is excluded. It honors that attempt's selected resources
even if permissions are subsequently revoked. Retries take a fresh snapshot.
Landmark enumeration does not create a personal collection.

Sources are captured individually; GitLab, database rows, and uploaded objects
are not an atomic cross-system snapshot. The manifest records captured revisions,
resource IDs, checksums, paths, and omissions. Absent optional project GeoJSON is
a note. A missing individual selected file can produce a partial export; broad
storage authorization/outage errors fail the attempt. No eligible sources yields
a valid empty archive, while every selected resource failing yields a failure.

## Resource and credential boundaries

The builder clones all advertised refs into an isolated temporary `.git/`
directory, verifies the repository, and checks out its current files alongside
that directory. This preserves history while making the contents useful as soon
as the ZIP is extracted. It never uses shared working repositories or helpers
which create remote projects. Authentication uses an ephemeral askpass
file/environment. Credentials are not archived or passed as task arguments.
The manifest records the checked-out commit. If the remote's default HEAD is
unavailable, a deterministic branch/tag commit supplies the working files while
all captured refs remain preserved. Checkout disables hooks and submodule
recursion. Tracked symlinks are represented by regular files containing their
link targets, with the original symlink objects preserved in Git; the exporter
never follows a link to copy files outside the project.
Every selected project is cloned from GitLab even when no shared local checkout
exists. Project creation initially writes only a database row; the first upload
initializes its remote repository. When cloning reports a missing remote and the
project has no recorded commits, the exporter verifies access to the configured
GitLab namespace and checks the project's remote metadata. A never-initialized
project or an accessible zero-commit repository is represented by the empty
`PROJECT IS EMPTY` marker alone, without any Git directory, remote creation, or
invented commits. The
manifest records `repository_state` as `uninitialized` or `empty` and adds an
informational note; this does not make the export partial.

Projects with recorded history report missing/inaccessible or unexpectedly empty
remotes as omissions; a recreated empty repository cannot hide known history loss
behind a successful empty-project marker. Configuration, authentication, and
network failures cannot become empty repositories. The commit-presence snapshot
uses one bulk database query; extra GitLab API reads occur only after a
missing-remote clone failure. A successful clone always preserves remote history,
even if Django has not indexed any commits. Local development database copies
need the corresponding GitLab
repositories as well as application rows for projects with existing history.
Only advertised refs and reachable Git history are exported; server reflogs,
unreachable objects, external LFS objects, and submodule repositories are excluded.

Each Git command runs under a small standard-library supervisor. The task owns
the only write end of a liveness pipe; the supervisor watches its read end. A
killed task closes the pipe even when Python cleanup cannot run. Pipe closure,
termination signals, and execution deadlines terminate the entire Git process
group, including its remote helpers, before another attempt starts consuming
resources. Git never inherits the liveness pipe.

Storage downloads stream to explicit disk files. Sources are staged before ZIP
entries are opened; a mid-entry write error fails the archive. ZIP64 supports
large exports, and packed/compressed sources avoid redundant compression.
Each worker replica processes one task at a time and releases each staged source.
Project scratch storage includes both the Git object database and checked-out
files, so capacity planning must account for both copies of current content.
Scratch-space checks preserve a configurable reserve; abandoned attempt folders
are reclaimed on subsequent worker activity or removed with ephemeral storage.
Git's disk usage is checked periodically; the reserve is not a filesystem quota.
Size worker storage for representative archives and monitor free space.

Derived GPX conversion defaults to 16 MiB/250,000 positions. Tracks beyond those
limits retain their stored GeoJSON and report the GPX omission. Imported GPX
timestamps/original GPX files cannot be reconstructed because they are not stored.

## Private download and retention

New archive objects live directly under `exports/{filename}.zip` in the existing
bucket. Filenames are `speleodb-export-YYYY-MM-DDTHH-MM-SSZ-<attempt-uuid>.zip`;
the timestamp is UTC at attempt start. The attempt ID prevents retries from
overwriting earlier objects. The same basename is recorded on the artifact,
included in notifications, and used for downloads. Historical stored keys remain
authoritative, including the previous nested layout.

`ExportStorage` uses the shared private backend in `speleodb.utils.s3_storages`.
Private production files use CloudFront signed URLs; local development uses
S3 presigning against the browser endpoint. Shared transfer and version-cleanup
methods use the backend's configured S3 connection, while the export adapter
provides ZIP metadata and validates the export prefix. Uploads retain bounded
multipart transfers (two threads, 16 MiB parts) and private/no-store caching.
Exports are ordinary ZIP files with no password.

Signed downloads preserve the recorded object version, filename, and
`private, no-store` response headers. The shared URL method translates boto API
parameter names to S3 HTTP query names when signing a CloudFront URL. The
`exports/*` CloudFront behavior must require signed viewer requests, forward
those query parameters, and disable caching. Its OAC has version-read permission;
anonymous direct S3 reads remain denied. See [the production policy and setup
steps](export-storage-policy.md) before deploying this configuration.

After upload and publication, availability lasts 24 hours. Download requests
require an active owner or superuser; staff status alone does not authorize other
users' downloads. Presigned URLs last at most five minutes and never extend the
availability deadline. A transfer started before expiry can finish afterward.

Beat schedules deletion every five minutes. Exact object versions are removed
when known; unpublished attempt keys are reconciled across versions. Failed
deletions remain tracked and retryable. Prefix-scoped S3 lifecycle rules provide
a two-day fallback for current objects, noncurrent versions and incomplete
multipart uploads; physical deletion is asynchronous, not precisely 24 hours.
Application history is retained for 90 days, Celery results for 30 days; records
needed for pending deletion are preserved.

History cleanup locks and rechecks each eligible job before deleting its related
records. This keeps an accepted retry from being collected as obsolete history;
if cleanup finishes first, retry/resend returns an unavailable-export response.

## Notifications and operations

Notifications use the verified primary email and link to the authenticated
account export page. A separate claim token prevents concurrent sends. Failed
sends retry up to five times without changing artifact expiry. Delivery is
at-least-once: an ambiguous provider timeout can result in a duplicate email.
Interrupted sends consume the same attempt budget. After five failed or
unconfirmed attempts, another send requires an explicit admin retry.

The Django admin provides controlled retry/resend actions, attempt history,
artifacts, and links to technical Celery records and the protected Kanchi console.
Arbitrary Kanchi reruns of export tasks are rejected by the task-ID guard.
Automatic Kanchi recovery workflows stay disabled; retention cleanup is enabled.

## Verification

Run every test, linter, type checker, build, and runtime check inside Docker.
See the implementation task for command output and final evidence. Integration
uses a dedicated test Redis broker, test database, test GitLab group and test
storage bucket. Real worker tests must cover outbox recovery, duplicate delivery,
worker interruption, stale publication, email failure, expiry enforcement,
version deletion, and monitoring outage isolation. Archive tests validate Git
restoration, source bytes, permissions, GeoJSON/GPX, ZIP integrity and checksums.
Real GitLab regressions cover never-initialized projects, empty repositories,
remote history absent from the database index, missing recorded history, and
invalid credentials or namespace configuration. Populated project tests verify
directly readable current files, a clean working tree, and preserved historical
branches/tags after extraction. Zero-commit project tests assert exactly one
empty marker file and no Git directory. Real download tests verify the filename
returned to the browser.

The populated GitLab fixture can receive a temporary HTTP 404 when it creates
the first commit immediately after project creation. Only that initial commit
is retried, with five attempts and 1/2/4/8-second backoff. A persistent 404 is
raised with its original details; other HTTP and transport errors propagate
without this retry because the write may have succeeded. Successful setup adds
no requests or delay. The production client and later fixture writes retain
their existing behavior.

`test_gitlab_initial_commit.py` exercises this fixture policy with real HTTP
responses and the python-gitlab client: immediate success, temporary 404
recovery, bounded exhaustion, other HTTP failures, and a lost response after
receiving the write. The live archive test still verifies actual GitLab commits,
branches, tags, and restored history.

Deploy one reviewed release to web and workers after checking storage access and
retention configuration. Verify exports from an ordinary active account, a real
retention cycle, and a representative large archive. See
`background-jobs-operations.md` for Compose and Railway details.
