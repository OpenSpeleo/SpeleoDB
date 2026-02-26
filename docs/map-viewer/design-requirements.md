# Map Viewer: Feature Design Requirements

This document captures the map viewer design requirements that should be treated
as feature contracts, not implementation suggestions.

## Scope and ownership boundaries

Most map viewer behavior is implemented in shared private modules and consumed
by both entrypoints:

- private entrypoint: `frontend_private/static/private/js/map_viewer/main.js`
- public entrypoint: `frontend_public/static/js/gis_view_main.js`

When touching shared behavior, keep private/public behavior aligned where
intended and verify both entrypoints still initialize correctly.

## Permission logic is centralized

Use `frontend_private/static/private/js/map_viewer/config.js` as the source of
truth.

Preferred APIs:

- `Config.hasProjectAccess(projectId, action)`
- `Config.hasNetworkAccess(networkId, action)`
- `Config.hasScopedAccess(scopeType, scopeId, action)`
- `Config.getStationAccess(station)`

Actions are normalized as `read | write | delete`.

Do not add one-off permission branches in UI modules when central APIs can be
used.

For expanded semantics and test coverage, see:

- `docs/map-viewer/permissions-and-access.md`

## Depth coloring must stay reactive and cached

Depth mode uses per-project domain cache + merged active domain:

- per-project domains are stored in `State.projectDepthDomains`
- active merged domain is stored in `State.activeDepthDomain`
- domains are merged via `mergeDepthDomains(...)` in `map/depth.js`
- depth line repaint uses active merged domain
- legend behavior is centralized in `components/depth_legend.js`

Critical performance invariant:

- project visibility toggles in depth mode should be `O(active projects)`, not
  `O(active features)`

For architecture details and behavior examples, see:

- `docs/map-viewer/depth-domain-reactivity.md`
- `docs/map-viewer/map_viewer_depth_coloring.md`

## Layer/source lifecycle discipline

When refreshing map data:

- remove dependent layers first, then remove source
- reuse teardown helpers for consistency and regression prevention
- avoid ad hoc `removeSource(...)` usage that skips dependent layers

## Visibility behavior contract

Project visibility should affect:

- project survey layers
- project-scoped markers (for example, leads and cylinder installs)
- depth-domain recomputation in depth mode

Avoid feature-specific visibility logic drift; prefer shared visibility
utilities.

## Context menu icon behavior

Context menu icon rendering is cache-backed to avoid repeated network fetches.

Do not regress into rebuilding image URLs in ways that re-trigger network loads
on every menu open.

## Validation expectations

When changing these feature areas:

- run `npm run lint:js`
- run `npm run test:js`
- verify private/public parity for shared map behavior

For the broader validation playbook, see:

- `docs/map-viewer/testing-and-quality.md`
