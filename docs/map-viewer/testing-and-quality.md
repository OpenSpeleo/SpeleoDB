# Map Viewer: Testing and Quality Playbook

This document explains how agents should validate map viewer work before
considering a change complete.

## Core Commands (Existing Application Container Only)

- Lint JavaScript:
  - `docker exec -w /app speleodb_local_django bun run lint:frontend`
- Run frontend unit tests:
  - `docker exec -w /app speleodb_local_django bun run test:frontend`
- Run backend tests:
  - `docker exec -w /app speleodb_local_django pytest <targets>`
- Clean production build:
  - `docker exec -w /app speleodb_local_django bun run build`

Do not start another stack or run tests on the host. Run GitLab-backed tests
serially under the repository audit contract.

## Distance ruler verification

[Measurement](measurement.md) requires pure geometry/formatting tests, real
controller and DOM integration, native renderer lifecycle tests, and actual
browser evidence. Explicitly check touch tap deduplication, entity drag
suppression, editor opening races, source-menu Escape focus, style changes,
globe sky picking, label collision, and cleanup. Public initialization must
remain unchanged. Use the existing container Playwright setup; confirm the clean
build's manifest hash served by Django before screenshots.

## Frontend Test Scope

Representative map viewer coverage (use the runner's report for current totals):

### Core modules

- `frontend_private/.../map_viewer/api.test.ts` — API client methods, request
  config, error handling
- `frontend_private/.../map_viewer/config.permissions.test.ts` — permission
  matrix, rank model, scope routing
- `frontend_private/.../map_viewer/config.loading.test.ts` — project/network/GPS
  loading, caching, setPublicProjects
- `frontend_private/.../map_viewer/state.test.ts` — state fields, init() reset
  behavior

### Map modules

- `frontend_private/.../map_viewer/map/depth.test.ts` — depth domain merging
- `frontend_private/.../map_viewer/map/layers.depth_domain.test.ts` — depth
  domain reactivity
- `frontend_private/.../map_viewer/map/geometry.test.ts` — Haversine, snap
  points, snap indicator, snap radius

### Components

- `frontend_private/.../map_viewer/components/depth_legend.test.ts` — legend
  rendering
- `frontend_private/.../map_viewer/components/context_menu.test.ts` — menu
  rendering, icon caching, positioning
- `frontend_private/.../map_viewer/components/modal.test.ts` — base HTML,
  open/close lifecycle
- `frontend_private/.../map_viewer/components/notification.test.ts` — toast
  creation, auto-removal
- `frontend_private/.../map_viewer/components/project_panel.test.ts` — panel
  init, toggle, sorting
- `frontend_private/.../map_viewer/components/upload.test.ts` — progress bar,
  XHR upload lifecycle

### Entity managers

- `frontend_private/.../map_viewer/stations/manager.test.ts` — CRUD, caching,
  cache invalidation
- `frontend_private/.../map_viewer/stations/tags.test.ts` — tag loading,
  selection, color updates
- `frontend_private/.../map_viewer/stations/logs.test.ts` — log rendering,
  access control, XSS safety
- `frontend_private/.../map_viewer/surface_stations/manager.test.ts` — CRUD,
  network scoping
- `frontend_private/.../map_viewer/landmarks/manager.test.ts` — CRUD, drag
  revert
- `frontend_private/.../map_viewer/exploration_leads/manager.test.ts` — CRUD,
  project filtering

### Public viewer

- `frontend_public/static/ts/gis_view_main.test.ts` — initialization, zoom
  limits, error handling

## Feature-Level Validation Expectations

### Permissions

- matrix coverage for project/network levels
- scope routing via station metadata
- backward compatibility helpers stay aligned

### Depth coloring and scale

- domain merges from visible projects
- gauge labels follow domain changes
- all-hidden case shows `N/A`
- public/private entrypoint wiring remains valid

### Visibility behavior

- project toggle hides related project-scoped layers
- any domain or color-mode side effects remain synchronized
- global categories compose with country/project/network/item selections
- station subtype filters affect symbols and labels, including Sensor fallback
- delayed loads and refreshes preserve current display settings
- persistence/reset remains private; public controls keep their existing
  behavior

### Settings and modal flows

- four equal-width toolbar actions with readable mobile labels and green Import
  GPS
- native dialog focus, keyboard containment, dismissal, and browser persistence
- separate Managers menu, manager/details/Back handoff, and single manager
  launch
- Settings keyboard input never changes an active geometry draft
- fullscreen contains toolbar, import, managers, child dialogs, and
  notifications
- actual authenticated browser evidence at 320/390px, tablet, desktop,
  landscape, 200% zoom, and reduced motion; inspect bounds and focus as well as
  screenshots

See [Settings design](settings.md) for the complete behavioral contract.

## Vite/Tailwind Pipeline Checks

When frontend build scripts, registry entries, or Tailwind sources change:

1. run
   - `docker exec -w /app speleodb_local_django bun run build`
   - `docker exec -w /app speleodb_local_django bun run test:assets-watch`
2. ensure no "No utility classes were detected" warnings
3. validate `.vite/manifest.json`, `style-app`, the bootstrap, and all map
   controller entries are generated under
   `speleodb/common/static/speleodb/vite/`

## CI and Automation Context

- JS tests run in GitHub Actions (`js-tests` job in `ci.yml`).
- JS lint is enforced via pre-commit (`lint-map-viewer-js`).
- Browserslist DB refresh runs in a scheduled workflow:
  - `.github/workflows/update_browserslist_db.yml`

## Practical Agent Checklist

Before finalizing changes:

1. lint clean
2. tests clean
3. no duplicated logic introduced where centralized API exists
4. docs updated for architecture-impacting behavior
5. public/private parity confirmed for shared map features

## Boundary evidence

Use real API requests and database rows for authorization/mutation assertions,
real rendered Django templates for route contracts, and configured storage for
storage/rollback evidence. Pure frontend rendering should be directly callable
with its real helpers so capability and XSS checks do not replace the behavior
under test. A mocked HTTP failure is unit-level control-flow evidence; it does
not establish real transaction, transport, storage compensation, or browser
behavior. Use the real integration paths for those claims, following the shared
[GitLab test contract](../ci-gitlab-testing.md) where applicable.

### Viewer startup composition

`frontend_common/test/viewer-composition.test.ts` imports the real public and
private roots and their shared modules. Only external Mapbox and network
boundaries are simulated. These cases check startup before the Mapbox `load`
event: request overlap, source-control mounting, private measurement/control
registration, and separate public display persistence. Root-specific suites
exercise asynchronous loading and style-change callbacks. Browser verification
remains responsible for rendering, gesture timing, and performance budgets; the
startup fixture does not model Mapbox rendering.
