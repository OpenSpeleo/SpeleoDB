# API v2 Coverage Backfill

Follow-up work scoped out of the initial v2 unwrap migration (see
`tasks/todos/api-v2-unwrap-migration_b57cfd8f.plan.md`). The migration
phase only fixed tests/templates/JS that were broken by the shape change;
it did not add missing coverage. This doc enumerates what is still
uncovered so the gaps can be closed in a dedicated pass.

## Goal

- Every `/api/v2/<endpoint>` has a Python test (pytest, using `reverse("api:v2:...")`).
- Every authenticated/public HTML template that issues an AJAX call has a
  co-located `*.test.js` covering at least the happy path and error path.

## Source of truth

URL names come from `speleodb/api/v2/urls/` (mounted in
`speleodb/api_router.py` under namespaces `api:v2` and `api:v2:gis-ogc`).

## Python endpoint gaps

Endpoints where **no** test under `speleodb/api/v2/tests/`,
`speleodb/common/tests/`, `speleodb/api/health/tests/`, or
`frontend_private/tests/` resolves the URL name (found via
`rg "api:v2:<name>"`):

- [ ] `api:v2:all-projects-geojson` — GET
- [ ] `api:v2:project-detail` — PUT, PATCH, DELETE (only GET is covered)
- [ ] `api:v2:project-user-permissions` — GET
- [ ] `api:v2:project-user-permissions-detail` — POST, PUT, DELETE
- [ ] `api:v2:project-team-permissions` — GET
- [ ] `api:v2:project-team-permissions-detail` — GET, POST, PUT, DELETE
- [ ] `api:v2:project-download-blob` — GET
- [ ] `api:v2:project-download-at-hash` — GET
- [ ] `api:v2:experiment-export-excel` — GET
- [ ] `api:v2:experiment-user-permissions` — GET, POST
- [ ] `api:v2:experiment-user-permissions-detail` — GET, PUT, DELETE
- [ ] `api:v2:experiment-records` (station-scoped) — GET, POST
- [ ] `api:v2:experiment-records-detail` — DELETE
- [ ] `api:v2:exploration-lead-all-geojson` — GET
- [ ] `api:v2:gis-ogc:experiment` — GET
- [ ] `api:v2:gps-tracks` — GET, POST
- [ ] `api:v2:gps-track-detail` — GET, PUT, PATCH, DELETE
- [ ] `api:v2:tool-dmp-doctor` — POST
- [ ] `api:v2:user-password-update` — PUT
- [ ] `api:v2:release-all-locks` — DELETE
- [ ] `api:v2:gis-views` — GET, POST
- [ ] `api:v2:gis-view-detail` — GET, PUT, PATCH, DELETE

Each backfilled test must:

1. Build via `BaseAPITestCase` / `BaseAPIProjectTestCase` or equivalent
   pytest fixtures in `speleodb/api/v2/tests/base_testcase.py`.
2. Cover authn/authz branches (no token, token but no permission, token
   with correct permission).
3. Assert the unwrapped v2 response shape (no `data`/`success`/`url`
   checks — those were removed during the migration).
4. Add a regression test for any 4xx/5xx failure mode the view documents
   (e.g. `tool-dmp-doctor` should exercise both good and malformed DMP
   payloads).

## Frontend AJAX coverage gaps

Templates under `frontend_private/templates/` that issue `$.ajax`,
`$.post`, `$.get`, or `fetch(...)` calls and currently have **no**
co-located `*.test.js` that asserts on the AJAX flow. Module-level
coverage of the underlying map viewer JS does **not** count as template
coverage for these forms.

### Project lifecycle
- [ ] `pages/project/new.html`
- [ ] `pages/project/details.html`
- [ ] `pages/project/danger_zone.html`
- [ ] `pages/project/upload.html`
- [ ] `pages/project/git_view.html`
- [ ] `pages/project/revision_history.html`
- [ ] `pages/project/mutex_history.html`
- [ ] `pages/project/user_permissions.html`
- [ ] `pages/project/team_permissions.html`

### Experiments
- [ ] `pages/experiment/new.html`
- [ ] `pages/experiment/details.html`
- [ ] `pages/experiment/data_viewer.html`
- [ ] `pages/experiment/user_permissions.html`
- [ ] `pages/experiment/danger_zone.html`

### Teams
- [ ] `pages/team/new.html`
- [ ] `pages/team/details.html`
- [ ] `pages/team/memberships.html`
- [ ] `pages/team/danger_zone.html`

### GIS views
- [ ] `pages/gis_view/new.html`
- [ ] `pages/gis_view/details.html`
- [ ] `pages/gis_view/danger_zone.html`

### Cylinder fleets
- [ ] `pages/cylinder_fleet/new.html`
- [ ] `pages/cylinder_fleet/details.html`
- [ ] `pages/cylinder_fleet/watchlist.html`
- [ ] `pages/cylinder_fleet/user_permissions.html`
- [ ] `pages/cylinder_fleet/danger_zone.html`

### Sensor fleets
- [ ] `pages/sensor_fleet/new.html`
- [ ] `pages/sensor_fleet/details.html`
- [ ] `pages/sensor_fleet/user_permissions.html`
- [ ] `pages/sensor_fleet/danger_zone.html`

### Surface networks
- [ ] `pages/surface_network/new.html`
- [ ] `pages/surface_network/details.html`
- [ ] `pages/surface_network/user_permissions.html`
- [ ] `pages/surface_network/danger_zone.html`

### Standalone pages
- [ ] `pages/station_tags.html`
- [ ] `pages/gps_tracks.html`
- [ ] `pages/user/password.html`
- [ ] `pages/user/preferences.html`
- [ ] `pages/user/feedback.html`

### Tools
- [ ] `pages/tools/xls2dmp.html`
- [ ] `pages/tools/xls2compass.html`
- [ ] `pages/tools/dmp2json.html`
- [ ] `pages/tools/dmp_doctor.html`

### Shared snippets
- [ ] `snippets/modal_data_import.html`
- [ ] `snippets/modal_gpx_import.html`

### Public auth pages
- [ ] `frontend_public/templates/auth/login.html`
- [ ] `frontend_public/templates/auth/signup.html`
- [ ] `frontend_public/templates/auth/password_reset.html`
- [ ] `frontend_public/templates/auth/password_reset_from_key.html`

Each new `*.test.js` should:

1. Mock `fetch` / `$.ajax` at the `globalThis` or module boundary.
2. Exercise the happy path (valid form submission, expected redirect /
   DOM update).
3. Exercise at least one error path (non-2xx response, validation error,
   network failure) and assert the user-visible surface (modal shown,
   notification, disabled button).
4. Never fall back to the legacy `{ data: ..., success: true }` mock
   envelope — the mock payload must match the v2 view's actual response
   shape.

## Suggested sequencing

1. Start with the highest-risk gaps: permissions endpoints
   (`project-user-permissions`, `project-team-permissions` variants,
   `experiment-user-permissions` variants) — these guard access control
   and are currently untested.
2. Then cover write endpoints that can silently corrupt state:
   `project-detail` PUT/PATCH/DELETE, `gps-tracks` writes,
   `release-all-locks`.
3. Finally cover read-only and export endpoints.
4. For the frontend, pair each backend testing wave with the templates
   that hit those endpoints so the JS mocks can be validated against
   real response shapes the new tests now lock in.
