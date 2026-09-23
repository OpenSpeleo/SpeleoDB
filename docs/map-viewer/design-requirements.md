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

## GeoJSON line rendering across zoom levels

GeoJSON line geometry remains available at state and country scales: project and
GPS line layers start at zoom zero. Other line layers retain their default zero
minimum. Keep geometry as lines when zooming out; do not replace it with
overview markers or clusters.

`map/line_rendering.js` builds the shared width expression from
`DEFAULTS.GEOJSON_RENDER`: 1 px through zoom 8, 1.5 px at zoom 12, and 2 px at
zoom 14, with continuous interpolation between stops. Overview widths are capped
at each renderer's detail width so a thin outline never grows thicker when
zooming out. Existing detail widths resume at zoom 16 and 18:

| Renderer                                         | Width at zoom 16 / 18 |
| ------------------------------------------------ | --------------------- |
| Public/private survey lines                      | 5 / 6 px              |
| GPS tracks                                       | 6 / 7 px              |
| Imported GIS layers and saved GIS geometry lines | 2.5 / 2.5 px          |
| GIS polygon outlines                             | 1.5 / 1.5 px          |
| Completed/draft measurement lines                | 2 / 2 px              |
| Measurement casing                               | 5 / 5 px              |
| Geometry editor shapes and previews              | 3 / 3 px              |
| Geometry editor bounding boxes                   | 1 / 1 px              |

Both public and private survey entrypoints use `Layers.addProjectGeoJSON`.
Imported GIS layers and saved geometries share `map/vector_overlay.js`;
measurements and editor previews use the same width helper in their own
renderers. Labels, points, fills, colors, dash patterns, geometry filters, and
visibility gates keep their existing behavior.

Measurement casing is a deliberate layered-stroke exception: its overview width
is 1 px wider in total than the foreground, leaving a dark contrasting edge on
light basemaps. `MEASUREMENT.CASING_OVERVIEW_WIDTH_OFFSET` applies to the shared
overview stops, capped at the casing's detail width. Foreground and casing
retain their original 2 px and 5 px widths from zoom 16 onward.

Every GeoJSON source used by these line layers sets simplification tolerance to
zero to retain short lines and polygon detail. This does not guarantee that
every shot is visible at every scale: Mapbox quantizes coordinates to an integer
tile grid, so sufficiently short shots can collapse to a single position before
rendering. Subpixel passages can also overlap on screen. Raising the source's
maximum zoom cannot recover precision in tiles requested at low zoom. See the
renderer's
[coordinate transform](https://github.com/mapbox/geojson-vt/blob/v4.0.2/src/transform.js)
and
[degenerate-line handling](https://github.com/mapbox/mapbox-gl-js/blob/v3.12.0/src/data/bucket/line_bucket.ts).

Rendering below zoom 8 means more visible surveys and GPS tracks may be
processed together. Disabling simplification for GIS imports and other line
sources retains more vertices, increasing tile processing and memory costs for
large datasets. Reuse the existing sources and style expressions: no per-zoom
geometry rebuild, additional source, or feature scan is required. Tolerance zero
already incurs the cost of retaining survey vertices; the shared policy extends
that behavior to all line renderers.

`map/layers.display_preferences.test.js` covers the zero-zoom cutoff, fractional
zoom widths, close-view widths, unsimplified source, refresh/rebuild behavior,
visibility gates, and project/depth/shot colors. GIS layer/geometry tests and
measurement/editor renderer tests cover the same policy for their respective
sources and detail widths, including style reconstruction. Run frontend tests in
the existing application container. Also inspect both viewers with a dense
survey, short shots, GIS lines/polygons, and GPS tracks at zooms 5, 8, 10, 12,
14, 16, and 18: mocked map tests verify layer configuration and lifecycle, not
actual GPU rendering or visual quality.

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
