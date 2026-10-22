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

### Projection-crossing pan regressions

`tests/browser/viewer-gestures.spec.ts` runs against the actual private and
public Django viewers in Chromium and WebKit. It protects the screen-space
navigation contract: the geographic point grabbed by a pointer must follow that
pointer throughout a pan, including after zooming through the globe to Mercator
transition. A final center assertion alone can miss sideways motion or jumps
within a gesture.

The tests observe the existing `speleo:map-created` event and use public
MapLibre APIs to measure the grabbed point. The Django entrypoints, renderer
construction, workers and input handlers remain real. The shared browser fixture
supplies small, deterministic survey and provider-style HTTP responses; these
tests do not depend on the external basemap service, modify renderer methods, or
generate source-processing workloads. The Django browser wrapper supplies an
isolated database user and public GIS view.

The four scenarios run in both engines, for eight executions. Each entrypoint
has one wheel/pan scenario at the original regression latitude, 20.1 degrees,
with normal motion. Real wheel input crosses from zoom 12.3 into the transition
band, back above zoom 12, then into the transition band again. One horizontal
and one vertical pan follow each crossing without resetting the camera or its
input history. The return crossing uses opposite directions, covering all four
cardinal directions across the sequence. Each scenario has six pans and 72
sampled positions, rather than repeating the renderer's latitude/direction
matrix. Every 48-pixel pan keeps twelve intermediate observations and the one
CSS pixel axis limit, with unchanged bearing and pitch. Zoom is not fixed during
globe pans because latitude compensation is valid engine behavior.

Two touch scenarios pair the private viewer with normal motion and the public
viewer with reduced motion. Both entrypoints initialize the same `MapCore`
renderer and touch handlers, so this covers both motion policies without a
Cartesian product of identical handler paths. They pinch from zoom 12.3 into the
transition band, lift one finger, and wait for actual camera motion to finish
without a camera setter or new touch. The held finger's next 48-pixel drag must
move the geographic anchor along its twelve-step path with the same one-pixel
axis limit. Full release must allow camera motion to finish. The pause catches
MapLibre 6.14's partial-release inertia resetting a live contact; immediate
dragging alone can pass before the faulty cleanup runs. Engine-owned unit tests
cover the underlying corrections; these browser cases protect their integration
into the application's UI. See
[MapLibre integration](shared-packages.md#web-renderer-and-providers).

Named Playwright steps separate viewer startup, wheel crossings, sampled pans,
pinch and contact completion so timing reports can identify avoidable setup or
harness costs. JSON attachments retain the sampled paths. Broaden these
representative cases only when a distinct application regression justifies the
extra combinations.

Chromium receives trusted CDP touch input and waits for the matching DOM contact
event before paint observation. WebKit replays browser `TouchEvent` contact
lists because Playwright does not expose native multi-touch there; it verifies
engine contact handling but does not certify native iOS delivery. Neither path
uses fixed sleeps, retries, geometric tolerance expansion or private handler
mutation. Touch-path JSON attachments retain the before state and every sample.

The former duplicate source-load matrix and 24,000-feature revisions are absent
from UI/UX coverage. Source installation, asynchronous updates, cancellation and
retry contracts belong in the existing Vitest map-layer suites; provider
projection configuration is covered by `map/mapbox_provider.test.ts`. The
browser scenarios retain actual wheel, pointer and touch delivery because a
DOM-only test cannot establish the rendered camera's response. Their duration
includes real render frames and natural gesture completion. Investigate runs
over five seconds using measured step durations. Prefer fewer representative
scenarios to exhaustive renderer matrices while retaining the original failure
conditions, meaningful intermediate screen positions and actual native input.

Run this coverage through the existing application container, after building
assets, with PostgreSQL configured as described in
[`tests/browser/README.md`](../../tests/browser/README.md):

```bash
docker exec -e VIEWER_BROWSER_GREP='projection-crossing gestures|paused pinch handoff' \
  -w /app speleodb-monorepo-django \
  pytest tests/browser/test_django_browser.py --gitlab-audit-deny-create \
  -o faulthandler_timeout=1860
```

The normal browser CI job discovers these cases without a separate dispatcher.
They must run when MapLibre, shared camera setup, or viewer initialization
changes. Real desktop mouse/wheel automation does not certify hardware trackpad
momentum, and browser touch automation does not certify native
touchscreen/WebView behavior; those require device verification. The web viewer
uses MapLibre directly, so a passing web test does not establish correctness for
a React camera wrapper in another application.

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

1. run `docker exec -w /app speleodb-monorepo-django bun run build` and wait for
   success before refreshing the browser
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

Use pytest with real API requests and database rows for authorization/mutation
assertions, real rendered Django templates for route contracts, and configured
storage for storage/rollback evidence. Browser tests are exclusively UI/UX: use
small deterministic fixtures and controlled server responses to exercise the
real renderer, forms, native input, focus, loading feedback and error recovery.
Verify frontend logic with Vitest. Both lower layers run under `make test`. Pure
frontend rendering should be directly callable with its real helpers so
capability and XSS checks do not replace the behavior under test. A mocked HTTP
failure is unit-level control-flow evidence; it does not establish real
transaction, transport, storage compensation, or browser behavior. Use the real
integration paths for those claims, following the shared
[GitLab test contract](../ci-gitlab-testing.md) where applicable.

### Viewer startup composition

`frontend_common/test/viewer-composition.test.ts` imports the real public and
private roots and their shared modules. Only external MapLibre and network
boundaries are simulated. These cases check startup before the MapLibre `load`
event: request overlap, source-control mounting, private measurement/control
registration, and separate public display persistence. Root-specific suites
exercise asynchronous loading and style-change callbacks. Browser verification
remains responsible for actual rendering and native gestures; the startup
fixture does not model MapLibre rendering. Scale/latency benchmarks are outside
default UI/UX CI and require explicit authorization. See the
[browser testing boundary](../../tests/browser/README.md).

The composition renderer double implements the shared `GlobeAtmosphereMap`
contract, including style readiness, sky state, and custom-layer storage. Its
hydration cases dispatch `style.load` before `load` and after style replacement
to exercise real atmosphere installation and recreation for both viewer roots,
alongside survey-source restoration. GPU resource creation and visual appearance
remain browser responsibilities.
