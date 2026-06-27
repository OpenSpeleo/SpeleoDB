# Build Project GeoJSONs Command

## Plan

- [x] Rename `build_all_project_geojsons` to `build_project_geojsons` without a
  compatibility alias.
- [x] Require exactly one of `--all` or `--project <project_uuid>`.
- [x] Preserve `--project_type` for batch mode and `--force_recompute` for both
  modes.
- [x] Add project-only `--fresh` behavior with fail-safe local-copy removal.
- [x] Preserve batch failure isolation and make targeted repository failures
  return a nonzero command result.
- [x] Rename and expand command tests for CLI validation, selection, fresh clone,
  recomputation, and failure handling.
- [x] Document the command contract, lifecycle, performance, and verification
  strategy under `docs/`.
- [x] Run focused tests, linting, type checking, command help, the full backend
  suite, and `git diff --check`.

## Review

Implemented:

- Renamed the command to `build_project_geojsons` and removed the old command
  without an alias.
- Added required `--all` / `--project <uuid>` selection with validation for
  incompatible flags, missing projects, and excluded projects.
- Preserved batch `--project_type` filtering and both-mode
  `--force_recompute` behavior.
- Added project-only `--fresh` handling that removes the working copy before
  repository access, tolerates a missing directory, and surfaces other removal
  failures.
- Preserved batch project-failure isolation while making targeted repository
  failures return a nonzero `CommandError`.
- Expanded command coverage for CLI validation, project selection, fresh clone
  lifecycle, cleanup failures, Ariane/Compass generation, skip/recompute
  behavior, and error policy.
- Added `docs/project-geojson-command.md` and linked it from the documentation
  index.

Verification:

```text
uv run --extra local pytest speleodb/common/management/commands/tests/test_build_project_geojsons.py -q -p no:sugar
16 passed, 2 subtests passed

uv run --extra local pytest -q -p no:sugar
3808 passed, 156 skipped, 35 subtests passed

uv run --extra local ruff check speleodb/common/management/commands/build_project_geojsons.py speleodb/common/management/commands/tests/test_build_project_geojsons.py
All checks passed

uv run --extra local mypy speleodb/common/management/commands/build_project_geojsons.py
Success: no issues found

DJANGO_SETTINGS_MODULE=config.settings.test uv run --extra local python manage.py help build_project_geojsons
Passed; rendered the required mutually exclusive modes and all retained flags

git diff --check
Passed
```
