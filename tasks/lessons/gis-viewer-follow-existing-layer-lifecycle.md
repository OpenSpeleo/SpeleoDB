# GIS viewer features must use the existing layer lifecycle

## Correction

The first private GIS Layer viewer introduced a client, store, runtime, generic
lazy-overlay manager, generation/version tracking, cache eviction, and
source-load timeouts. The existing GPS Track path already owned the required
API, Config, State, Layers, panel, cache, visibility, loading, and bounds
conventions. Removing that machinery must not remove accepted GIS feature popup
behavior.

## Rule

- Put Map Viewer API calls in `api.js`, entity metadata in `Config`, mutable map
  state in `State`, and rendering in `map/layers.js`.
- Follow the GPS Track path for a private session-only GeoJSON overlay unless a
  concrete product requirement proves that path insufficient.
- Do not introduce generic overlay runtimes, generation/version schemes, cache
  policies, or timers for hypothetical future needs.
- Preserve accepted product interactions during architectural cleanup. Popup
  presentation and safe click-handler ownership do not justify a separate data
  lifecycle.
- Resolve overlapping interactive overlays through one rendered-feature query in
  the existing global click dispatcher. Separate Mapbox layer handlers do not
  define a reliable single winner when features overlap.
- Pass fetched GeoJSON to Mapbox unchanged. Compute only the bounds required by
  explicit zoom behavior.
- A row click may show the entity and call `fitBounds`; a toggle click changes
  visibility only and must not move the camera.
- Keep private-only entities out of the public viewer dependency graph and API
  traffic.
