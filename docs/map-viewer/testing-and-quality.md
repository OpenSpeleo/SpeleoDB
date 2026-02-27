# Map Viewer: Testing and Quality Playbook

This document explains how agents should validate map viewer work before
considering a change complete.

## Core Commands (Run From Repo Root)

- Lint JavaScript:
  - `npm run lint:js`
- Run frontend unit tests:
  - `npm run test:js`
- Run backend tests:
  - `pytest`
- Combined local smoke:
  - `make test`

## Frontend Test Scope

Current map viewer tests (20 files, 484+ tests):

### Core modules
- `frontend_private/.../map_viewer/api.test.js` — API client methods, request config, error handling
- `frontend_private/.../map_viewer/config.permissions.test.js` — permission matrix, rank model, scope routing
- `frontend_private/.../map_viewer/config.loading.test.js` — project/network/GPS loading, caching, setPublicProjects
- `frontend_private/.../map_viewer/state.test.js` — state fields, init() reset behavior

### Map modules
- `frontend_private/.../map_viewer/map/depth.test.js` — depth domain merging
- `frontend_private/.../map_viewer/map/layers.depth_domain.test.js` — depth domain reactivity
- `frontend_private/.../map_viewer/map/geometry.test.js` — Haversine, snap points, snap indicator, snap radius

### Components
- `frontend_private/.../map_viewer/components/depth_legend.test.js` — legend rendering
- `frontend_private/.../map_viewer/components/context_menu.test.js` — menu rendering, icon caching, positioning
- `frontend_private/.../map_viewer/components/modal.test.js` — base HTML, open/close lifecycle
- `frontend_private/.../map_viewer/components/notification.test.js` — toast creation, auto-removal
- `frontend_private/.../map_viewer/components/project_panel.test.js` — panel init, toggle, sorting
- `frontend_private/.../map_viewer/components/upload.test.js` — progress bar, XHR upload lifecycle

### Entity managers
- `frontend_private/.../map_viewer/stations/manager.test.js` — CRUD, caching, cache invalidation
- `frontend_private/.../map_viewer/stations/tags.test.js` — tag loading, selection, color updates
- `frontend_private/.../map_viewer/stations/logs.test.js` — log rendering, access control, XSS safety
- `frontend_private/.../map_viewer/surface_stations/manager.test.js` — CRUD, network scoping
- `frontend_private/.../map_viewer/landmarks/manager.test.js` — CRUD, drag revert
- `frontend_private/.../map_viewer/exploration_leads/manager.test.js` — CRUD, project filtering

### Public viewer
- `frontend_public/static/js/gis_view_main.test.js` — initialization, zoom limits, error handling

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

## Tailwind/CSS Pipeline Checks

When frontend build scripts or tailwind configs change:

1. run
   - `npm run build:tailwind:public`
   - `npm run build:tailwind:private`
2. ensure no "No utility classes were detected" warnings
3. validate both output files are generated:
   - `frontend_public/static/css/style.css`
   - `frontend_private/static/private/css/style.css`

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

