# Background survey map generation

Survey source history is authoritative; GeoJSON is an optional derived artifact.
Uploads validate, save, commit and push source files, then construct commit
metadata. After SQL commit an eligible upload schedules its exact committed
revision on `background_control`. Failed pushes, rolled-back requests, unchanged
uploads, excluded projects and unrelated file types create no map execution.

HTTP success confirms source-save success. The upload response has no
`geojson_status` field and the former GeoJSON status endpoint is removed.
Optional map-scheduling failure is logged and recorded in task results when a
task row could be created, without rejecting the saved source. SQL bookkeeping
errors are isolated by a savepoint. Git and SQL remain separate systems: process
exit between push and SQL commit can leave remote history ahead of metadata.

Celery TaskResult is the sole execution record. There is no generation model,
dispatch lease, automatic retry, recovery callback or periodic map scheduling
coordinator. Superusers explicitly rerun failed work through
[Operations](admin-operations.md). Broker timeouts can mean ambiguous delivery;
inspect receipts and worker logs before rerunning. Whole-worker loss can leave
completion unconfirmed. Do not infer success from absence of a terminal result.

The worker mirrors the existing remote read-only in a disposable disk workspace
under `GEOJSON_GENERATION_SCRATCH_DIR`. It reads immutable source blobs,
converts the requested revision, and uploads an immutable artifact before
publishing its row. Shared conversion serves both CLI and Celery. Expected
omissions are explained skips; unexpected conversion errors fail the task. Run a
history reset while the project is idle. Avoid editing or submitting other work
for that project until the reset finishes.

Git handles close and temporary sources are removed on success, ordinary failure
and soft timeout. Workspace cleanup preserves active worker directories; later
sweeps remove abandoned local directories. Hard kill cannot run cleanup. Without
an upload journal it may also leave an orphaned object; the next explicit full
history reset purges the project namespace. Ordinary failed unpublished uploads
are cleaned immediately where possible. No hidden recovery journal replaces the
removed model.

Artifact selection retains authored-date, source-record creation-date and SHA
ordering, independent of task completion time. Force replacements retain retired
objects for existing signed URLs; only explicit history reset purges them. See
[artifact retention](project-geojson-artifacts.md) and
[the historical conversion command](project-geojson-command.md).

Ariane coordinates come from explicit Latitude/Longitude fields. Comments do not
supply coordinates or declination. Stalagmight conversion uses OpenSpeleo's
native SQLite adapter and common exporter. Invalid data does not become guessed
map coordinates. Missing sources, empty surveys and absent usable anchors are
skips; invalid surveys fail while preserving earlier artifacts. Solver memory
requirements are unchanged by disk-backed source workspaces.

Deploy matching web and worker code together, draining old generation work and
cleaning journaled unpublished objects before table removal. The detailed
migration, consumer coordination and runtime verification procedure is in
[Operations](admin-operations.md).
