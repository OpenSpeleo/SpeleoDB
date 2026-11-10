# Administrator operations

Active superusers can open **Background operations → Operations** in Django
admin. Staff access and project ADMIN permission do not authorize operations.
Project selectors use Django admin autocomplete: type a name or UUID and select
the matching project. Results include both name and UUID. Each action occupies a
separate full-width row.

Export jobs retain their existing permissions and lifecycle. Task results and
group results remain in their owning applications with their existing URLs.

## Available actions

Recompute project GeoJSONs processes the complete supported history of one
project. Recompute all GeoJSONs submits an independent task for every eligible
project and records the task IDs in a Celery GroupResult. Excluded and
unsupported projects are omitted. The page shows the eligible count before
submission.

Force is off by default: generate missing GeoJSONs. Enabling force validates and
uploads replacements before atomically replacing database rows. A failed
replacement leaves the previous artifact usable. Retired objects remain
available under the existing signed download URL policy.

Rebuild Git history validates the existing remote before deleting anything. Its
confirmation identifies the project and explains temporary history/map
unavailability, deletion of all project GeoJSON objects, and invalidation of
existing download links. An excluded or unsupported project can rebuild history;
GeoJSON regeneration is skipped. This operation never creates, rewrites or
deletes the remote repository, and preserves settings, permissions and GIS
views.

The worker first acquires and validates a fresh read-only clone of the existing
remote in a private workspace using supervised Git commands. It then removes
commit metadata and purges the exact project storage namespace. This includes
current, retired and orphaned GeoJSON objects. Storage pagination, per-object
deletion errors and an empty-namespace check precede replacement generation. It
discards its local checkout, installs the validated clone, reconstructs
default-branch history including the initial commit, and generates eligible
maps. Temporary workspaces are removed on ordinary failures and soft timeouts.

## Results and recovery

Scheduling performs validation, task creation and broker publication in the
request; Git, storage and conversion run in Celery on `background_control`.
TaskResult is the sole execution record. Receipts show QUEUED, IN PROGRESS,
SUCCEEDED or FAILED and link each project to its task result; **Refresh status**
reloads them. A confirmed submission means the broker accepted publication, not
that conversion completed. Unattempted publication and ambiguous delivery are
shown separately. Do not assume a broker timeout means a message was rejected.

Tasks have no automatic retry or worker-loss requeue. Duplicate delivery cannot
claim an execution already started. A lost worker may leave a nonterminal
result; after its deadline the page reports **Completion unconfirmed**. Inspect
worker logs and active work before starting a new execution. **Run again**
allocates a new ID, retains the recomputation force setting, and repeats
destructive confirmation for history reset. Reset starts from zero; it has no
resume engine. Task results retain the existing Celery retention policy.

Conversion continues across independent revisions, reports processed, generated,
existing, skipped and failed counts, logs conversion failure tracebacks, and
fails the task if any revision failed. Missing supported sources, empty surveys
and unusable anchors are explained omissions. Successful revisions remain
available even when another revision fails. Correct invalid source before
rerunning it.

## Local checkouts

These actions are intended for the single-admin, low-traffic deployment. Run a
history reset while the project is idle and avoid editing or submitting other
work for that project until the reset finishes.

Reset replaces the worker's local checkout with the validated clone. Other
services continue to use their ordinary Git pull and checkout behavior. Checkout
deletion is restricted to the UUID-owned directory below the configured root and
rejects symlinks and path escapes.

## Implementation boundaries

`background_jobs.operations.schedule_operation()` validates requests, precreates
results and publishes after commit. `operation_execution()` claims those rows
once and publishes terminal status together with its encoded result. Operation
metadata also travels in Celery headers so failures before task entry retain
receipts. The admin forms and views use the custom `SpeleoDBAdminSite` while
workers retain Django's lightweight admin configuration.

`Project.git_repo` opens the local repository, acquiring it when absent.
`Project.reset_git_history()` owns history reset, storage purge and supervised
private clone installation. The Celery task then calls
`Project.convert_geojson_history()` using that fresh checkout.
`Project.build_geojsons()` shares historical conversion between CLI and workers.
`replace_project_geojson()` owns validation, upload and atomic publication.

## Coordinated rollout

Drain old GeoJSON executions and inspect pending generation records before
removing their table. Finish unpublished-object cleanup with the old code and
retain project/revision identifiers needed for manual resubmission. Apply the
journal-removal migration, then deploy matching web and worker signatures and
contract consumers together. The upload response no longer contains
`geojson_status`.

Removing that required field is blocked for deployment until native client
adoption is complete. The monorepo's Cargo path override uses the checked-out
Rust SDK; it does not prove that standalone clients use those bindings. Before
deploying the field removal, publish the regenerated SDK through its existing
authorized release process, update the Compass Sidecar and Stalagmight SDK pins
and lockfiles to that published release, and verify both consumers outside the
monorepo override. A local SDK edit or regenerated fixture alone does not update
an installed client. Keep this release/adoption gate separate from
implementation and local validation; no compatibility response field is
retained.

Verify a project recomputation, an isolated history reset and a small batch.
Inspect task results, runtime logs, reconstructed history and stored artifacts.
Implementation and schema generation do not authorize production execution or
publication. No Railway service-setting change is required.
