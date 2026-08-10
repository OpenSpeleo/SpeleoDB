# GPS Track Sharing and GPX Export

## Implementation

- [x] Add the GPS Track active lifecycle and user-permission model migrations.
- [x] Backfill legacy owners with active ADMIN permissions.
- [x] Integrate GPS Tracks into centralized access checks and accessible
      querysets.
- [x] Add permission-management and GPX-export API routes.
- [x] Preserve owner provenance and create owner ADMIN permissions for new
      tracks.
- [x] Add permission-aware GPS Track list and access-control webpages.
- [x] Add responsive, XSS-safe frontend behavior and shared-track map loading.
- [x] Add model, migration, admin, API, frontend, and JavaScript tests.
- [x] Update GPS Track and affected architecture/API documentation.

## Verification

- [x] Ask the user to enter the devcontainer before running tests.
- [x] Run focused backend and frontend test targets.
- [x] Run the full Python and JavaScript test suites.
- [x] Run Python/JavaScript linting, strict typing, migrations, templates, URL,
      asset-build, and whitespace checks.

## Review / Results

GPS Tracks now use the same direct-user sharing architecture as the other
top-level collaborative entities. Existing owners were backfilled as ADMIN, new
imports create the owner permission atomically, shared tracks are loaded by the
existing map path, and deletion is a permission-preserving soft delete. READ
users can view and export, READ_AND_WRITE users can edit metadata, and ADMIN
users can share or delete.

The GPX export is a GPX 1.1 file generated from the stored GeoJSON with one
segment per line geometry, ordered coordinates, elevations when available,
SpeleoDB metadata, and explicit invalid-data responses. The GPS list retains the
product label “My GPS Tracks”. Its import success modal now says “Refreshing GPS
tracks...” instead of referring to map data.

Verification was performed inside the development container:

- Full Python suite: `3992 passed, 154 skipped`.
- Full JavaScript suite: `50 passed` files, `933 passed` tests.
- Focused final regressions: GPS page `10 passed`; GPX export `12 passed`;
  URL/schema `2 passed`.
- `npm run lint:js` and a clean `npm run build` passed.
- Ruff check and format validation passed for all 34 changed Python files.
- Mypy passed for all 34 changed Python files with no issues.
- Django migration drift, template validation, real migration application, API
  schema warnings, URL snapshot, and whitespace checks passed.
- Feature-test source audit found no monkeypatching or module mocks. The asset
  graph test also proves `*.test.js` files cannot enter production bundles.
