# Project GeoJSON Build Command

`build_project_geojsons` materializes survey sources from project Git history
and stores a `ProjectGeoJSON` for each supported commit. Each project uses its
own disposable directory on disk. The command never opens, resets, or deletes
the shared checkout used by uploads.

## Command contract

Exactly one selection mode is required:

```bash
python manage.py build_project_geojsons --all
python manage.py build_project_geojsons --project 01234567-89ab-cdef-0123-456789abcdef
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

## Enqueue independent project rebuilds

`speleodb.surveys.tasks.refresh_all_projects_geojson` is a short coordinator. It
streams eligible project IDs and enqueues exactly one
`refresh_project_geojson(project_id, force_recompute=True)` task per ID. It does
not clone, convert, wait for children, or invoke the command in batch mode.

From the application environment:

```bash
python manage.py shell -c 'from speleodb.surveys.tasks import refresh_all_projects_geojson; print(refresh_all_projects_geojson.delay().id)'
```

Alternatively, sign in as a superuser and open **Django admin → Background jobs
→ Background jobs** (`/admin/background_jobs/backgroundjob/`). **Rebuild all
GeoJSONs** enqueues the coordinator, regardless of list selection or filters.
The CSRF-protected POST redirects to the list; refreshing that page does not
resubmit the request. Each new button submission schedules another batch.

The coordinator result contains `enqueued` and a `tasks` list of `project_id` /
`task_id` pairs. Each successful publication is also logged. Its `SUCCESS` means
scheduling finished; inspect each child's result and worker logs to assess the
rebuild. Broker failure stops the coordinator, leaving already published
children independent and runnable. Review those IDs before resubmitting to avoid
unintentionally overlapping work. No whole-batch automatic retry is installed.
An empty eligible scope returns zero children without cloning or writing data.

Each child rechecks that its project still exists and is not excluded before
calling the single-project command. Deleted or newly excluded projects return
`skipped`; completed commands return `completed`. Repository failures and task
timeouts fail only that child. Commit-level materialization/conversion failures
are logged and isolated so other commits can still be rebuilt; a completed child
can therefore require inspection of logged conversion failures.

To retry one inspected project:

```bash
python manage.py shell -c 'from speleodb.surveys.tasks import refresh_project_geojson; print(refresh_project_geojson.delay("<project-uuid>", force_recompute=True).id)'
```

The coordinator and children use `background_control`. The existing worker
concurrency controls how many projects execute at once. A single-slot worker
still converts projects sequentially, but each project has its own result,
limits and cleanup boundary. Other queued work may wait behind those children.
No recurring rebuild schedule, automatic child retry, distributed singleton
lock, or resume checkpoint is installed.

## Repository and temporary-file lifecycle

The workspace root is `GEOJSON_GENERATION_SCRATCH_DIR`, defaulting to
`/tmp/speleodb-geojson`. Each rebuild creates a private `work-rebuild-`
directory under it. The authenticated read-only mirror helper clones there
without provisioning a GitLab project or persisting credentials. Git
authentication helper files, repository contents and extracted sources all
belong to that task's directory. Sources are streamed from immutable commit
blobs into per-commit files rather than buffered as whole Git blobs in memory.

The command closes Git handles and removes each commit's extracted files, then
removes the whole task workspace on success, failure, or a propagated soft
timeout. Shared upload working copies and remote repositories remain intact. The
shared workspace helper holds an ownership lock while work is active;
maintenance can remove abandoned directories after an abrupt worker kill without
deleting a live task's files. See
[background generation](project-geojson-background.md) for the recovery cadence
and local-filesystem scope.

Each project task has a configurable six-hour soft limit
(`GEOJSON_REBUILD_SOFT_TIME_LIMIT`) and a hard limit one minute later
(`GEOJSON_REBUILD_HARD_TIME_LIMIT`). The coordinator uses normal short-task
limits. A soft timeout must stop processing and allow cleanup; a hard kill
cannot execute Python cleanup and relies on abandoned-workspace recovery.
Previously published replacements remain stored. Error handling recognizes
timeouts even when another exception wraps them, provided the converter
propagates the error. Compass may internally swallow coordinate conversion
exceptions; its soft interruption remains best effort and the hard limit is the
final bound.

Disk-backed clones and per-project tasks reduce shared state and isolate worker
failures. They do not bound all converter memory: the Compass solver can still
allocate large dense arrays for a large survey. Do not treat this transition as
a fix for the observed solver OOM, or automatically repeat a failing project.
Ensure scratch has enough disk space for a full clone and one extracted
revision.

## History traversal and artifact replacement

The command walks every non-initial commit available from `GitRepo.commits`.
Ariane materializes its TML source; Compass materializes its TOML-declared
MAK/DAT bundle. The existing `build_geojson()` processors and `ProjectCommit`
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
continues; the single-project command raises `CommandError` for repository-level
failure. Both log and isolate ordinary commit-level failures.

## Rollout and verification

Deploy matching application and worker code before submitting a coordinator.
Already-running workers retain their old task implementation, which performs the
entire rebuild inline. Let an existing rebuild finish or inspect its failure
before enqueueing the new flow. The direct-upload scheduling and maintenance
schedule transition is documented in
[background operations](background-jobs-operations.md).

Coverage in `speleodb/surveys/tests/test_tasks.py` exercises real broker
messages, exact fan-out cardinality and force flags, empty scope,
deleted/excluded projects, and independent child failure. Command integration
tests in
`speleodb/common/management/commands/tests/test_build_project_geojsons.py`
exercise Ariane and Compass history, skip/replacement behavior, read-only source
access, shared-checkout preservation, and temporary cleanup under success,
failure and an actual OS soft-timeout signal. GitLab integration reuses the
bounded canonical repository pool. Run the backend suite and repository checks
in the application Docker container; never enqueue verification tasks against
development data.

Runtime and Git traffic scale with each project's reachable history. Forced
replacement adds conversion, upload and retained artifact storage for every
existing artifact. Prefer a single-project pilot before scheduling all projects.
Updated exporters do not rewrite stored history, and identical uploads still
return HTTP 304. A forced rebuild needs no artificial survey commits or client
cache purge; clients receive the new revision after a successful online refresh.

Normal uploads directly enqueue their committed revision after transaction
commit, with durable recovery for broker failure. Those short generation tasks
share source and workspace helpers but never invoke the historical scan. See
[background generation](project-geojson-background.md) for status and retry
behavior.
