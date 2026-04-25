# Landmark Collections

## Checklist

- [x] Show personal collections in My GIS Landmark Collections.
- [x] Hide personal collection sharing and danger-zone management while showing GIS integration.
- [x] Add model-backed Landmark Collection colors using the existing project color palette.
- [x] Expose collection colors through authenticated collection and Landmark GeoJSON APIs.
- [x] Add collection color pickers to shared Landmark Collection create/detail pages.
- [x] Group GIS Landmark manager rows by collection, collapsed by default.
- [x] Render Landmark map markers and labels with their collection color.
- [x] Make personal Landmark Collections white by default.
- [x] Expose GIS OGC endpoints for personal Landmark Collections.
- [x] Remove personal collection details editing form while keeping table and GIS OGC access.
- [x] Align shared Landmark Collection permission table and action controls with Project user permissions.
- [x] Match Project permission sorting: ADMIN first, then READ_AND_WRITE, then READ_ONLY.
- [x] Make Landmark Collection OGC discovery QGIS-compatible with `/collections` links and routes.
- [x] Add a user-scoped Landmark Collection OGC link using the existing application token.
- [x] Add user-scoped Landmark Collection OGC landing, conformance, collections, metadata, and items endpoints.
- [x] Render an All Landmark Collections GIS card on My GIS Landmark Collections.
- [x] Add backend/frontend tests for user-scoped Landmark Collection OGC access and listing UI.
- [x] Add an application-token refresh button and confirmation modal to the all-collections GIS card.
- [x] Tighten mypy annotations and remove stale Landmark ownership typing drift.
- [x] Add explicit drf-spectacular schemas for Landmark Collection Excel/GPX exports.
- [x] Add backend, frontend view, and JS coverage for visibility, color, grouping, and marker color behavior.
- [x] Update docs for personal collection management visibility and collection-driven marker colors.
- [x] Redesign Landmarks to be collection-first with one lazy personal collection per user.
- [x] Add Landmark `created_by`, collection type, personal owner, and database constraints.
- [x] Add a central personal collection helper and use it from Landmark list/create/import paths.
- [x] Backfill existing unassigned Landmarks into personal collections in migration logic.
- [x] Remove Landmark access behavior that treats `Landmark.user` as ownership.
- [x] Remove the legacy `Landmark.user` FK and update all Landmark code/tests to use `created_by` plus collection permission.
- [x] Hide personal collections from shared collection management pages while exposing them to map selectors.
- [x] Update imports, exports, OGC, and table code to use `created_by` provenance.
- [x] Add backend model/API/import/export tests for personal collection creation and access.
- [x] Add frontend/JS tests for selector defaults and personal/shared collection labels.
- [x] Update docs and lessons for the collection-first ownership model.
- [x] Add backend models, migration, admin registration, and model tests.
- [x] Add permission-aware Landmark Collection serializers, API views, URLs, and tests.
- [x] Update existing Landmark CRUD/GeoJSON/import APIs for optional collections and tests.
- [x] Add Landmark Collection OGC endpoints and tests.
- [x] Add private UI pages, routes, sidebar entry, and frontend view tests.
- [x] Extend map viewer landmark API/client/manager/UI for collection assignment and read-only guards.
- [x] Update docs for feature intent, API surface, map-viewer behavior, and permissions.
- [x] Run JS lint/tests/build and focused Django tests where possible.
- [x] Add collection Landmark table to the private details page.
- [x] Add Excel and GPX export endpoints for collection Landmarks.
- [x] Add backend/frontend tests for Landmark table and exports.
- [x] Update Landmark Collection docs and verification notes for table/export work.

## Review / Results

Implemented `LandmarkCollection` as the permissioned ownership boundary for
all Landmarks. Private Landmarks now live in each user's lazily-created
personal collection; shared Landmarks live in normal shared collections.

Key implementation results:

- Added `LandmarkCollection` and `LandmarkCollectionUserPermission` models,
  admin registration, migration, factories, and focused model coverage.
- Added `Landmark.created_by`, `LandmarkCollection.collection_type`, and
  `LandmarkCollection.personal_owner`. Personal collections are constrained to
  one per user; shared collections cannot have a personal owner.
- Added `get_or_create_personal_landmark_collection(user)` and use it from
  Landmark create/list/import paths. Missing or null collection assignment now
  resolves to the caller's personal collection at authenticated entrypoints.
- Extended `BaseAccessLevel` and Landmark query paths so all Landmark access
  delegates to collection permissions.
- Removed the legacy `Landmark.user` FK after migration backfill. `created_by`
  is the only Landmark creator/provenance field, and the collection FK is the
  only access boundary.
- Made the `0037` rollback path explicit: rollback re-adds the old user column
  as nullable, restores `user_id` from personal ownership or collection
  permissions, collapses rows the old per-user coordinate constraint cannot
  represent, and then restores the old non-null schema.
- Replaced user-scoped coordinate uniqueness with collection-scoped coordinate
  uniqueness.
- Changed physical collection deletion to cascade member Landmarks instead of
  nulling `collection_id`; soft deletion remains the product path and keeps
  member Landmarks attached to the inactive, invisible collection.
- Added authenticated CRUD and permission APIs for Landmark Collections,
  including creator ADMIN grants, active-only listing, soft delete that hides
  member Landmarks without unassigning them, permission grant/update/revoke/
  reactivate, self-target guards, and inactive-user guards.
- Updated Landmark serializers/endpoints and GPX/KML imports to accept optional
  collection assignment. Missing collection imports go to the personal
  collection; explicit shared collection imports require WRITE access. Import
  de-duplication now scopes by collection and coordinates.
- Added public OGC endpoints for active collection GIS tokens, including
  personal and shared collections, with dynamic Point GeoJSON, ETag/304
  support, `application/geo+json`, and short public cache headers.
- Added private Landmark Collection listing/new/details/permissions/GIS/danger
  pages, sidebar navigation, and view/url tests. Shared collection management
  pages hide personal collections and redirect direct personal collection URLs.
- Extended the map viewer and import modal to hydrate collections, group/show
  labels, include collection selectors in create/edit/import flows, and block
  edit/delete/drag affordances for read-only collection Landmarks.
- Added a Sensor Fleet-style details-page Landmark table with name,
  longitude, latitude, map Go To link, creator email, DataTables sorting, and
  empty-state behavior.
- Added READ-permission Excel and GPX exports for collection Landmarks, using
  the shared collection Landmark queryset and existing `xlsxwriter`/`gpxpy`
  dependencies. Exports carry data only; the UI-only map Go To action is not
  included. GPX exports use GPX 1.1 namespace/schema metadata and
  `creator="SpeleoDB"`.
- Added `LandmarkCollection.color`, matching the existing project/GPS track
  color palette and validation pattern. Collection APIs now normalize colors
  and Landmark GeoJSON exposes `collection_color`.
- Personal collections now appear in My GIS Landmark Collections and open the
  details/table/export and GIS integration pages. Permission and danger-zone
  pages are hidden and redirect for personal collections; API permission
  management and deletion remain blocked.
- Shared WRITE users can update collection color with name/description.
  Personal collection details no longer expose name, description, or color
  editing; the page keeps only the Landmark table and export actions, with OGC
  access on the GIS integration tab.
- Shared Landmark Collection permission pages now mirror Project user
  permission pages for responsive cards, desktop table structure, Grant Access
  button states, modal chrome, permission pills, and icon-only edit/delete
  actions. Ordering now matches Project permissions: ADMIN first, then
  READ_AND_WRITE, then READ_ONLY, with email as the tie-breaker. Landmark
  Collections still use no-WEB_VIEWER permission choices.
- Landmark Collection OGC now exposes the landing page as the user-facing GIS
  URL and advertises standards-shaped `/collections`,
  `/collections/landmarks`, and `/collections/landmarks/items` links for QGIS.
  The older bare-token URLs remain available as compatibility aliases.
- Added a user-scoped Landmark Collection OGC service at
  `/api/v2/gis-ogc/landmark-collections/user/<user_token>/`. It reuses the
  application token, lists all active personal and shared collections the token
  owner can READ, uses collection UUIDs as OGC collection ids, and returns
  collection-scoped Point GeoJSON from each `/items` endpoint.
- Added an **All Landmark Collections GIS** card to **My GIS Landmark
  Collections**, mirroring the Personal GIS View copy-card pattern and warning
  that the URL grants read access to all currently accessible Landmark
  Collections.
- Added application-token refresh from the **All Landmark Collections GIS**
  card with a confirmation modal explaining that Ariane, Compass, mobile apps,
  GIS integrations, API scripts, and other connected apps will stop
  authenticating until updated with the new token.
- Fixed mypy issues from the collection-first redesign by removing the stale
  `Landmark.user` permission check, narrowing redirect response types in view
  tests, typing the OGC streaming-response helper with a protocol/cast at the
  framework boundary, correcting admin anonymous-user narrowing, and typing the
  factory-boy collection descriptor instead of suppressing it.
- Added explicit binary OpenAPI response schemas and serializer classes for the
  Landmark Collection Excel and GPX export views so schema generation remains
  warning/error-free.
- The GIS Landmark manager now groups Landmarks by collection, with all groups
  collapsed by default. Group headers show the collection color, count, access
  state, and personal/private label.
- Landmark marker and label paint now use each feature's `collection_color`
  with the standard map fallback color when missing.
- Personal Landmark Collections default to white (`#ffffff`) through the lazy
  helper and migration backfill. White markers use a dark halo/outline so they
  remain visible on the map and in the manager.
- Added `docs/landmark-collections.md` and updated map-viewer API, feature,
  data-flow, and permissions docs.

Verification completed:

- `uv run --extra local ruff check ...changed Python files...`
- `python3 -m py_compile ...changed Python files...`
- `uv run --extra local python manage.py makemigrations gis --check --dry-run --settings=config.settings.test --skip-checks`
  - Result: no changes detected in app `gis`.
- `uv run --extra local pytest speleodb/gis/tests/test_landmark_model.py speleodb/gis/tests/test_landmark_collection_model.py speleodb/api/v2/tests/test_landmark_serializers.py speleodb/api/v2/tests/test_landmark_endpoints.py speleodb/api/v2/tests/test_landmark_collection_api.py speleodb/api/v2/tests/test_landmark_collection_ogc.py frontend_private/tests/test_views.py::LandmarkCollectionViewsTest`
  - Result: 103 passed.
- `uv run --extra local pytest speleodb/api/v2/tests/test_user_dashboard_stats.py speleodb/users/tests/test_admin.py`
  - Result: 129 passed, 2 skipped.
- `uv run --extra local pytest speleodb/gis/tests/test_landmark_collection_model.py speleodb/api/v2/tests/test_landmark_collection_api.py speleodb/api/v2/tests/test_landmark_endpoints.py speleodb/api/v2/tests/test_landmark_serializers.py speleodb/api/v2/tests/test_landmark_collection_ogc.py`
  - Result: 74 passed.
- `uv run --extra local pytest speleodb/gis/tests/test_landmark_collection_model.py speleodb/api/v2/tests/test_landmark_collection_api.py speleodb/api/v2/tests/test_landmark_collection_ogc.py speleodb/api/v2/tests/test_landmark_serializers.py speleodb/api/v2/tests/test_landmark_endpoints.py frontend_private/tests/test_urls.py frontend_private/tests/test_views.py`
  - Result: 180 passed.
- `uv run --extra local pytest speleodb/api/v2/tests/test_landmark_collection_api.py frontend_private/tests/test_views.py frontend_private/tests/test_urls.py speleodb/common/tests/test_urls.py`
  - Result: 150 passed.
- `uv run --extra local pytest speleodb/gis/tests/test_landmark_collection_migration.py speleodb/gis/tests/test_landmark_model.py speleodb/gis/tests/test_landmark_collection_model.py speleodb/api/v2/tests/test_landmark_serializers.py speleodb/api/v2/tests/test_landmark_endpoints.py speleodb/api/v2/tests/test_landmark_collection_api.py speleodb/api/v2/tests/test_landmark_collection_ogc.py speleodb/api/v2/tests/test_user_dashboard_stats.py speleodb/users/tests/test_admin.py frontend_private/tests/test_views.py::LandmarkCollectionViewsTest`
  - Result after removing `Landmark.user` and fixing rollback: 233 passed, 2 skipped.
- `uv run --extra local pytest speleodb/api/v2/tests/test_landmark_collection_api.py::TestLandmarkCollectionLandmarkExports::test_gpx_export_contains_collection_waypoints_only speleodb/api/v2/tests/test_landmark_collection_api.py::TestLandmarkCollectionLandmarkExports::test_empty_gpx_export_is_valid_gpx`
  - Result: 2 passed.
- `npm run test:js`
  - Result before color/grouping work: 37 test files, 835 tests passed.
- `npm run test:js`
  - Result after color/grouping work: 38 test files, 839 tests passed.
- `npm run lint:js`
- `npm run build:esbuild:private`
- `uv run --extra local ruff check ...changed Python files...`
  - Result after color/grouping work: all checks passed.
- `uv run --extra local python manage.py makemigrations gis --check --dry-run --settings=config.settings.test --skip-checks`
  - Result after color/grouping work: no changes detected in app `gis`.
- `uv run --extra local pytest speleodb/gis/tests/test_landmark_collection_model.py speleodb/gis/tests/test_landmark_collection_migration.py speleodb/api/v2/tests/test_landmark_serializers.py speleodb/api/v2/tests/test_landmark_collection_api.py frontend_private/tests/test_views.py::LandmarkCollectionViewsTest`
  - Result after color/grouping work: 70 passed.
- `uv run --extra local pytest speleodb/gis/tests/test_landmark_collection_model.py speleodb/gis/tests/test_landmark_collection_migration.py speleodb/api/v2/tests/test_landmark_collection_api.py`
  - Result after personal-white default: 45 passed.
- `npm run test:js -- --run frontend_private/static/private/js/map_viewer/map/layers.landmarks.test.js frontend_private/static/private/js/map_viewer/landmarks/ui.test.js`
  - Result after personal-white default: 2 test files, 9 tests passed.
- `uv run --extra local pytest speleodb/api/v2/tests/test_landmark_collection_ogc.py speleodb/api/v2/tests/test_landmark_collection_api.py frontend_private/tests/test_views.py::LandmarkCollectionViewsTest`
  - Result after exposing personal collection OGC endpoints: 54 passed.
- `uv run --extra local ruff check speleodb/api/v2/serializers/landmark_collection.py speleodb/api/v2/views/landmark_collection_ogc.py frontend_private/views/landmark_collections.py speleodb/api/v2/tests/test_landmark_collection_api.py speleodb/api/v2/tests/test_landmark_collection_ogc.py frontend_private/tests/test_views.py`
  - Result after exposing personal collection OGC endpoints: all checks passed.
- `uv run --extra local python manage.py makemigrations gis --check --dry-run --settings=config.settings.test --skip-checks`
  - Result after exposing personal collection OGC endpoints: no changes detected in app `gis`.
- `git diff --check`
  - Result after exposing personal collection OGC endpoints: clean.
- `uv run --extra local pytest frontend_private/tests/test_views.py::LandmarkCollectionViewsTest`
  - Result after removing personal collection details editing form: 16 passed.
- `uv run --extra local ruff check frontend_private/tests/test_views.py`
  - Result after removing personal collection details editing form: all checks passed.
- `git diff --check`
  - Result after removing personal collection details editing form: clean.
- `uv run --extra local pytest frontend_private/tests/test_views.py::LandmarkCollectionViewsTest`
  - Result after aligning permission table/actions with Project design: 17 passed.
- `uv run --extra local ruff check speleodb/surveys/templatetags/permission_levels.py frontend_private/tests/test_views.py`
  - Result after aligning permission table/actions with Project design: all checks passed.
- `uv run --extra local pytest frontend_private/tests/test_views.py::LandmarkCollectionViewsTest speleodb/api/v2/tests/test_landmark_collection_api.py::TestLandmarkCollectionAPI::test_permission_list_matches_project_sorting`
  - Result after matching Project permission sorting: 19 passed.
- `uv run --extra local ruff check frontend_private/views/landmark_collections.py speleodb/api/v2/views/landmark_collection.py frontend_private/tests/test_views.py speleodb/api/v2/tests/test_landmark_collection_api.py`
  - Result after matching Project permission sorting: all checks passed.
- `uv run --extra local pytest speleodb/api/v2/tests/test_landmark_collection_ogc.py frontend_private/tests/test_views.py::LandmarkCollectionViewsTest speleodb/common/tests/test_urls.py`
  - Result after making Landmark OGC discovery QGIS-compatible: 24 passed.
- `uv run --extra local ruff check speleodb/api/v2/views/landmark_collection_ogc.py speleodb/api/v2/urls/gis.py speleodb/api/v2/tests/test_landmark_collection_ogc.py frontend_private/tests/test_views.py`
  - Result after making Landmark OGC discovery QGIS-compatible: all checks passed.
- `git diff --check`
  - Result after making Landmark OGC discovery QGIS-compatible: clean.
- `uv run --extra local pytest speleodb/api/v2/tests/test_landmark_collection_ogc.py frontend_private/tests/test_views.py::LandmarkCollectionViewsTest speleodb/common/tests/test_urls.py`
  - Result after adding user-scoped Landmark Collection OGC: 34 passed.
- `uv run --extra local ruff check speleodb/api/v2/landmark_access.py speleodb/api/v2/views/landmark_collection_ogc.py speleodb/api/v2/urls/gis.py frontend_private/views/landmark_collections.py speleodb/api/v2/tests/test_landmark_collection_ogc.py frontend_private/tests/test_views.py`
  - Result after adding user-scoped Landmark Collection OGC: all checks passed.
- `npm run test:js`
  - Result after adding user-scoped Landmark Collection OGC: 38 test files, 839 tests passed.
- `npm run lint:js`
  - Result after adding user-scoped Landmark Collection OGC: passed.
- `git diff --check`
  - Result after adding user-scoped Landmark Collection OGC: clean.
- `uv run --extra local pytest frontend_private/tests/test_views.py::LandmarkCollectionViewsTest`
  - Result after adding application-token refresh modal: 21 passed.
- `uv run --extra local pytest speleodb/api/v2/tests/test_landmark_collection_ogc.py frontend_private/tests/test_views.py::LandmarkCollectionViewsTest speleodb/common/tests/test_urls.py`
  - Result after adding application-token refresh modal: 35 passed.
- `uv run --extra local ruff check frontend_private/views/landmark_collections.py frontend_private/tests/test_views.py`
  - Result after adding application-token refresh modal: all checks passed.
- `npm run test:js`
  - Result after adding application-token refresh modal: 38 test files, 839 tests passed.
- `npm run lint:js`
  - Result after adding application-token refresh modal: passed.
- `git diff --check`
  - Result after adding application-token refresh modal: clean.
- `uv run --extra local dmypy run -- --config-file pyproject.toml .`
  - Result after typing cleanup: success, no issues in 581 source files.
- `uv run --extra local ruff check speleodb/api/v2/permissions.py speleodb/gis/admin/landmark.py speleodb/api/v2/tests/factories.py speleodb/api/v2/tests/test_landmark_collection_ogc.py frontend_private/tests/test_views.py`
  - Result after typing cleanup: all checks passed.
- `uv run --extra local pytest speleodb/api/v2/tests/test_landmark_collection_ogc.py frontend_private/tests/test_views.py::LandmarkCollectionViewsTest speleodb/gis/tests/test_landmark_model.py speleodb/gis/tests/test_landmark_collection_model.py`
  - Result after typing cleanup: 54 passed.
- `git diff --check`
  - Result after typing cleanup: clean.
- `uv run --extra local pytest speleodb/users/tests/test_swagger.py::test_api_schema_no_warnings`
  - Result after export schema fix: 1 passed.
- `uv run --extra local pytest speleodb/api/v2/tests/test_landmark_collection_api.py::TestLandmarkCollectionLandmarkExports speleodb/users/tests/test_swagger.py`
  - Result after export schema fix: 22 passed.
- `uv run --extra local ruff check speleodb/api/v2/views/landmark_collection.py`
  - Result after export schema fix: all checks passed.
- `uv run --extra local dmypy run -- --config-file pyproject.toml .`
  - Result after export schema fix: success, no issues in 581 source files.

## Adversarial Review Fixes - 2026-04-25

Review pass found real contract bugs, not cosmetic churn:

- [x] Added `collection_color` to normal Landmark serializer responses, not
  just GeoJSON, and asserted it in serializer coverage.
- [x] Made `LandmarkCollection.is_active` read-only through public create/update
  APIs: creates force active rows, update attempts are rejected, and soft delete
  remains the only normal API path that deactivates a collection.
- [x] Removed `is_active` from public Landmark Collection and collection
  permission serializers; active rows are filtered server-side instead of
  advertising lifecycle state.
- [x] Made inactive collection object/export/permission/member Landmark routes
  resolve as 404, while active no-permission authenticated failures remain 403.
- [x] Changed permission `PUT` to target only active permission rows so revoked
  rows cannot be silently edited back into shape; reactivation stays on `POST`.
- [x] Wrapped Landmark create/update saves in transaction savepoints before
  catching duplicate-coordinate `IntegrityError`, preventing broken Django test
  transactions and real request transaction poisoning.
- [x] Wrapped GPX/KML Landmark creation in transactions so failed imports do not
  leave partial Landmark rows after validation/parsing succeeds.
- [x] Fixed public collection OGC `/collections?f=json` child link generation
  so query parameters do not corrupt metadata or items URLs.
- [x] Fixed bad comma-exception handling in Landmark Collection private views
  and the collection permission helper.
- [x] Removed read-only Landmark edit/delete affordances from the details modal
  and right-click menu, and made drag/move require known `can_write === true`.
- [x] Added Git integrations to the application-token refresh warning.
- [x] Added focused tests for all of the above, including JS drag gating and
  read-only detail controls.

Verification after review fixes:

- `uv run --extra local dmypy run -- --config-file pyproject.toml .`
  - Result: success, no issues in 581 source files.
- `uv run --extra local ruff check ...touched Python files...`
  - Result: all checks passed.
- `uv run --extra local ruff check`
  - Result: blocked by pre-existing unrelated `bin/squash_dependencies.py`
    lint debt; no Landmark Collection review files reported.
- `uv run --extra local pytest speleodb/users/tests/test_swagger.py -q`
  - Result: 8 passed.
- `uv run --extra local pytest speleodb/gis/tests/test_landmark_model.py speleodb/gis/tests/test_landmark_collection_model.py speleodb/gis/tests/test_landmark_collection_migration.py -q`
  - Result: 21 passed.
- `uv run --extra local pytest speleodb/api/v2/tests/test_landmark_serializers.py speleodb/api/v2/tests/test_landmark_endpoints.py speleodb/api/v2/tests/test_landmark_collection_api.py speleodb/api/v2/tests/test_landmark_collection_ogc.py -q`
  - Result: 95 passed.
- `uv run --extra local pytest speleodb/api/v2/tests/test_landmark_collection_api.py speleodb/api/v2/tests/test_landmark_serializers.py speleodb/api/v2/tests/test_landmark_collection_ogc.py -q`
  - Result after removing `is_active` from public payloads: 66 passed.
- `uv run --extra local ruff check speleodb/api/v2/serializers/landmark_collection.py speleodb/api/v2/tests/test_landmark_collection_api.py`
  - Result after removing `is_active` from public payloads: all checks passed.
- `uv run --extra local pytest frontend_private/tests/test_urls.py frontend_private/tests/test_views.py -q`
  - Result: 139 passed.
- `npm run test:js`
  - Result: 39 files, 843 tests passed.
- `npm run lint:js`
  - Result: passed.
- `npm run build:esbuild:private`
  - Result: passed after `npm install` repaired missing Rollup optional
    dependency and `npm rebuild esbuild` replaced a stale Linux esbuild binary
    in local `node_modules`.
- `git diff --check` and `git diff --check --cached`
  - Result: clean.
- `npm run test:js`
  - Result after aligning permission table/actions with Project design: 38 test files, 839 tests passed.
- `npm run lint:js`
  - Result after aligning permission table/actions with Project design: passed.
- `git diff --check`
  - Result after aligning permission table/actions with Project design: clean.
- `npm run test:js`
  - Result after removing personal collection details editing form: 38 test files, 839 tests passed.
- `npm run lint:js`
  - Result after removing personal collection details editing form: passed.
- `npm run lint:js`
  - Result after personal-white default: passed.
- `uv run --extra local python manage.py makemigrations gis --check --dry-run --settings=config.settings.test --skip-checks`
  - Result after personal-white default: no changes detected in app `gis`.
- `git diff --check`
- Prior Docker-side Python tests run by the user before the table/export
  addition
  - Result: passed.

Known verification limits:

- `uv run --extra local python manage.py check` is blocked locally by missing
  `DATABASE_URL`.
- `uv run --extra local python manage.py makemigrations --check --dry-run --settings=config.settings.test`
  is blocked by an existing `corsheaders.E014` test-settings value with a path
  in `CORS_ALLOWED_ORIGINS`.
- Local full-suite `uv run --extra local pytest` previously timed out after 600
  seconds in the non-Docker environment, but Docker-side Python verification
  passed.
- Docker-side rerun for the new table/export tests is still pending.
