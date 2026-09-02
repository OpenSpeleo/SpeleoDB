# Private GIS Layers Implementation

## Goal

Provide private KML, KMZ, and GeoJSON overlays with the smallest practical model
and request path.

## Completed design

- [x] Store layer metadata, creator email, original source, and renderable data.
- [x] Store GeoJSON once and expose it directly without preprocessing.
- [x] Convert KML, KMZ, TopoJSON, and zipped Shapefiles to the single GeoJSON
      file required by Mapbox.
- [x] Use direct-user permission rows for list, detail, edit, delete, and
      sharing.
- [x] Add creator ADMIN permission explicitly at each creation entry point.
- [x] Keep GPS Track provenance as `created_by`; remove its user FK and hash.
- [x] Return signed display-file URLs in the normal list/detail serializers.
- [x] Render the returned URL directly with no manifest, revision, polling, or
      job.
- [x] Keep upload modals open unless explicitly dismissed.
- [x] Keep GIS Layer endpoints free of feature throttles.
- [x] Cover models, migrations, API permissions, direct GeoJSON,
      supported-format conversion, storage, admin, management UI, and map
      rendering.

## Private Map Viewer frontend cleanup

- [x] Move GIS Layer API calls into the existing Map Viewer `api.js` module.
- [x] Load GIS Layer metadata through `Config` and keep its session-only
      visibility, loading, registered layers, and bounds in `State`.
- [x] Render and toggle GIS Layers in `map/layers.js`, following the existing
      GPS Track flow and refreshing detail metadata before using a signed URL.
- [x] Make card-body activation show the layer and call only `fitBounds`; keep
      toggle clicks isolated from card activation.
- [x] Delete the GIS client/store/runtime, generic lazy-overlay manager, source
      timeout machinery, cache eviction, and their tests while preserving the
      accepted GIS feature popup.
- [x] Preserve the private-only boundary, supported geometry roles, 130px
      collapsed panels, responsive behavior, and style-reload restoration.
- [x] Replace abstraction tests with direct Config/State/Layers/panel tests.
- [x] Update Map Viewer documentation and record the architectural lesson.
- [x] Run focused tests, the Map Viewer test set, and JavaScript lint.

## Cleanup review

The frontend now follows the GPS Track path without a GIS-specific lifecycle
framework. A first activation refreshes detail metadata, fetches and parses the
current signed GeoJSON once, hands that same object to Mapbox, and computes only
the bounds required for `fitBounds`. Session state and style restoration use the
existing Config/State/Layers conventions.

Removed modules and behavior:

- GIS-specific API client, store, runtime, and generic lazy-overlay manager
- generation/version reconciliation, abort controllers, eviction, and source
  timeout machinery
- separate renderer and label layers; popup presentation remains attached
  directly to the simplified Layers path

Behavior audit against `06136022`:

- Preserved: private-only loading, default-OFF visibility, polygon fill and
  outline, line and point rendering, model color, layer ordering, style
  restoration, and the exact accepted feature-card DOM/CSS/overflow behavior.
- Changed interaction: polygon and point clicks now use the existing single map
  click dispatcher and Mapbox rendered-feature order, so overlaps open exactly
  one popup for the topmost feature. The previous line popup was intentionally
  removed; line clicks no longer open one.
- Removed presentation: the generated label layer and converted-format
  `render_color`, `render_fill_opacity`, `render_outline_opacity`,
  `render_line_width`, and `render_label` styling. Every format now uses the GIS
  Layer model color and the same four basic geometry roles.
- Changed loading: the browser fetches and parses the current display GeoJSON
  once, caches that same object for the session, passes it unchanged to Mapbox,
  and scans it only for the required bounds. Previously Mapbox received the
  signed URL and a source-data listener waited up to 30 seconds.
- Removed lifecycle behavior: request abort/generation guards, modified-date
  version reconciliation, eight-entry LRU eviction, source-load timeout/error
  listeners, generated source IDs, and the `speleo:refresh-gis-layers` Map
  Viewer listener. A page session therefore does not discover a layer created,
  deleted, recolored, or replaced after initial metadata loading.
- Changed controls/errors: a loading toggle is disabled instead of cancelling an
  in-flight activation, and display failures show the generic panel message
  while retaining the detailed error only in the console.
- Added required row behavior: card activation shows the layer if needed and
  invokes only `fitBounds` for its computed bounds; the toggle never moves the
  camera.
- Remaining tradeoffs to review explicitly: parsed GeoJSON cache size is no
  longer bounded, and a synchronous `addSource`/`addLayer` failure does not have
  the old renderer's explicit partial-registration rollback.

Verification:

- focused API/Config/State/Layers/panel/main plus public-boundary tests: 193
  passed
- focused popup, overlap ordering, replacement/style-rebuild, panel, and
  public-boundary tests: 39 passed in the latest focused run
- private Map Viewer plus public-boundary suite: 772 passed
- `npm run lint:js`: passed
- `npm run build`: passed
