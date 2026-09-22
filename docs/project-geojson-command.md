# Project GeoJSON Build Command

`build_project_geojsons` materializes survey sources from project Git history
and stores a `ProjectGeoJSON` for each supported commit. It supports a bounded
single-project workflow for repairs and a batch workflow for backfills.

The former `build_all_project_geojsons` command has been removed. There is no
compatibility alias because the new command requires operators to choose the
scope explicitly.

## Command contract

Exactly one selection mode is required:

```bash
python manage.py build_project_geojsons --all
python manage.py build_project_geojsons --project 01234567-89ab-cdef-0123-456789abcdef
```

| Option                  | Valid mode     | Effect                                                                           |
| ----------------------- | -------------- | -------------------------------------------------------------------------------- |
| `--all`                 | Batch          | Processes all projects where `exclude_geojson=False`, newest first.              |
| `--project <uuid>`      | Single project | Processes only the identified project.                                           |
| `--fresh`               | Single project | Removes the local working copy before repository access, forcing a GitLab clone. |
| `--project_type <type>` | Batch          | Restricts the eligible queryset to one `ProjectType`.                            |
| `--force_recompute`     | Both           | Safely replaces GeoJSON artifacts that already exist.                            |

Examples:

```bash
# Backfill all eligible Compass projects.
python manage.py build_project_geojsons --all --project_type compass

# Build missing GeoJSONs for one project from a fresh GitLab clone.
python manage.py build_project_geojsons --project <project-uuid> --fresh

# Rebuild existing GeoJSONs as well as refreshing the Git source.
python manage.py build_project_geojsons \
  --project <project-uuid> \
  --fresh \
  --force_recompute
```

`--fresh` and `--force_recompute` are intentionally independent. The former
controls the Git source; the latter controls stored GeoJSON replacement. A fresh
clone without `--force_recompute` still skips commits whose GeoJSON already
exists.

## Selection and validation

Validation completes before any repository cleanup or GeoJSON write:

- Omitting the selection mode or passing both modes is an error.
- `--project` values must be valid UUIDs and identify an existing project.
- A selected project with `exclude_geojson=True` is rejected; explicit selection
  does not override the model-level exclusion.
- `--fresh` with `--all` is rejected to avoid destructive batch refreshes.
- `--project_type` with `--project` is rejected because the UUID already selects
  the project.

CLI and selection errors raise Django `CommandError` and return a nonzero exit
status.

## Processing and repository lifecycle

The command walks every non-initial commit available from `GitRepo.commits`. For
Ariane projects it materializes the TML source; for Compass projects it
materializes the TOML-declared MAK/DAT bundle. Each source is passed to the
project's existing `build_geojson()` processor and stored through the existing
`ProjectCommit` and `ProjectGeoJSON` models.

For `--project --fresh`, local-copy removal happens before `Project.git_repo` is
accessed. An absent directory is an accepted no-op. The model then follows its
existing GitLab create-or-clone path. Deletion errors other than a missing path
are surfaced so the command cannot silently process a stale checkout.

As before, every processed project's local working copy is removed in a
`finally` block. This applies to both selection modes and to successful or
failed processing.

Forced recomputation materializes and validates the complete replacement and
uploads it to a new object before changing the stored record. The database
replacement is atomic and retains the existing survey commit identity. The old
object remains stored so in-flight readers and issued signed download URLs
remain usable. Its storage key is logged after a successful commit for later
operator cleanup. Generation, validation, upload, or database failure preserves
the previous artifact; unpublished replacement uploads are cleaned up. Normal
`ProjectGeoJSON` model updates remain forbidden. A non-forced run also preserves
an artifact created concurrently while its source was being processed.

Each replacement receives a new `geojson_revision`; OGC caches include this
revision, so a late reader cannot populate the replacement's cache with old
features. See [GeoJSON artifact contract](project-geojson-artifacts.md) for
client refresh behavior and the additive shot-color property.

Batch mode logs a project-level failure and continues with the remaining
projects. Single-project mode raises `CommandError` for a repository-level
failure so automation receives a nonzero result. Commit-level materialization or
generation failures remain isolated to that commit and are logged before the
command continues.

## Performance and verification

Runtime and GitLab traffic scale with the number of selected projects and the
full reachable commit history of each repository. Prefer `--project` for repairs
and use `--project_type` to bound batch work. `--force_recompute` also adds
processor work, an object-storage upload, and retained historical storage for
every existing GeoJSON.

Regression coverage is in
`speleodb/common/management/commands/tests/test_build_project_geojsons.py` and
includes CLI validation, selection boundaries, cleanup behavior, batch versus
targeted errors, Ariane and Compass generation, skipping, and forced
recomputation.

Artifact transaction, storage-failure, metadata-query and cache-revision
coverage also lives in `speleodb/gis/tests/test_project_geojson_replacement.py`.

## Adding colors to previously generated surveys

Library updates affect newly generated artifacts; they do not rewrite stored
history. Uploading identical source files returns HTTP 304 before GeoJSON
generation and preserves the stored artifact, including its colors and revision.
A new revision title alone does not regenerate it. After the updated exporters
are installed, an operator can pilot `--project <uuid> --force_recompute`,
inspect the generated colors and revision, then run bounded batches with
`--all --project_type ariane --force_recompute` and
`--all --project_type compass --force_recompute`. The command processes
historical commits as well as the newest commit, including artifacts pinned by
GIS views. Keep storage/database backups and review logged failures before the
next batch. Excluded projects remain excluded.

This is an explicit maintenance operation on server checkouts. It must not run
as a database migration or against a developer's working copy: the command's
existing final cleanup removes each processed local Git checkout. No artificial
survey commits or client offline-cache purge are needed. Existing offline maps
remain usable in survey-color fallback until a successful refresh.
