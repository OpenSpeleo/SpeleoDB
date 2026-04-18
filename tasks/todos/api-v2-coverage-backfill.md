# API v2 Coverage Backfill

Living checklist for the follow-up work scoped out of the initial v2
unwrap migration. Tick items as they land.

## Status snapshot

**Python backend:** every permission, write, read, and export endpoint
flagged in the original backfill plan has coverage, including the
station-scoped `experiment-records` CRUD.

**Phase 2 (permission endpoints) — amended 2026-04-17:** The initial
Phase-2 tests were found (in the adversarial review recorded in
`tasks/lessons/phase2-permissions-review-followups.md`) to have material
gaps and two pinned bad contracts. The following remedial work has now
landed in the same branch:

- `ValueNotFoundError -> 404` for missing body fields has been replaced
  with `MissingFieldError -> 400`
  (`speleodb/utils/exceptions.py`), and the five permission views
  (`user_project_permission.py`, `user_experiment_permission.py`,
  `cylinder_fleet.py`, `sensor_fleet.py`, `surface_network.py`) have
  been migrated.
- The 10 unreachable inline "`if user == perm_data['user']: return 400`"
  self-target branches in the five permission views have been deleted.
  The sole guard now lives in `_process_request_data` (401).
- `TeamRequestWithProjectLevelSerializer.level` has been tightened to
  `choices_no_admin`, preventing the latent 500 that an `ADMIN`-level
  team POST previously triggered against the `TeamProjectPermission`
  `CheckConstraint`.
- The three Phase-2 test files have been rewritten to add
  `parameterized_class` matrix coverage over `(level, permission_type)`
  for each endpoint, plus negative tests for: missing-field, inactive
  target user, idempotent DELETE, soft-deleted perm 404, empty body,
  unknown team UUID, malformed UUID, team `level=ADMIN` rejection,
  invalid tokens, and anonymous POST/PUT/DELETE.
- Latent test flake from `UserFactory.django_get_or_create=["email"]` +
  Faker email collisions has been eliminated by passing explicit
  `uuid4`-suffixed emails via `_unique_email()`.

**Frontend refactor:** all 12 originally-planned shared modules have
landed. The only templates still inlining the legacy
`{% include 'snippets/ajax_error_modal_management.js' %}` block are the
5 unique templates that weren't part of any shared-pattern group
(listed at the bottom as a one-line follow-up).

## Goals

- Every `/api/v2/<endpoint>` has a Python test (pytest,
  `reverse("api:v2:...")`).
- Every authenticated / public HTML template that issues an AJAX call
  either (a) delegates to a shared-module helper or (b) has a
  co-located `*.test.js`.

## Python endpoint gaps

- [x] `api:v2:all-projects-geojson` -- `test_read_export_endpoints.py`
- [x] `api:v2:project-detail` PUT/PATCH/DELETE -- `test_project_detail_write.py`
- [x] `api:v2:project-user-permissions` (+ detail) -- `test_project_user_permissions.py`
- [x] `api:v2:project-team-permissions` (+ detail) -- `test_project_team_permissions.py`
- [x] `api:v2:project-download-blob` (authz) -- `test_read_export_endpoints.py`
- [x] `api:v2:project-download-at-hash` (authz) -- `test_read_export_endpoints.py`
- [x] `api:v2:experiment-export-excel` -- `test_read_export_endpoints.py`
- [x] `api:v2:experiment-user-permissions` (+ detail) -- `test_experiment_user_permissions.py`
- [x] `api:v2:experiment-records` + `experiment-records-detail` -- `test_experiment_records_api.py`
- [x] `api:v2:exploration-lead-all-geojson` -- `test_read_export_endpoints.py`
- [x] `api:v2:gis-ogc:experiment` -- `test_read_export_endpoints.py`
- [x] `api:v2:gps-tracks` + `gps-track-detail` -- `test_gps_track_api.py`
- [x] `api:v2:tool-dmp-doctor` -- `test_tool_dmp_doctor.py`
- [x] `api:v2:user-password-update` -- `test_user_password_and_locks.py`
- [x] `api:v2:release-all-locks` -- `test_user_password_and_locks.py`
- [x] `api:v2:gis-views` + `gis-view-detail` -- `test_gis_view_management_api.py`

### Phase 1 insurance regression tests

- [x] v1 wrap vs v2 raw shape contract -- `test_middleware_scope.py`
- [x] spectacular schema excludes `/v1/` + unique operationIds --
  `test_swagger.py`
- [x] autocomplete regression (`Array.isArray` guard, debounce, error) --
  `user_autocomplete.test.js`
- [x] dropped-assertion audit -- strengthened `test_auth_token.py`

## Frontend refactor (shared modules)

Each shared module replaces one or more inline `<script>` blocks in
Django templates. Full API reference in
[`docs/frontend-forms.md`](../../docs/frontend-forms.md).

- [x] `forms/ajax_errors.js` + test -- replaces the
  `snippets/ajax_error_modal_management.js` Django include
- [x] `forms/modals.js` + test -- `FormModals` namespace
- [x] `forms/danger_zone.js` + test -- **7** `*/danger_zone.html` templates
- [x] `forms/entity_crud_form.js` + test -- **10** CRUD templates
- [x] `forms/permission_modal.js` + test -- **5** user_permissions + `team/memberships.html`
  (via `selectors` + `fieldName='role'` options)
- [x] `forms/team_permission_modal.js` -- `project/team_permissions.html`
- [x] `forms/mutex_lock.js` -- `project/mutex_history.html`
- [x] `forms/auth_form.js` (at `frontend_public/static/js/auth_form.js`) -- **4** public auth templates
- [x] `forms/fleet_watchlist.js` -- both fleet watchlist pages
- [x] `forms/fleet_settings_form.js` -- both fleet details pages
- [x] `forms/fleet_entity_crud.js` -- all four cylinder / sensor fleet pages
  (shared cylinder/sensor modal helpers live in
  `templates/snippets/{cylinder,sensor}_modal_helpers.js`)
- [x] `forms/gis_view_form.js` -- `gis_view/new.html` + `gis_view/details.html`
- [x] `forms/tagged_entity_list.js` -- `station_tags.html` + `gps_tracks.html`
- [x] `forms/tool_file_upload.js` -- `tools/dmp2json.html` + `tools/dmp_doctor.html`
  (drop-zone only; each page owns its own success handler)
- [x] `forms/survey_table_tool.js` -- `tools/xls2dmp.html` + `tools/xls2compass.html`
  (table editing / paste / keyboard nav; each page owns its own submit + post-parse)

### Remaining inline-JS templates

The 5 templates below are non-duplicated single-purpose pages. They
still inline `{% include 'snippets/ajax_error_modal_management.js' %}`
but are functionally correct. Replace the include with
`<script src="forms/ajax_errors.js"></script>` + `showAjaxErrorModal(xhr)`
when next touching them.

- `pages/projects.html`
- `pages/project/upload.html`
- `pages/user/dashboard.html`
- `pages/experiment/new.html`
- `pages/experiment/details.html`

### Per-template wiring tests (optional)

Each shared module already has its own test suite. Per-template tests
are only useful when the template's inline glue is non-trivial. Worth
adding for:

- `pages/project/upload.html` (multipart upload + progress bar)
- `pages/project/git_view.html` (tree explorer)
- `pages/project/revision_history.html` (commit table + back-in-time)
- `pages/experiment/data_viewer.html` (ag-Grid + export)
- `pages/experiment/{new,details}.html` (`ExperimentFields` field builder)
- `tools/xls2compass.html` (team tags + Nominatim geocoding)
