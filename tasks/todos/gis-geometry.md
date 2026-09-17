# GIS Geometry

Approved implementation plan: one private LineString or simple Polygon per named
record, direct-user sharing, model-driven color, editable GeoJSON, 100 editable
vertices, and a strict 30 km² bounding-box limit (>8 km² warning). The revised
user contract removes Point support and requires one canonical JS/Python
constants source with a cross-language consistency test.

- [x] Models, migrations, shared validation, permission-aware API, admin, tests.
- [x] Reused private listing/settings/sharing UI and advanced GeoJSON editing.
- [x] Lazy default-hidden map overlays and private-only initialization.
- [x] Mouse/GPS editor, draft isolation, Undo/Redo, Save/Revert, conflict
      handling.
- [x] Interaction ownership, responsive/accessible UI, visual review/refinement.
- [x] Documentation of intent, interfaces, limits, performance, and testing.
- [x] Container-only tests, lint/types, migrations, clean assets, browser
      checks.
- [x] Record review results and remaining limitations in tasks/todo.md.

## Contract

GeoJSON is a bare 2D Geometry object. Polygon holes, multipart geometries and
antimeridian-crossing segments are unsupported. Polygon closure does not count
toward the vertex limit. Compute unrounded spherical latitude/longitude bounding
rectangle area using radius 6371008.8 m; never trust supplied bounds. Server and
browser enforce the same contract. All metadata/geometry updates are atomic and
require expected_revision; stale writes return 409. Creator receives ADMIN on
creation; active permission rows alone authorize subsequent access.

Management mirrors GIS Layers using existing templates/controllers. Drawing is
private-only, uses the existing API/Config/State/Layers/Interactions ownership,
and keeps an isolated draft until Save. Stored shapes start hidden each session;
successful saves reveal the result. Revert restores previous visibility. GPS
fields flush before Save. No additional drawing dependency or overlay runtime.

## Verification

All checks run in the existing speleodb_local_django container at /app. Geometry
tests allocate no GitLab projects. Include permission/revision/validation tests,
shared JS/Python area fixtures, draft command and interaction regression tests,
full JS/Python suites, lint/types, migration checks, clean build, and desktop /
mobile browser evidence. Preserve GIS Layers, GPS Tracks, and public viewer.

## Results

The full JavaScript suite passes 1,155 tests across 72 files, including both map
entrypoints and the shared contract consistency tests. All pre-commit checks
pass across tracked and new files, including Ruff, mypy, templates, JavaScript,
dependency/security checks, URL consistency, and a clean production Vite build.
Both migrations are applied locally and the migration drift check is clean.

Focused backend regression coverage passes 102 tests and three subtests. Twelve
additional tests and three subtests also pass against PostgreSQL, exercising the
actual row-locking behavior. These focused runs created no GitLab projects.

The full Python run finished with 4,863 passing and 178 skipped tests. Its one
failure exposed a native Node JSON import attribute requirement; adding the
attribute fixed it. The final PostgreSQL run passed 67 tests and three subtests,
including that integration, geometry/API/admin, shared GIS Layer permissions,
and soft-deletion timestamps. The final private-page run passed ten tests.

Full-run GitLab audit `94b39f43d58f4d48b9642699cc6ca2c4` recorded nine
creations, ten creation POSTs, zero violations, and no unresolved outcomes. All
nine repositories have verified deletion marks. Final focused runs created none.

Real Chromium/Mapbox checks passed GPS line creation and editing, mouse polygon
creation, default-hidden visibility, Revert, oversized/Point API rejection,
orange/red feedback, advanced GeoJSON validation and saving, complete bounding
box framing outside the inspector, mobile sheet placement, fullscreen, and no
runtime errors. Browser evidence is under `.artifacts/gis-geometry/`.

The final user refinements put creation beside Import GPS, match existing panel
chevrons, and fit shapes into the visible unobstructed map. Native vertex drag,
real revision-conflict recovery, mobile touch drawing/saving, fullscreen, and
the served asset manifest passed additional browser checks. All seven toolbar
controls and labels are visible: one row at 1440px, three rows at 390px and
320px, with no horizontal overflow and at least 44px mobile touch targets.

No unresolved feature defects remain from verification. Supported geographic
limits and intentionally unsupported geometry types are documented in the
feature guide. Temporary browser QA records and the QA account are removed.
