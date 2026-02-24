# Map Viewer: Depth Domain Reactivity

Agent-focused documentation for the depth coloring refactor in the private and
public map viewers.

## Feature Intent

Depth coloring must react immediately when projects are shown/hidden, without
re-scanning every feature on every toggle.

The previous behavior was effectively feature-count driven during interactions.
The current behavior is project-count driven during interactions.

## Engineering Scope

This feature spans shared map viewer modules and both entrypoints.

### Shared modules

- `frontend_private/static/private/js/map_viewer/map/depth.js`
- `frontend_private/static/private/js/map_viewer/map/layers.js`
- `frontend_private/static/private/js/map_viewer/map/colors.js`
- `frontend_private/static/private/js/map_viewer/state.js`
- `frontend_private/static/private/js/map_viewer/components/depth_legend.js`

### Entrypoints

- Private viewer:
  - `frontend_private/static/private/js/map_viewer/main.js`
- Public viewer:
  - `frontend_public/static/js/gis_view_main.js`

Any depth behavior changes should be validated in both flows.

## Current Architecture

Depth mode uses a two-stage model:

1. **Per-project domain computation at GeoJSON load/refresh**
2. **Merged active-domain computation on visibility changes**

### Stage A: Per-project domain cache

At GeoJSON ingest time (`processGeoJSON(projectId, data)`), each project gets:

- line feature depth fields:
  - `depth_val` (canonical raw depth)
  - `depth_norm` (legacy normalized fallback)
- a stored domain in `State.projectDepthDomains`:
  - `{ min: 0, max: <project max depth> }` or `null`

Helpers involved:

- `buildSectionDepthAverageMap(...)`
- `resolveLineDepthValue(...)`
- `computeProjectDepthDomain(...)`

### Stage B: Active merged domain

On project visibility change and depth mode activation:

- visible project ids are derived via `Layers.getVisibleProjectIds()`
- domains are merged via `mergeDepthDomains(...)`
- result is stored in `State.activeDepthDomain`

Domain updates are emitted as:

- `speleo:depth-domain-updated` (primary)
- `speleo:depth-data-updated` (legacy compatibility payload)

## Design Invariants

1. **Min depth remains pinned at `0`**
   - Domain contract is `{ min: 0, max }`.
2. **No-feature rescans during toggle**
   - Toggling visibility merges cached domains only.
3. **Legend and layer colors use the same active domain**
   - Avoid domain drift between visual elements.
4. **Null domain is valid**
   - When no visible projects have depth, domain is `null`.
   - UI should show `N/A` labels.

## Coloring and Legend Behavior

### Layer coloring

`Colors.getDepthPaint(depthDomain)`:

- returns deterministic fallback color when domain is missing
- otherwise interpolates using `depth_val` and merged domain max

`Layers.applyDepthLineColors()` applies this expression to project line layers.

### Legend and cursor

`DepthLegend` is the single source of behavior for:

- showing/hiding depth legend by color mode
- rendering min/max labels from active domain
- showing `N/A` when domain is missing
- cursor depth indicator from rendered feature values

This module is reused by both private/public entrypoints.

## Performance Intent

### Complexity targets

| Operation | Previous expectation | Current expectation |
|---|---|---|
| GeoJSON load | O(total features) | O(total features) + cache write |
| Toggle in depth mode | O(active features) | O(active projects) |
| Memory | GeoJSON only | GeoJSON + one domain per project |

### Why this matters

With many features and relatively few projects, interaction latency drops
significantly because toggles no longer scale with feature count.

## Regression Risks

Watch for these common mistakes:

- recomputing domain by iterating raw features on every toggle
- bypassing `State.projectDepthDomains` cache
- restoring fixed depth ranges (for example hardcoded `0..500`)
- splitting legend logic across entrypoints instead of using `DepthLegend`
- updating only private or only public entrypoint wiring

## Required Validation

After depth-domain changes, run:

- `npm run lint:js`
- `npm run test:js`

And manually verify:

1. depth mode project hide/show updates color scale immediately
2. all-hidden projects in depth mode shows `N/A`
3. private and public viewers both behave the same way

## Test Coverage Map

### Unit and integration-style frontend tests

- `frontend_private/static/private/js/map_viewer/map/depth.test.js`
  - `mergeDepthDomains` behavior and edge cases
- `frontend_private/static/private/js/map_viewer/map/layers.depth_domain.test.js`
  - reactive domain recomputation from project visibility toggles
- `frontend_private/static/private/js/map_viewer/components/depth_legend.test.js`
  - gauge labels and cursor behavior from domain events
- `frontend_public/static/js/gis_view_main.test.js`
  - public entrypoint initialization and depth-legend wiring

## Implementation Notes for Agents

- Keep domain APIs pure where possible (`map/depth.js`).
- Keep map mutation concentrated in layer/legend modules.
- Prefer extending existing helpers over introducing parallel utilities.
- If event payload shape changes, update all listeners and tests together.

