# Project GeoJSON Build Command

`build_project_geojsons` materializes survey sources from project Git history
and stores a `ProjectGeoJSON` for each supported commit. Each project uses its
own disposable directory on disk. The command never opens, resets, or deletes
the shared checkout used by uploads.

## Command contract

Exactly one selection mode is required:

```bash
python manage.py build_project_geojsons --all
python manage.py build_project_geojsons --project <project-uuid>
```

| Option                                   | Valid mode     | Effect                                                   |
| ---------------------------------------- | -------------- | -------------------------------------------------------- |
| `--all`                                  | Batch          | Processes eligible projects synchronously, newest first. |
| `--project <uuid>`                       | Single project | Processes only the identified project's history.         |
| `--project_type <type>`                  | Batch          | Restricts the eligible queryset to one `ProjectType`.    |
| `--force_recompute`, `--force-recompute` | Both           | Safely replaces GeoJSON artifacts that already exist.    |

Every project receives a fresh read-only clone, so the former `--fresh` option
is removed. Fresh source acquisition and forced artifact replacement are
separate concepts: without `--force-recompute`, existing artifacts are skipped.
The former `build_all_project_geojsons` command also remains removed.

```bash
# Backfill missing GeoJSONs for eligible Compass projects.
python manage.py build_project_geojsons --all --project_type compass

# Regenerate all supported historical artifacts for one project.
python manage.py build_project_geojsons --project <project-uuid> --force-recompute
```

Omitting a selection, selecting both modes, passing an invalid or unknown UUID,
selecting an excluded project, or combining `--project_type` with `--project`
raises `CommandError`. These validation failures happen before repository work.

## Schedule independent project rebuilds

Use **Django admin → Background operations → Operations** to schedule one
project or all eligible projects. Force defaults to off. The request precreates
TaskResult rows and directly publishes one independent task per project after
commit, with GroupResult recording batch IDs. There is no scheduling
coordinator. Receipts distinguish confirmed, ambiguous and unattempted
publication. Inspect individual project outcomes; no batch success implies
successful conversion.

The command and Celery tasks call `Project.build_geojsons()`, which acquires a
read-only clone and invokes `Project.convert_geojson_history()`. These model
methods return processed, generated, existing, skipped and failed counts.
Conversion logs each unexpected failure with its traceback, continues
independent revisions, then raises an aggregate exception so partial failures
fail Celery execution. Expected omissions such as missing sources or unusable
anchors remain skips. Tasks do not automatically retry; Run again creates a new
execution. See [Operations](admin-operations.md) for confirmation, status and
recovery.

## Repository and temporary-file lifecycle

The workspace root is `GEOJSON_GENERATION_SCRATCH_DIR`, defaulting to
`/tmp/speleodb-geojson`. Each rebuild creates a private `work-rebuild-`
directory under it. The authenticated read-only mirror helper clones there
without provisioning a GitLab project or persisting credentials. Git
authentication helper files, repository contents and extracted sources all
belong to that task's directory. Sources are streamed from immutable commit
blobs into per-commit files rather than buffered as whole Git blobs in memory.

The command removes each commit's extracted files, then removes the whole task
workspace on success, failure, or a propagated soft timeout. Shared upload
working copies and remote repositories remain intact. The shared workspace
helper preserves active worker directories and removes abandoned directories
during a later sweep after an abrupt worker kill. See
[background generation](project-geojson-background.md) for workspace cleanup and
local-filesystem scope; no generation execution is automatically recovered.

Each project task has a configurable six-hour soft limit
(`GEOJSON_REBUILD_SOFT_TIME_LIMIT`) and a hard limit one minute later
(`GEOJSON_REBUILD_HARD_TIME_LIMIT`). A soft timeout must stop processing and
allow cleanup; a hard kill cannot execute Python cleanup and relies on
abandoned-workspace recovery. Previously published replacements remain stored.
Error handling recognizes timeouts even when another exception wraps them,
provided the converter propagates the error. Compass may internally swallow
coordinate conversion exceptions; its soft interruption remains best effort and
the hard limit is the final bound.

Disk-backed clones and per-project tasks reduce shared state and isolate worker
failures. They do not bound all converter memory: the Compass solver can still
allocate large dense arrays for a large survey. Do not treat this transition as
a fix for the observed solver OOM, or automatically repeat a failing project.
Ensure scratch has enough disk space for a full clone and one extracted
revision.

## History traversal and artifact replacement

The command walks complete default-branch history with `iter_commits("HEAD")`,
including the initial revision. Revisions without complete supported source
files are explained skips. Ariane materializes its TML source; Compass
materializes its TOML-declared MAK/DAT bundle; Stalagmight materializes the
original `stalagmight.stalx` SQLite blob at each selected commit. Native
conversion uses the same OpenSpeleo adapter and common exporter as background
generation. The existing `build_geojson()` processors and `ProjectCommit`
identity remain authoritative. Neither the command nor worker guesses missing
coordinates or reads corrections from comments.

Forced recomputation validates a complete replacement and uploads a new object
before atomically changing the stored artifact. Generation, validation, upload
or database failure preserves the previous artifact. Unpublished replacement
uploads are cleaned up. A non-forced run preserves an artifact created
concurrently. Published old objects remain stored for in-flight readers and
issued signed URLs; their keys are logged for later operator cleanup. Temporary
Git/source cleanup does not remove those published objects.

Each replacement receives a new `geojson_revision`, also used by OGC caches. See
the [artifact contract](project-geojson-artifacts.md) for refresh behavior and
section colors. The synchronous `--all` CLI logs project-level failures and
continues, then raises `CommandError` if any project failed. The single-project
command also raises `CommandError` for failures. Both process independent
revisions before reporting aggregate conversion failure.

## Rollout and verification

Deploy matching application and worker code before submitting operations.
Already-running workers retain their old task signatures until restarted. Drain
old work before removing the journal and restart workers with matching code;
otherwise a task can fail before processing begins. See
[Operations](admin-operations.md) for coordinated rollout.

Coverage in `speleodb/background_jobs/tests/test_operations.py` protects direct
fan-out, force flags and honest partial publication. Conversion and task tests
exercise immutable source revisions, aggregate failure and real worker delivery.
Command integration tests in
`speleodb/common/management/commands/tests/test_build_project_geojsons.py`
exercise Ariane, Compass, and Stalagmight history, skip/replacement behavior,
read-only source access, shared-checkout preservation, and temporary cleanup
under success, failure and an actual OS soft-timeout signal. GitLab integration
reuses the bounded canonical repository pool. Run the backend suite and
repository checks in the application Docker container; never enqueue
verification tasks against development data.

Runtime and Git traffic scale with each project's reachable history. Forced
replacement adds conversion, upload and retained artifact storage for every
existing artifact. Prefer a single-project pilot before scheduling all projects.
Updated exporters do not rewrite stored history, and identical uploads still
return HTTP 304. A forced rebuild needs no artificial survey commits or client
cache purge; clients receive the new revision after a successful online refresh.

Normal uploads directly enqueue their committed revision after transaction
commit. Broker failures leave TaskResult receipts showing uncertain or
unattempted submission; they are not automatically republished. A superuser must
inspect the receipt and worker state, then explicitly schedule another execution
when needed. Those short generation tasks share source and workspace helpers but
never invoke the historical scan. See
[background generation](project-geojson-background.md) for status and manual
recovery behavior.
