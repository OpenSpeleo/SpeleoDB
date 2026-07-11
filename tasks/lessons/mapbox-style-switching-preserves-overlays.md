# Mapbox Base Sources Must Not Clear Runtime Overlays

When a map viewer feature changes only the base map, do not reach for
`map.setStyle()` by default. In this codebase, survey lines, stations,
landmarks, GPS tracks, cylinder installs, exploration leads, labels, depth
coloring, and project visibility are runtime Mapbox sources/layers. A full style
reset removes that runtime state and forces brittle rehydration.

Rules to keep:

- Use a shared source registry for provider definitions.
- For tokenless raster providers, add/replace one base raster source/layer below
  SpeleoDB overlays instead of resetting the style.
- Hide only underlying base-style layers while the raster base is active. Never
  hide layers with SpeleoDB overlay prefixes.
- Source-change events that do not destroy overlays must carry
  `reloadRequired: false`, and entrypoints must ignore them.
- Tests should assert the negative behavior: no `setStyle()`, no overlay reload,
  no custom layer hiding, and one raster layer inserted below overlays.

If a future provider truly requires a full Mapbox style reset, make that an
explicit `reloadRequired: true` path with tests proving the overlay reload is
intentional and complete.
