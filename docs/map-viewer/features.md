# Map Viewer Features

> Agent-focused documentation for the SpeleoDB map viewer feature set. Covers
> engineering intent, module boundaries, and behavioral contracts.

The private map viewer entrypoint is
`frontend_private/static/private/ts/map_viewer/main.ts`. The public viewer
entrypoint is `frontend_public/static/ts/gis_view_main.ts`. Both share the same
underlying modules; the public viewer exposes a read-only, token-authenticated
subset.

---

## Distance Measurement (Private)

The ruler below Map Source measures independent temporary A–B pairs, showing
metric and imperial distance together. Mouse, touch, and keyboard placement
share one tool state. Cancel affects only the draft; turning the tool off or
starting geometry editing clears all pairs. Native map overlays retain correct
camera and globe behavior. See
[distance ruler architecture and UX](measurement.md) for distance semantics,
input ownership, lifecycle, and verification.

## Map Source Selection

The public and private viewers share a single base-map source system. Users
select the base map from the existing map-canvas source control in the private
viewer and the in-map **Map Source** control in the public viewer; the choice is
persisted in browser `localStorage` under `DEFAULTS.STORAGE_KEYS.MAP_SOURCE`.

Supported sources are defined in one registry, `MAP_SOURCES` in
`frontend_private/static/private/ts/map_viewer/config.ts`:

- `MapBox - Satellite` uses the existing Mapbox satellite streets style and
  requires the configured Mapbox token.
- `ESRI - Satellite` uses the public ESRI World Imagery raster tile endpoint.
- `ESRI - World Hillshade` uses the public ESRI raster tile endpoint.
- `ESRI - World Hillshade Dark` uses the public ESRI dark hillshade raster tile
  endpoint.

The registry order is also the order shown in the selector. When no Mapbox token
is available, the token-required `MapBox - Satellite` entry is filtered out and
the first remaining source (`ESRI - Satellite`) becomes the default.

For local Compose development, `MAPBOX_API_TOKEN` is developer-owned in the
repository-root `.env`. `local.yml` interpolates that value into the Django and
webserver services; `.envs/.django` must not define a placeholder that shadows
it. If the root value is blank or absent, the existing tokenless ESRI Satellite
fallback is used and the browser does not request the Mapbox Styles API.

The ESRI hillshade sources use raster provider `maxzoom: 16`; the viewer may
zoom beyond 16, but MapLibre GL overzooms the zoom-16 ESRI tiles instead of
requesting ESRI zoom 17+ tiles. ESRI Satellite uses provider `maxzoom: 18`.
`DEFAULTS.MAP.MISSING_TILE_SHA256_HASHES` is a global missing tile image hash
list applied systematically to every configured raster source. MapLibre's scoped
asynchronous raster protocol checks configured tile responses against this list
before decoding. It forwards cancellation and cache metadata without modifying
global `fetch`. The MapLibre engine and worker are bundled by Vite; Mapbox
continues to supply the classic satellite/vector-label provider through
documented HTTPS APIs. Its logo and native text attribution remain visible. See
[Shared map packages](shared-packages.md).

Provider behavior lives in `map/sources.ts`. It validates persisted source ids,
filters token-required providers when a token is unavailable, builds the initial
Mapbox style object, and switches ESRI sources by replacing one raster tile
layer below all SpeleoDB overlays. It does not call `map.setStyle()` for ESRI
switches, so survey/station/marker layers remain visible.

To add another source, add one `MAP_SOURCES` entry with its id, label, source
type, tile/style config, attribution, and token requirement. Do not add
public/private entrypoint-specific provider logic. Raster tile URLs may include
`{accessToken}` when a future provider needs a token.

Source changes dispatch `speleo:map-source-changed`. ESRI switches set
`reloadRequired: false`; private and public entrypoints ignore those events
because the switch is a base-raster replacement, not a full style reset. The
control icon is the trusted static `MAP_SOURCE_ICON_SVG` constant in
`map/sources.ts`; keep user/API data out of that `innerHTML` path.

---

## 1. Station Management

The private toolbar provides Create Geometry, Import GPX/KML, Managers, and
Settings. Settings owns color and marker visibility preferences. Managers
separately opens Survey Stations, Surface Stations, and Landmarks. See
[Settings design](settings.md) for visibility composition, persistence,
accessibility, and extension contracts.

### 1.1 Subsurface Stations

**Module:** `stations/manager.ts`

Subsurface stations are **project-scoped**. Each station belongs to exactly one
project and carries a UUID, lat/lng coordinates, and an optional
`subsurface_type` discriminator.

#### Subsurface types

| Type       | Layer suffix      | Icon key   |
| ---------- | ----------------- | ---------- |
| `sensor`   | `-circles`        | `sensor`   |
| `biology`  | `-biology-icons`  | `biology`  |
| `bone`     | `-bone-icons`     | `bone`     |
| `artifact` | `-artifact-icons` | `artifact` |
| `geology`  | `-geology-icons`  | `geology`  |

Plain sensor stations render as circles; the remaining types render as custom
icon images loaded from `window.MAPVIEWER_CONTEXT.icons`.

#### Data loading strategy

`StationManager.ensureAllStationsLoaded()` fetches **all** subsurface stations
visible to the current user in a single
`GET /api/v2/stations/subsurface/geojson/` call, then caches the
`FeatureCollection` in the module-level `allStationsGeoJson` variable.
Project-specific views (`loadStationsForProject`) filter the cached collection
client-side. The cache is invalidated on any create/delete mutation via
`invalidateCache()`.

#### CRUD operations

| Operation | Manager method                      | API method                  | HTTP verb |
| --------- | ----------------------------------- | --------------------------- | --------- |
| Create    | `createStation(projectId, data)`    | `API.createStation`         | `POST`    |
| Read      | `loadStationsForProject(projectId)` | `API.getAllStationsGeoJSON` | `GET`     |
| Update    | `updateStation(stationId, data)`    | `API.updateStation`         | `PATCH`   |
| Delete    | `deleteStation(stationId)`          | `API.deleteStation`         | `DELETE`  |
| Move      | `moveStation(stationId, coords)`    | (calls `updateStation`)     | `PATCH`   |

After every mutation the manager invalidates its cache and calls
`Layers.refreshStationsAfterChange(projectId)` to redraw the map layer.
`moveStation` includes a visual-revert path: if the API call fails, the station
is snapped back to its original coordinates on the map via
`Layers.updateStationPosition`.

#### Permission gating

Station loading is skipped when the user lacks `read` access on the project
(`Config.hasProjectAccess(projectId, 'read')`). Drag-to-move requires `write`
access checked via `Config.hasScopedAccess('project', projectId, 'write')`.

### 1.2 Surface Stations

**Module:** `surface_stations/manager.ts`

Surface stations are **network-scoped** (belong to a `SurfaceMonitoringNetwork`,
not a project). They render as diamond symbols on layers prefixed
`surface-stations-`. The data loading strategy mirrors subsurface stations: a
single `GET /api/v2/stations/surface/geojson/` call returns all surface
stations, which are filtered by network client-side.

Surface stations are managed via:

| API method                         | HTTP | URL pattern                                               |
| ---------------------------------- | ---- | --------------------------------------------------------- |
| `API.createSurfaceStation`         | POST | `/api/v2/surface-networks/<network_id>/stations/`         |
| `API.getNetworkStationsGeoJSON`    | GET  | `/api/v2/surface-networks/<network_id>/stations/geojson/` |
| `API.getAllSurfaceStationsGeoJSON` | GET  | `/api/v2/stations/surface/geojson/`                       |

### 1.3 Station Details Modal

**Module:** `stations/details.ts`

The details modal is opened via
`StationDetails.openModal(stationId, parentId, isNewlyCreated, stationType)`. It
tracks both subsurface and surface stations with a `currentStationType`
discriminator (`'subsurface'` or `'surface'`).

#### Tabs

| Tab             | Sub-module                | Description                                             |
| --------------- | ------------------------- | ------------------------------------------------------- |
| **Details**     | inline in `details.ts`    | Name, description, type badge, coordinates, dates       |
| **Logs**        | `stations/logs.ts`        | Timestamped field-log entries with optional images      |
| **Resources**   | `stations/resources.ts`   | File attachments (photos, documents, data files)        |
| **Sensors**     | `stations/sensors.ts`     | Sensor install history, fleet integration, Excel export |
| **Experiments** | `stations/experiments.ts` | Experiment records linked to the station                |

The active tab is tracked via the module-level `activeTab` variable (default
`'details'`).

### 1.4 Station Tags

**Module:** `stations/tags.ts`

Tags provide **user-defined color coding** for stations. Each user can create
named tags with one of 20 predefined colors (fetched from `API.getTagColors()`;
fallback palette hardcoded in `FALLBACK_COLORS`).

Key operations:

- `StationTags.init()` — loads tags and colors in parallel.
- `StationTags.openTagSelector(stationId)` — renders a modal overlay allowing
  the user to assign/create/remove a tag.
- `API.setStationTag(stationId, tagId)` / `API.removeStationTag(stationId)` —
  server-side assignment.
- Tags apply to both subsurface and surface stations (state lookup checks both
  `State.allStations` and `State.allSurfaceStations`).

Tag color is reflected on the map by updating the station's `color` property in
the GeoJSON source data.

---

## 2. Landmark Management

**Module:** `landmarks/manager.ts`

Landmarks are **collection-scoped**, not project-scoped. A user's private
Landmarks live in their personal Landmark Collection, and shared Landmarks are
visible through Landmark Collection permissions.

### Data loading

`LandmarkManager.loadAllLandmarks()` calls `API.getAllLandmarksGeoJSON()` and
populates `State.allLandmarks`. Properties stored per landmark: `id`, `name`,
`description`, `latitude`, `longitude`, `coordinates`, `collection`,
`collection_name`, `collection_type`, `collection_color`, `created_by`,
`creation_date`, `can_write`, and `can_delete`.

### CRUD operations

| Operation | Manager method                     | API method               | HTTP   |
| --------- | ---------------------------------- | ------------------------ | ------ |
| Create    | `createLandmark(data)`             | `API.createLandmark`     | POST   |
| Update    | `updateLandmark(landmarkId, data)` | `API.updateLandmark`     | PATCH  |
| Delete    | `deleteLandmark(landmarkId)`       | `API.deleteLandmark`     | DELETE |
| Move      | `moveLandmark(landmarkId, coords)` | (calls `updateLandmark`) | PATCH  |

After every mutation the full landmark set is reloaded and the layer is redrawn
via `Layers.addLandmarkLayer(featureCollection)` followed by
`Layers.reorderLayers()` to ensure landmarks render on top.

### Drag-to-move with confirmation

Landmarks support drag-to-move. Unlike stations, landmarks **do not** snap to
survey lines — they are placed freely on the map. On drag end, the
`onLandmarkDragEnd` handler fires with
`(landmarkId, newCoords, originalCoords)`, and a confirmation modal is shown. On
cancel, the landmark reverts to its original position via
`Layers.revertLandmarkPosition`.

---

## 3. Exploration Leads

**Module:** `exploration_leads/manager.ts`

Exploration leads are **project-scoped** markers that indicate promising areas
for future exploration. They are placed at survey line endpoints (magnetic
snap-to-line required; see Section 6).

### Data loading strategy

Identical to `StationManager`: a single `GET /api/v2/exploration-leads/geojson/`
call fetches all leads into a module-level `allLeadsGeoJson` cache.
`loadLeadsForProject(projectId)` filters client-side. The cache is invalidated
after create/delete operations.

### Permission gating

- Loading requires `read` access on the project.
- Projects with only `WEB_VIEWER` permission are excluded.
- Drag-to-move requires `write` access checked by the interaction layer
  (`Config.hasScopedAccess('project', projectId, 'write')`).

### CRUD operations

| Operation | Manager method                                    | API method                                 | HTTP   |
| --------- | ------------------------------------------------- | ------------------------------------------ | ------ |
| Create    | `createLead(projectId, coordinates, description)` | `API.createExplorationLead`                | POST   |
| Read      | `loadLeadsForProject(projectId)`                  | `API.getAllProjectExplorationLeadsGeoJSON` | GET    |
| Update    | `updateLead(leadId, data)`                        | `API.updateExplorationLead`                | PATCH  |
| Delete    | `deleteLead(leadId)`                              | `API.deleteExplorationLead`                | DELETE |
| Move      | `moveLead(leadId, newCoords)`                     | (calls `updateLead`)                       | PATCH  |

Coordinates are stored with 7 decimal places of precision (`toFixed(7)`).

---

## 4. GPS Tracks

**Module:** `components/gps_tracks_panel.ts`

GPS tracks are authenticated, direct-user permissioned track files. Creator
provenance remains on the model, while active READ_ONLY, READ_AND_WRITE, or
ADMIN permission rows determine access. The panel is only rendered if
`Config.gpsTracks.length > 0`.

### Architecture

- Track metadata is provided via `Config.gpsTracks` (populated from the
  accessible-track API). This includes creator-owned and shared tracks.
- Track GeoJSON data is loaded **on demand** when the user activates a track via
  the panel toggle.
- Loaded track data is **lazily cached** in `State.gpsTrackCache` (keyed by
  track ID as string).
- Track bounds are stored in `State.gpsTrackBounds` for the fly-to-track
  feature.

### GPX import

New tracks are imported via `API.importGPX(formData)` which hits
`PUT /api/v2/import/gpx/`. The server converts GPX to GeoJSON for storage and
grants the importer ADMIN access. See `docs/gps-tracks.md` for export and
sharing contracts.

### Panel behavior

- The panel positions itself below the project panel (expanded or minimized),
  using a `ResizeObserver` on the project panel to reposition dynamically
  (catches country group collapse/expand).
- Each track item shows: color dot, name (truncated at 30 chars), loading
  spinner (when fetching), and a toggle switch.
- Clicking the track card body activates the track and flies to its bounds
  (`fitBounds` with padding 50, maxZoom 16).
- Colors are model-stored; resolved via `Colors.getGPSTrackColor(trackId)` which
  reads `Config.getGPSTrackById(trackId).color`.

### Visibility control

`Layers.toggleGPSTrackVisibility(trackId, isVisible, trackUrl)` handles both
fetching (if not cached) and showing/hiding the track layer. GIS Layers do not
replace or generalize this established GPS Track lifecycle.

## 4.1 Private GIS Layers

**Modules:** `api.ts`, `config.ts`, `state.ts`, `map/layers.ts`, and
`components/gis_layers_panel.ts`

GIS Layers are authenticated KML, KMZ, GeoJSON, TopoJSON, or zipped Shapefile
overlays. Every layer defaults OFF. First activation refreshes the authenticated
detail response and fetches its current signed GeoJSON. The standard Map Viewer
State/Layers cache retains that original document; cooperative preparation
derives bounds and a separate display copy for geometry-type filtering. GPS
Tracks and GIS Layers share `toggleLazyOverlay` in `map/layers.ts`, which checks
map generation, latest visibility intent, and metadata modification time, and
aborts replaced requests. Only current results reach scheduled map installation.
Polygon fill/outline, line, and point roles are created.

Clicking a row shows the layer if necessary and calls only `fitBounds` with its
computed GeoJSON bounds. The toggle changes visibility without moving the
camera. There is no separate GIS runtime or server job lifecycle. The shared
concurrency guards prevent stale loads from undoing a later toggle or metadata
refresh. The feature is not loaded by the public viewer.

Polygon-zone and point clicks open the established GIS-scoped MapLibre popup. It
uses DOM creation and `textContent` only, shows the feature title and optional
plain-text description, and bounds the existing geometry/folder/ExtendedData
rows and text length. The header and metadata footer remain fixed while the
description uses the accepted custom scroll viewport, persistent overflow rail,
wheel/touch isolation, keyboard access, and responsive sizing. Every MapLibre
override remains scoped beneath `.gis-layer-feature-popup`.

The existing global Map Viewer click dispatcher queries all active polygon fill
and point layer IDs together and opens one popup for MapLibre's topmost rendered
feature. Source replacement updates that ID set and a destructive style rebuild
clears it; neither operation registers another click handler. Lines do not open
the popup.

---

## 5. Cylinder Installs

Cylinder installs track **safety cylinders** (e.g., breathing gas cylinders
placed underground for emergency use).

### Data model

- **Cylinder Fleet** — a fleet/group of cylinders.
- **Cylinder** — an individual physical cylinder.
- **Cylinder Install** — a placement record linking a cylinder to a geographic
  location (with a station or standalone coordinates).
- **Pressure Check** — a timestamped pressure reading for an installed cylinder.

### Map integration

Cylinder installs render as a dedicated `cylinder-installs-layer`. GeoJSON is
fetched via `API.getAllCylinderInstallsGeoJSON()` at
`GET /api/v2/cylinder-installs/geojson/`.

Cylinder installs support:

- Click to view details (`onCylinderInstallClick` handler).
- Drag-to-move with magnetic snap-to-line behavior (same as stations).
- Right-click context menu.
- Write permission is checked per project for drag operations.

### API surface

| API method                           | HTTP   | Description                           |
| ------------------------------------ | ------ | ------------------------------------- |
| `getCylinderInstalls(params)`        | GET    | List installs, optional query filters |
| `getCylinderInstallsGeoJSON()`       | GET    | GeoJSON for map rendering             |
| `createCylinderInstall(data)`        | POST   | Create new install                    |
| `getCylinderInstallDetails(id)`      | GET    | Single install detail                 |
| `updateCylinderInstall(id, data)`    | PATCH  | Update install                        |
| `deleteCylinderInstall(id)`          | DELETE | Remove install                        |
| `getCylinderPressureChecks(id)`      | GET    | List pressure checks for an install   |
| `createCylinderPressureCheck(id, d)` | POST   | Record a pressure check               |
| `updateCylinderPressureCheck(...)`   | PATCH  | Update a pressure check               |
| `deleteCylinderPressureCheck(...)`   | DELETE | Remove a pressure check               |

---

## 6. Drag-and-Drop System

**Module:** `map/interactions.ts`, `map/geometry.ts`

The drag system handles repositioning of stations, landmarks, cylinder installs,
and exploration leads on the map.

### Drag threshold

A `DRAG_THRESHOLD` of 10 pixels prevents accidental drags from firing on simple
clicks. The threshold is calculated as Euclidean pixel distance from the
mousedown point.

### Drag types and snap behavior

| Drag type          | Snaps to survey lines | Visual feedback during drag                  |
| ------------------ | --------------------- | -------------------------------------------- |
| `station`          | Yes                   | Color change: green (snapped) / amber (free) |
| `cylinder-install` | Yes                   | Highlight circle: green/amber                |
| `exploration-lead` | Yes                   | Highlight circle: green/amber                |
| `landmark`         | No                    | Free drag, no snap indicator                 |

The `SNAPPABLE_TYPES` constant defines which types participate in magnetic
snapping: `['station', 'cylinder-install', 'exploration-lead']`.

### Magnetic snap-to-line

**Module:** `map/geometry.ts`

`Geometry.findMagneticSnapPoint(coords, excludeFeatureId)` searches cached
survey line endpoints for the nearest point within `MAGNETIC_SNAP_RADIUS`
(default 10 meters). Distance is computed using the Haversine formula.

Snap points are cached per project in `snapPointsCache`. The cache is populated
by `Geometry.cacheLineFeatures(projectId, geojsonData)` which extracts start and
end vertices of every `LineString` feature.

The snap indicator (a visual dot on the map) is shown/hidden via
`Geometry.showSnapIndicator(coords, map, isSnapped)` /
`Geometry.hideSnapIndicator()`.

### Confirmation flow

On drag end, a confirmation modal is presented:

1. **Snapped position** — shows which survey line endpoint the feature snapped
   to.
2. **Free position** — shows raw coordinates.
3. **Cancel** — reverts the feature to its original position on the map.

The revert path differs by type:

- Stations: `Layers.updateStationPosition(sourceId, stationId, originalCoords)`
- Landmarks: `Layers.revertLandmarkPosition(landmarkId, originalCoords)`
- Cylinder installs: `Layers.updateCylinderInstallPosition(id, originalCoords)`
- Exploration leads: `Layers.updateExplorationLeadPosition(id, originalCoords)`

### Permission gating

Drag initiation requires write access:

- Stations, cylinder installs, exploration leads:
  `Config.hasScopedAccess('project', projectId, 'write')`
- Landmarks: any authenticated user can drag their own landmarks (no
  project-level check).

---

## 7. Context Menu

**Module:** `components/context_menu.ts`

A right-click context menu provides actions on map features.

### Supported targets

| Target             | `type` string        | Data passed to handler         |
| ------------------ | -------------------- | ------------------------------ |
| Subsurface station | `'station'`          | `{ id, feature, stationType }` |
| Surface station    | `'surface-station'`  | `{ id, feature, stationType }` |
| Landmark           | `'landmark'`         | `{ id, feature }`              |
| Cylinder install   | `'cylinder-install'` | `{ id, feature }`              |
| Exploration lead   | `'exploration-lead'` | `{ id, feature }`              |
| Map background     | `'map'`              | `{ coordinates }`              |

### Menu item structure

Each item can have: `label`, `subtitle`, `icon` (HTML markup), `disabled`
(boolean), `onClick` (callback). The separator `'-'` renders a visual divider.

### Icon caching for performance

Icons referenced in menu item markup (via `src=` attributes) are prefetched and
converted to data-URLs at initialization (`prefetchKnownIcons`) and before each
`show()` call (`prefetchIconsFromItems`). Cached data-URLs are stored in
`iconDataUrlCache` (a `Map`). The `getCachedIconMarkup(markup)` method rewrites
`src` attributes to use cached data-URLs, eliminating redundant network fetches.

### Positioning

`getClampedPosition(clickX, clickY, menuRect, viewportPadding)` ensures the menu
stays within viewport bounds, flipping near edges before clamping.

### Dismissal

The menu hides on any document click or the Escape key.

---

## 8. Component Library

### 8.1 Modals

**Module:** `components/modal.ts`

Confirmation and input modals used by the drag system, deletion confirmations,
and CRUD workflows. Modals are rendered as fixed overlays with backdrop blur.

`dialog_lifecycle.ts` owns nested-dialog isolation, live dismissal guards,
keyboard capture, and return focus. `dialog_focus.ts` computes the visible
keyboard order, including disclosure summaries. The HTML-accepting `Modal`
facade retains content ownership and delayed `onOpen` callbacks; callers escape
untrusted values before building its markup. `ts-types/domain/map-dialog.ts`
describes these capabilities without changing DOM timing or singleton identity.

`panel_position.ts` positions panels below the first anchor whose inline display
is not `none`; it does not perform a new visibility scan. Colocated tests cover
focus/inert restoration, guarded dismissal, repeat opens, and anchor offsets.

### 8.2 Notifications

**Module:** `components/notification.ts`

Toast-style notifications for success/error/info feedback after operations
(station created, drag confirmed, API errors, etc.).

### 8.3 Upload with Progress

**Module:** `components/upload.ts`

File upload component used for station resources, log entry attachments, and GPX
imports. `uploadWithProgress` owns an XMLHttpRequest transport, returns the
original XHR for cancellation, and forwards progress and upload-complete events.
`UploadProgressController` owns progress markup and a promise facade. This path
returns `null` for 204 or empty successful responses; unreadable successful
responses remain ambiguous errors. Error objects retain status, ambiguity, and
parsed payload fields rather than becoming a new error class.

`ts-types/domain/upload.ts` separates callback payloads from untrusted
serializer errors. Type-only class fields do not create new instance properties.
Unit coverage checks FormData identity, callback receivers, error/abort
payloads, promise settlement, and the delayed hide; Django subprocess
integration checks the real transport against the application.

### 8.4 Project Panel

**Module:** `components/project_panel.ts`

Left-side panel listing all projects the user has access to. Projects are
grouped by country when the `country` field is present on at least one project;
otherwise a flat alphabetical list is rendered. Each country group has a
collapsible header with a flag emoji, project count, and a bulk-toggle switch
that acts as a **visibility gate** for all projects in the group.

#### Two-level visibility model

Map visibility uses two independent controls:

1. **Country gate** — the country toggle switch. When OFF, all projects in that
   country are hidden on the map regardless of individual state.
2. **Individual project toggle** — per-project visibility.

A project is visible on the map only when **both** its country gate AND its
individual toggle are ON. Toggling a country OFF/ON does not reset individual
project preferences.

`State.effectiveProjectVisibility` (`Map<string, boolean>`) tracks the actual
map-level visibility computed from both gates. It is set **before** the map
guard in `applyProjectLayerVisibility` so that downstream consumers
(`getVisibleProjectIds`) read the real on-map state. This affects stations,
leads, cylinders, depth domains, and survey snapping. Both magnetic snapping and
context-menu nearest-endpoint lookup use the shared selectors in
`map/project_visibility.ts`, including when a specific project is requested.
Each query reads current effective state; changing either gate does not rescan
GeoJSON or discard cached endpoints. Opening a country restores snapping only
for projects whose individual preference is still enabled. Before effective
state has been published, selectors retain the individual-preference fallback.

`geometry.visibility.test.ts` exercises both query methods with the real
project-panel visibility operations, including immediate gate changes and
repeated toggles without endpoint-cache rebuilding. `layers.visibility.test.ts`
protects the existing Layers facade's receiver behavior and State resets.

`_applyInitialCountryVisibility()` is called during `ProjectPanel.init()` to
enforce country gates on page load.

Collapse state is persisted to `localStorage` under
`DEFAULTS.STORAGE_KEYS.COUNTRY_COLLAPSED`. Country visibility state is persisted
under `DEFAULTS.STORAGE_KEYS.COUNTRY_VISIBILITY`.

### 8.5 GPS Tracks Panel

**Module:** `components/gps_tracks_panel.ts`

See Section 4. Positioned below the project panel, auto-repositions on project
panel resize (including country group collapse/expand) via a `ResizeObserver` on
the project panel container.

### 8.6 GIS Layers Panel

**Module:** `components/gis_layers_panel.ts`

Private accessible layers appear alphabetically, default OFF, and show loading
and safe failure feedback. It is an isolated sibling below GPS Tracks in the
existing left-side panel stack and is hidden at the same established mobile
breakpoint. Its collapsed width is 130px. Geometry-role children never become
user-facing toggles.

---

## 9. Project, GPS Track & GIS Layer Colors

**Model fields:** `Project.color`, `GPSTrack.color`, `GISLayer.color`,
`LandmarkCollection.color` (all `CharField(max_length=7)`) **Palette:**
`ColorPalette` in `speleodb/common/enums.py` **JS module:** `map/colors.ts`

### Model-stored colors

`Project`, `GPSTrack`, and `LandmarkCollection` store a hex color on the Django
model, assigned randomly from `ColorPalette.COLORS` (20 perceptually distinct
entries) at creation time via `ColorPalette.random_color()`. Users can change
the color via color pickers on project pages, GPS track edit pages, and Landmark
Collection create/details pages.

Personal Landmark Collections are the exception to random assignment: they
default to white (`#ffffff`) so private Landmarks have a consistent visual
identity. The map uses a dark halo for white Landmark markers and labels.

### Color resolution in the map viewer

`Colors.getProjectColor(projectId)` reads the stored color from
`Config.getProjectById(projectId).color`. If the project is not yet loaded in
Config, it returns `FALLBACK_COLOR` (`#94a3b8`) **without caching**, so the next
call retries (resolves timing issues during init).

`Colors.getGPSTrackColor(trackId)` follows the same pattern via
`Config.getGPSTrackById(trackId).color`, falling back to `FALLBACK_COLOR`.

GIS Layers read their model-stored color from `Config.getGISLayerById(layerId)`
when their MapLibre roles are created, with the same fallback.

Landmark marker and label colors come directly from each GeoJSON feature's
`collection_color` property, falling back to `FALLBACK_COLOR` if the property is
missing.

There is **no palette array in JS**. All color assignment is model-driven.

### Palette source of truth

The 20-color palette lives in a single canonical location:

| Location                   | Class                                                                                         |
| -------------------------- | --------------------------------------------------------------------------------------------- |
| `speleodb/common/enums.py` | `ColorPalette` — `COLORS` tuple, `random_color()` classmethod, `is_valid_hex()` static method |

The palette is exposed to Django templates via the
`{% get_project_color_palette %}` template tag (returns `ColorPalette.COLORS`).

### Serializer validation

`ProjectSerializer.validate_color()`, `GPSTrackSerializer.validate_color()`, and
`LandmarkCollectionSerializer.validate_color()` enforce hex format via
`ColorPalette.is_valid_hex()` and normalize to lowercase.

`GPSTrackSerializer` updates metadata without replacing the stored GeoJSON.

### Color picker UI

**Pages:** `details.html`, `new.html` (projects and Landmark Collections), GPS
track edit modal

The color picker renders:

1. Preset swatches from `{% get_project_color_palette %}`.
2. A native color picker triggered via an SVG icon.
3. An editable hex input with `#` prefix.

For read-only projects, the picker is visually disabled (opacity 0.5,
pointer-events none), presets are hidden, and the save button is grayed with
cursor-not-allowed.

### Template tag

`{% get_project_color_palette %}` (registered in
`speleodb/surveys/templatetags/project_colors.py`) exposes the palette to Django
templates for rendering color-picker preset swatches.

---

## 10. Country Grouping

**JS module:** `components/project_panel.ts` **Django view:**
`ProjectListingView` in `frontend_private/views/project.py`

Projects are grouped by country in two places: the project panel inside the map
viewer, and the project listing page (`projects.html`).

### Map viewer project panel

When at least one project has a `country` value, `ProjectPanel` renders country
groups instead of a flat list. Each group has:

- A collapsible header with flag emoji (`Utils.countryFlag()`), country code
  (ISO alpha-2), project count badge, and a bulk visibility toggle.
- An indeterminate checkbox state when only some projects in the group are
  visible.
- Collapse/expand state persisted to `localStorage` under
  `DEFAULTS.STORAGE_KEYS.COUNTRY_COLLAPSED`.
- Country visibility state persisted under
  `DEFAULTS.STORAGE_KEYS.COUNTRY_VISIBILITY`.
- CSS transition at `DEFAULTS.UI.COUNTRY_GROUP_TRANSITION_MS` (250 ms).

#### Two-level visibility

The country toggle acts as a **visibility gate** separate from individual
project toggles:

- A project is visible on the map only when **both** its country gate AND its
  individual toggle are ON.
- Toggling a country OFF does not reset individual project preferences; toggling
  it back ON restores exactly the projects that were individually enabled.
- `State.effectiveProjectVisibility` (`Map<string, boolean>`) tracks the actual
  on-map visibility (set before the map guard in `applyProjectLayerVisibility`).
- `toggleProjectVisibility` clears stale `effectiveProjectVisibility` entries
  before re-applying.
- `getVisibleProjectIds()` reads from `effectiveProjectVisibility`, ensuring
  stations, leads, cylinders, and depth domains all respect the two-level gate.
- `_applyInitialCountryVisibility()` is called during `ProjectPanel.init()` to
  enforce country gates on page load.

If no project has a `country` value, the panel falls back to a flat alphabetical
list (`_renderFlat`). The public viewer always uses the flat fallback because
`setPublicProjects()` does not include `country`.

### Project listing page

`ProjectListingView` groups projects into `projects_by_country` (a
`dict[str, list[ProjectInfoData]]` sorted alphabetically by country name). The
template renders collapsible sections with flag emojis via the `country_flag`
template filter. Collapse state is persisted to `localStorage` under
`DEFAULTS.STORAGE_KEYS.PROJECTS_COUNTRY_COLLAPSED`.

### Country flag utilities

| Context          | Function                                    | Input            |
| ---------------- | ------------------------------------------- | ---------------- |
| Django templates | `country_flag` filter (`project_colors.py`) | ISO alpha-2 code |
| JS (ES modules)  | `Utils.countryFlag(code)` (`utils.ts`)      | ISO alpha-2 code |

Both convert a two-letter code to the corresponding regional indicator emoji
pair (e.g. `"FR"` -> the French flag emoji).

---

## 11. Landmark Collections

Landmarks always belong to one Landmark Collection. Private Landmarks live in
the user's lazily-created personal collection; collaborative Landmarks live in
shared collections. The private map viewer loads accessible collections before
loading Landmark GeoJSON so create/edit/import flows can offer collection
selectors.

Map behavior:

- Manager rows are grouped by collection and collapsed by default. Group headers
  show the collection label, landmark count, permission state, and color.
- Create from map, manual create, edit, GPX import, and KML/KMZ import can
  assign new Landmarks to collections where the user has WRITE access. The
  default selector value is the user's personal collection.
- Landmark markers and labels use the collection's `color`.
- Read-only collection Landmarks remain visible but edit, delete, and drag
  actions are disabled or rejected before the API call.
- API responses include `can_write` and `can_delete`; the frontend uses these
  server-derived flags instead of reimplementing collection permission logic.

`MAP_SOURCES` order is part of the UI/default contract: it determines menu order
and the first token-satisfied fallback. A registry reorder must update the
order-sensitive available-source and tokenless-default expectations in
`map/sources.test.ts` and the documented list together. Verify the intended
default and manifest-owned output after a clean build.

## Station feature contracts

Station feature declarations distinguish API records from display projections.
The tag owner retains the API tag-array and tag-object identities; mutation
updates the existing station and then its marker/detail display. Its deferred
color initialization calls the original receiver.

Journal and resource forms keep multipart `FormData`, upload progress for files,
and their separate text-only API paths. Successful mutations start the existing
refresh without awaiting it. Resource sorting mutates the fetched array, and
edit/delete operations use its cached records. Replacing the file preview
preserves the selected input and File identity. Photo, video, and note viewers
retain their individual scroll/keyboard lifecycles.

Cylinder fleet availability is cached within an install-modal session and
refetched for the next session. Install/status changes dispatch
`speleo:refresh-cylinder-installs` on Document without an explicit detail value.
Pressure operations refresh the pressure tab. Sensor availability retains its
separate cache and current-sensor editing exception; empty expiries are omitted
on create and serialized by FormData as the literal string `null` on edit.
Sensor sorting/filtering, permission checks, and dynamic State imports remain
owned by the sensor module.

Collocated TypeScript tests characterize API payloads, callback receivers,
response/cache identity, mutation ordering, cancellation, failure settlement,
file-input preservation, and malicious display values. These contracts prevent
shared presentation work from changing transport or lifetime policies.

Station and surface-station manager composition remains separate in
`stations/ui.ts` and `surface_stations/ui.ts`. Both retain return-focus
forwarding and context-preserving details navigation. Subsurface creation uses
the existing snapping result; surface creation reads writable networks and
validates coordinate bounds. The details module owns family/parent context,
clones tab controls during initialization, and retains the supplied navigation
handler object. Tests exercise both families, absent DOM, permission-negative
creation, malformed station types, submission values, and callback ordering.
