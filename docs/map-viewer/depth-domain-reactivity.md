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
- an optional private depth limit replaces the merged maximum, when depth data
  exists; the result is stored in `State.activeDepthDomain`

Individual project toggles resolve the country gate before applying visibility
or emitting depth-domain events. The saved individual preference and effective
map visibility are passed through one layer operation. Applying the country gate
in a second step would leave the legend using a hidden project's depth range.

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

### Private depth limit

Settings → Appearance → By Depth reveals a collapsed **Depth limit** disclosure.
The collapsed row uses muted text with no highlighted border, background, or
value; the expanded control carries the selected-state styling. Its summary
shows Full range or the configured maximum, so the active limit stays
discoverable without leaving a large form open. Expanding it exposes one numeric
field and a Meters/Feet toggle. The field accepts positive finite values;
clearing it or choosing **Reset to Full Depth Range** restores the
visible-project range. Validation happens while typing, but map updates happen
on blur/change or Enter. Invalid drafts retain the last applied limit and show
an inline error.

The limit is a fixed **0–X scale**, including when all visible surveys are
shallower than X. Deeper lines saturate at the deepest color and hover readings
stop at X. Hiding/revealing projects or country groups, or loading projects
later, cannot move a configured maximum. With no visible depth data the legend
still shows N/A. Clearing the limit immediately uses the latest visible
projects' cached maximum. Original GeoJSON depths, exports, and per-project
domains remain unchanged.

Survey compilers produce canonical depths in feet. `depthLimitFeet` stores the
physical limit and `depthUnit` (`ft` or `m`) controls input and legend
formatting. Conversions use `DEFAULTS.MEASUREMENT.METERS_PER_FOOT`. Switching
units preserves canonical feet rather than converting a rounded input back
repeatedly. Fractional limits appear without the automatic feet axis's
historical integer ceiling. Cursor readings use one decimal except at the cap,
where the limit's precision prevents a rounded label from exceeding the chosen
maximum.

Ownership is deliberately small:

- `map/depth.js`: pure validation, conversion, and domain-limit helpers.
- `Layers.setDepthLimit(limitFeet, unit)`: validated preference mutation, cached
  domain recomputation, paint updates, and existing preference/domain events.
- `DepthLegend`: unit labels and capped hover readings, including a
  constant-time source-project lookup for legacy normalized depths when a limit
  is active.
- `MapSettings`: disclosure, numeric draft/validation, and unit controls.
- `DisplayPreferences`: optional fields in the existing versioned browser
  record. Older records use full-range/feet defaults. Reset clears the limit and
  units.

Only the private template exposes the setting and private initialization
restores it. Public initialization resets preferences without reading or writing
the private record, so public maps retain automatic depth scaling and feet.
Shared layers and legend still use the same implementation in both viewers. This
is a local display preference; no API, database migration, background job, or
source rebuild is needed.

## Performance Intent

### Complexity targets

| Operation            | Previous expectation | Current expectation              |
| -------------------- | -------------------- | -------------------------------- |
| GeoJSON load         | O(total features)    | O(total features) + cache write  |
| Toggle in depth mode | O(active features)   | O(active projects)               |
| Memory               | GeoJSON only         | GeoJSON + one domain per project |

Limit changes also cost O(projects), with no feature traversal or network
request. Unit-only changes emit a domain event to update labels and the
stationary hover cursor, but do not repaint lines. Input keystrokes only
validate the local draft.

### Why this matters

With many features and relatively few projects, interaction latency drops
significantly because toggles no longer scale with feature count.

## Regression Risks

Watch for these common mistakes:

- recomputing domain by iterating raw features on every toggle
- bypassing `State.projectDepthDomains` cache
- introducing hardcoded depth ranges instead of the explicit optional user limit
- splitting legend logic across entrypoints instead of using `DepthLegend`
- updating only private or only public entrypoint wiring

## Required Validation

After depth-domain changes, run inside the existing application container:

- `docker exec -w /app speleodb_local_django npm run lint:js`
- `docker exec -w /app speleodb_local_django npm run test:js`
- `docker exec -w /app speleodb_local_django npm run build`

And manually verify:

1. depth mode project hide/show updates color scale immediately
2. all-hidden projects in depth mode shows `N/A`
3. shared automatic behavior remains aligned; private limits do not leak
   publicly
4. limit/unit edits update labels and the current hover without another mouse
   move
5. project/country toggles and delayed loading retain a configured scale

## Test Coverage Map

### Unit and integration-style frontend tests

- `frontend_private/static/private/js/map_viewer/map/depth.test.js`
  - domain merging, limit validation, conversion, fixed maxima and null domains
- `frontend_private/static/private/js/map_viewer/map/layers.depth_domain.test.js`
  - reactive domain recomputation from project visibility toggles
- `frontend_private/static/private/js/map_viewer/map/layers.depth_limit.test.js`
  - fixed limits, country gates, late loads, clearing, reset and repaint
    boundaries
- `frontend_private/static/private/js/map_viewer/map/layers.depth_limit_performance.test.js`
  - ingest 20,000 lines once, then enforce no feature reads, downloads or source
    rebuilds across 100 limit/unit/visibility cycles; no timing thresholds
- `frontend_private/static/private/js/map_viewer/components/depth_legend.test.js`
  - gauge labels, fractional limits, units, saturation and legacy hover behavior
- `frontend_private/static/private/js/map_viewer/components/settings.test.js`
  - disclosure, commit/validation, no typing repaint, conversion without drift
- `frontend_private/static/private/js/map_viewer/display_preferences.test.js`
  - optional field migration, validation, reset, storage failure, public
    isolation
- `frontend_public/static/js/gis_view_main.test.js`
  - public entrypoint initialization and depth-legend wiring

## Implementation Notes for Agents

- Keep domain APIs pure where possible (`map/depth.js`).
- Keep map mutation concentrated in layer/legend modules.
- Prefer extending existing helpers over introducing parallel utilities.
- If event payload shape changes, update all listeners and tests together.
