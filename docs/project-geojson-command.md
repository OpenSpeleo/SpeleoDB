# Project GeoJSON Build Command

`build_project_geojsons` materializes survey sources from project Git history and
stores a `ProjectGeoJSON` for each supported commit. It supports a bounded
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

| Option | Valid mode | Effect |
|---|---|---|
| `--all` | Batch | Processes all projects where `exclude_geojson=False`, newest first. |
| `--project <uuid>` | Single project | Processes only the identified project. |
| `--fresh` | Single project | Removes the local working copy before repository access, forcing a GitLab clone. |
| `--project_type <type>` | Batch | Restricts the eligible queryset to one `ProjectType`. |
| `--force_recompute` | Both | Deletes and recreates GeoJSON records that already exist. |

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

The command walks every non-initial commit available from `GitRepo.commits`.
For Ariane projects it materializes the TML source; for Compass projects it
materializes the TOML-declared MAK/DAT bundle. Each source is passed to the
project's existing `build_geojson()` processor and stored through the existing
`ProjectCommit` and `ProjectGeoJSON` models.

For `--project --fresh`, local-copy removal happens before `Project.git_repo` is
accessed. An absent directory is an accepted no-op. The model then follows its
existing GitLab create-or-clone path. Deletion errors other than a missing path
are surfaced so the command cannot silently process a stale checkout.

As before, every processed project's local working copy is removed in a
`finally` block. This applies to both selection modes and to successful or failed
processing.

Batch mode logs a project-level failure and continues with the remaining
projects. Single-project mode raises `CommandError` for a repository-level
failure so automation receives a nonzero result. Commit-level materialization
or generation failures remain isolated to that commit and are logged before the
command continues.

## Performance and verification

Runtime and GitLab traffic scale with the number of selected projects and the
full reachable commit history of each repository. Prefer `--project` for repairs
and use `--project_type` to bound batch work. `--force_recompute` also adds
processor work and object-storage deletes/uploads for every existing GeoJSON.

Regression coverage is in
`speleodb/common/management/commands/tests/test_build_project_geojsons.py` and
includes CLI validation, selection boundaries, cleanup behavior, batch versus
targeted errors, Ariane and Compass generation, skipping, and forced
recomputation.
