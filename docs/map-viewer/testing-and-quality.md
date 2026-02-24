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

Current map viewer tests include:

- `frontend_private/static/private/js/map_viewer/config.permissions.test.js`
- `frontend_private/static/private/js/map_viewer/map/depth.test.js`
- `frontend_private/static/private/js/map_viewer/map/layers.depth_domain.test.js`
- `frontend_private/static/private/js/map_viewer/components/depth_legend.test.js`
- `frontend_public/static/js/gis_view_main.test.js`

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

