# AGENTS.md

Guidance for AI/code agents working in the SpeleoDB repository.

This file is intentionally opinionated and feature-focused so agents can make
correct changes without re-discovering architecture every session.

## Primary Goals

- Preserve product behavior while improving maintainability.
- Keep private/public map viewers behaviorally aligned where intended.
- Prevent regressions in performance-sensitive map features.
- Prefer centralized logic over duplicated conditionals or per-call custom checks.

## Repository Map

- `speleodb/`: Django backend code (APIs, models, permissions, tests).
- `frontend_private/`: authenticated/private UI assets and templates.
- `frontend_public/`: public UI assets and templates.
- `frontend_private/static/private/js/map_viewer/`: core map viewer modules.
- `frontend_public/static/js/gis_view_main.js`: public viewer entrypoint.
- `tailwind_css/static_src/`: Tailwind source styles and Tailwind configs.
- `docs/`: agent-focused design and implementation docs.

## JavaScript Workspace Contract

The repository now uses a single Node workspace at the repo root.

- Canonical Node manifests are:
  - `package.json`
  - `package-lock.json`
- Do not re-introduce nested `package.json` files for frontend tooling.
- Tailwind configs stay in `tailwind_css/static_src/src/**/tailwind.config.js`,
  but all scripts run from root.

### Root JS commands

- `npm run lint:js`
- `npm run test:js`
- `npm run build:tailwind:public`
- `npm run build:tailwind:private`
- `npm run build:esbuild:private`
- `npm run build:esbuild:public`

### Related system hooks

- Dev container/webserver bootstrap: `compose/start` (root npm commands).
- Railway predeploy: `railway.toml` (root npm commands).
- CI jobs: `.github/workflows/ci.yml` (root npm install + test/lint paths).
- Pre-commit hooks: `.pre-commit-config.yaml` (root npm scripts).

## Map Viewer Design Guardrails

## Shared code, two entrypoints

Most map viewer behavior is implemented in shared private modules and consumed by:

- private entrypoint: `frontend_private/static/private/js/map_viewer/main.js`
- public entrypoint: `frontend_public/static/js/gis_view_main.js`

When touching shared behavior, explicitly verify both entrypoints are still valid.

## Permission logic is centralized

Use `frontend_private/static/private/js/map_viewer/config.js` as the source of truth.

Preferred APIs:

- `Config.hasProjectAccess(projectId, action)`
- `Config.hasNetworkAccess(networkId, action)`
- `Config.hasScopedAccess(scopeType, scopeId, action)`
- `Config.getStationAccess(station)`

Actions are normalized as `read | write | delete`.
Do not add one-off permission branches in UI modules when central APIs can be used.

## Depth coloring must remain reactive and cached

Depth mode behavior uses per-project domain cache + merged active domain:

- Per-project domains stored in `State.projectDepthDomains`
- Active domain stored in `State.activeDepthDomain`
- Merge utility: `mergeDepthDomains(...)` in `map/depth.js`
- Layer repaint in depth mode uses active merged domain
- Legend behavior is centralized in `components/depth_legend.js`

Critical performance invariant:

- Project visibility toggles in depth mode should be `O(active projects)`,
  not `O(active features)`.

## Layer/source lifecycle discipline

When refreshing map data:

- Remove dependent layers first, then remove source.
- Reuse teardown helpers (for consistency and regression prevention).
- Avoid ad hoc `removeSource(...)` usage that skips dependent layers.

## Visibility behavior

Project visibility should affect:

- project survey layers
- project-scoped markers (for example leads and cylinder installs)
- depth-domain recomputation in depth mode

Avoid feature-specific visibility logic drift; prefer shared visibility utilities.

## Context menu icon behavior

Context menu icon rendering is cache-backed to avoid repeated network fetches.
Do not regress into rebuilding image URLs in ways that re-trigger network loads
on every menu open.

## Testing Requirements

For map viewer/frontend changes, validate both lint and tests:

- `npm run lint:js`
- `npm run test:js`

Key current test files:

- `frontend_private/static/private/js/map_viewer/config.permissions.test.js`
- `frontend_private/static/private/js/map_viewer/map/depth.test.js`
- `frontend_private/static/private/js/map_viewer/map/layers.depth_domain.test.js`
- `frontend_private/static/private/js/map_viewer/components/depth_legend.test.js`
- `frontend_public/static/js/gis_view_main.test.js`

Backend/API changes should also run relevant `pytest` targets.

## Documentation Expectations for Agents

When changing feature behavior or architecture, update docs under `docs/`
for the impacted topic:

- feature intent
- engineering scope and ownership boundaries
- testing and verification strategy
- performance implications

Do not only document "what changed"; include "why this architecture exists".

## Performance and Regression Checklist

Before finishing map viewer work, check:

1. No duplicated permission matrix logic was added.
2. Depth mode toggles still avoid per-feature rescans.
3. Public and private map viewers still initialize shared modules correctly.
4. Lint and tests pass from root.
5. Tailwind outputs still generate from root scripts.

## Practical Do/Do-Not

Do:

- Prefer shared utilities/modules over copy-paste.
- Keep behavior parity for public/private map flows when intended.
- Add focused tests when changing invariants.

Do not:

- Reintroduce nested Node toolchains.
- Bypass centralized permission APIs.
- Add expensive computations into frequent map interaction paths.
