# Survey shot coloring

## Intent and data contract

The private Survey Viewer offers **By Shot** in Settings → Appearance alongside
By Survey and By Depth. It displays Ariane's recorded shot colors or Compass's
assigned section colors, making source distinctions visible without changing
survey identity, selection, geometry, or depth measurements.

A survey GeoJSON feature may contain `properties.color`. Exporters normalize
opaque colors to `#rrggbb` and colors with transparency to `rgba(r,g,b,a)`.
Legacy exports and individual features without colors remain usable. Regenerated
GeoJSON is required to add source colors to previously stored exports.

Compass palette assignment is random and can change on regeneration. The
exporter stops after at most 16 improving passes, or earlier when a pass makes
no progress, then assigns distinct extra vivid colors with an input-sized
candidate budget. Reaching the pass limit does not leave touching sections with
the same color. Only exhaustion of the finite vivid RGB space omits unresolved
`color` values; those sections use the viewer's survey-color fallback and can
share its displayed color.

## Rendering ownership

`DEFAULTS.DISPLAY.COLOR_MODES` defines the supported internal values: `project`,
`depth`, and `shot`. `Colors.isValidColorMode()` validates both preference
restoration and runtime changes. The existing storage version and default remain
unchanged; resetting returns to By Survey. Public initialization does not read
private preferences and retains its two-mode controls.

`Colors.getSurveyPaint(projectId, mode, depthDomain)` owns paint selection for
mode changes and newly loaded or rebuilt survey line layers. Shot mode uses:

```javascript
["to-color", ["get", "color"], Colors.getProjectColor(projectId)];
```

Mapbox resolves each feature's color during rendering, using that project's
stored color if conversion fails or the property is absent. Alpha is preserved.
The fallback continues to use the existing model-driven color cache; no frontend
palette or source-format-specific parser is introduced. Project identity chips,
entrance symbols, station markers, GPS tracks, and GIS overlays retain their
existing colors.

`Layers.setColorMode()` updates line paint and emits the existing mode and
preference events. Toggling modes never fetches GeoJSON, scans features,
rebuilds sources, resets styles, or moves the camera. Initial GeoJSON processing
already preserves arbitrary feature properties. Depth mode still uses its cached
project domains; leaving it clears the legend's active hover and hides depth
controls.

## UI and verification

The existing native radio group provides keyboard selection and visible focus.
Helper text describes Ariane, Compass, and missing-color behavior. The selected
mode remains available for mixed and legacy datasets, with no availability scan.

Run frontend tests only in the existing application container. Regression
coverage exercises actual template controls, persistence/reset, public
preference isolation, depth hover cleanup, per-project paint fallback, late
loading, replacement data, and layer reconstruction. Source properties include
opaque, transparent, absent, and invalid colors. Expression conversion behavior
should also be verified through the map renderer rather than inferred from
mocked paint calls. Browser verification should cover narrow screens, short
landscape, keyboard focus, and 200% zoom after a clean production asset build.
