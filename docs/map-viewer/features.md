# Map Viewer Features

> Agent-focused documentation for the SpeleoDB map viewer feature set.
> Covers engineering intent, module boundaries, and behavioral contracts.

The private map viewer entrypoint is
`frontend_private/static/private/js/map_viewer/main.js`.
The public viewer entrypoint is `frontend_public/static/js/gis_view_main.js`.
Both share the same underlying modules; the public viewer exposes a
read-only, token-authenticated subset.

---

## 1. Station Management

### 1.1 Subsurface Stations

**Module:** `stations/manager.js`

Subsurface stations are **project-scoped**. Each station belongs to exactly
one project and carries a UUID, lat/lng coordinates, and an optional
`subsurface_type` discriminator.

#### Subsurface types

| Type       | Layer suffix       | Icon key     |
|------------|--------------------|--------------|
| `sensor`   | `-circles`         | `sensor`     |
| `biology`  | `-biology-icons`   | `biology`    |
| `bone`     | `-bone-icons`      | `bone`       |
| `artifact` | `-artifact-icons`  | `artifact`   |
| `geology`  | `-geology-icons`   | `geology`    |

Plain sensor stations render as circles; the remaining types render as
custom icon images loaded from `window.MAPVIEWER_CONTEXT.icons`.

#### Data loading strategy

`StationManager.ensureAllStationsLoaded()` fetches **all** subsurface
stations visible to the current user in a single
`GET /api/v1/stations/subsurface/geojson/` call, then caches the
`FeatureCollection` in the module-level `allStationsGeoJson` variable.
Project-specific views (`loadStationsForProject`) filter the cached
collection client-side.  The cache is invalidated on any create/delete
mutation via `invalidateCache()`.

#### CRUD operations

| Operation | Manager method                     | API method                  | HTTP verb |
|-----------|------------------------------------|-----------------------------|-----------|
| Create    | `createStation(projectId, data)`   | `API.createStation`         | `POST`    |
| Read      | `loadStationsForProject(projectId)`| `API.getAllStationsGeoJSON`  | `GET`     |
| Update    | `updateStation(stationId, data)`   | `API.updateStation`         | `PATCH`   |
| Delete    | `deleteStation(stationId)`         | `API.deleteStation`         | `DELETE`  |
| Move      | `moveStation(stationId, coords)`   | (calls `updateStation`)     | `PATCH`   |

After every mutation the manager invalidates its cache and calls
`Layers.refreshStationsAfterChange(projectId)` to redraw the map layer.
`moveStation` includes a visual-revert path: if the API call fails, the
station is snapped back to its original coordinates on the map via
`Layers.updateStationPosition`.

#### Permission gating

Station loading is skipped when the user lacks `read` access on the
project (`Config.hasProjectAccess(projectId, 'read')`).  Drag-to-move
requires `write` access checked via
`Config.hasScopedAccess('project', projectId, 'write')`.

### 1.2 Surface Stations

**Module:** `surface_stations/manager.js`

Surface stations are **network-scoped** (belong to a
`SurfaceMonitoringNetwork`, not a project). They render as diamond symbols
on layers prefixed `surface-stations-`.  The data loading strategy mirrors
subsurface stations: a single `GET /api/v1/stations/surface/geojson/` call
returns all surface stations, which are filtered by network client-side.

Surface stations are managed via:

| API method                          | HTTP  | URL pattern                                        |
|-------------------------------------|-------|----------------------------------------------------|
| `API.createSurfaceStation`          | POST  | `/api/v1/surface-networks/<network_id>/stations/`  |
| `API.getNetworkStationsGeoJSON`     | GET   | `/api/v1/surface-networks/<network_id>/stations/geojson/` |
| `API.getAllSurfaceStationsGeoJSON`   | GET   | `/api/v1/stations/surface/geojson/`                |

### 1.3 Station Details Modal

**Module:** `stations/details.js`

The details modal is opened via `StationDetails.openModal(stationId,
parentId, isNewlyCreated, stationType)`. It tracks both subsurface and
surface stations with a `currentStationType` discriminator (`'subsurface'`
or `'surface'`).

#### Tabs

| Tab            | Sub-module               | Description                                         |
|----------------|--------------------------|-----------------------------------------------------|
| **Details**    | inline in `details.js`   | Name, description, type badge, coordinates, dates   |
| **Logs**       | `stations/logs.js`       | Timestamped field-log entries with optional images   |
| **Resources**  | `stations/resources.js`  | File attachments (photos, documents, data files)     |
| **Sensors**    | `stations/sensors.js`    | Sensor install history, fleet integration, Excel export |
| **Experiments**| `stations/experiments.js`| Experiment records linked to the station             |

The active tab is tracked via the module-level `activeTab` variable
(default `'details'`).

### 1.4 Station Tags

**Module:** `stations/tags.js`

Tags provide **user-defined color coding** for stations. Each user can
create named tags with one of 20 predefined colors (fetched from
`API.getTagColors()`; fallback palette hardcoded in `FALLBACK_COLORS`).

Key operations:

- `StationTags.init()` — loads tags and colors in parallel.
- `StationTags.openTagSelector(stationId)` — renders a modal overlay
  allowing the user to assign/create/remove a tag.
- `API.setStationTag(stationId, tagId)` / `API.removeStationTag(stationId)`
  — server-side assignment.
- Tags apply to both subsurface and surface stations (state lookup checks
  both `State.allStations` and `State.allSurfaceStations`).

Tag color is reflected on the map by updating the station's `color`
property in the GeoJSON source data.

---

## 2. Landmark Management

**Module:** `landmarks/manager.js`

Landmarks are **user-scoped** (personal to the authenticated user, not
project-scoped). Every authenticated user sees only their own landmarks.

### Data loading

`LandmarkManager.loadAllLandmarks()` calls
`API.getAllLandmarksGeoJSON()` and populates `State.allLandmarks`.
Properties stored per landmark: `id`, `name`, `description`,
`latitude`, `longitude`, `coordinates`, `created_by`, `creation_date`.

### CRUD operations

| Operation | Manager method                      | API method              | HTTP  |
|-----------|-------------------------------------|-------------------------|-------|
| Create    | `createLandmark(data)`              | `API.createLandmark`    | POST  |
| Update    | `updateLandmark(landmarkId, data)`  | `API.updateLandmark`    | PATCH |
| Delete    | `deleteLandmark(landmarkId)`        | `API.deleteLandmark`    | DELETE|
| Move      | `moveLandmark(landmarkId, coords)`  | (calls `updateLandmark`)| PATCH |

After every mutation the full landmark set is reloaded and the layer is
redrawn via `Layers.addLandmarkLayer(featureCollection)` followed by
`Layers.reorderLayers()` to ensure landmarks render on top.

### Drag-to-move with confirmation

Landmarks support drag-to-move. Unlike stations, landmarks **do not** snap
to survey lines — they are placed freely on the map. On drag end, the
`onLandmarkDragEnd` handler fires with `(landmarkId, newCoords,
originalCoords)`, and a confirmation modal is shown. On cancel, the
landmark reverts to its original position via
`Layers.revertLandmarkPosition`.

---

## 3. Exploration Leads

**Module:** `exploration_leads/manager.js`

Exploration leads are **project-scoped** markers that indicate promising
areas for future exploration. They are placed at survey line endpoints
(magnetic snap-to-line required; see Section 6).

### Data loading strategy

Identical to `StationManager`: a single
`GET /api/v1/exploration-leads/geojson/` call fetches all leads into a
module-level `allLeadsGeoJson` cache. `loadLeadsForProject(projectId)`
filters client-side. The cache is invalidated after create/delete
operations.

### Permission gating

- Loading requires `read` access on the project.
- Projects with only `WEB_VIEWER` permission are excluded.
- Drag-to-move requires `write` access checked by the interaction layer
  (`Config.hasScopedAccess('project', projectId, 'write')`).

### CRUD operations

| Operation | Manager method                                | API method                     | HTTP   |
|-----------|-----------------------------------------------|--------------------------------|--------|
| Create    | `createLead(projectId, coordinates, description)` | `API.createExplorationLead` | POST   |
| Read      | `loadLeadsForProject(projectId)`              | `API.getAllProjectExplorationLeadsGeoJSON` | GET |
| Update    | `updateLead(leadId, data)`                    | `API.updateExplorationLead`    | PATCH  |
| Delete    | `deleteLead(leadId)`                          | `API.deleteExplorationLead`    | DELETE |
| Move      | `moveLead(leadId, newCoords)`                 | (calls `updateLead`)           | PATCH  |

Coordinates are stored with 7 decimal places of precision
(`toFixed(7)`).

---

## 4. GPS Tracks

**Module:** `components/gps_tracks_panel.js`

GPS tracks are **user-owned** track files. The panel is only rendered if
`Config.gpsTracks.length > 0`.

### Architecture

- Track metadata is provided via `Config.gpsTracks` (populated from the
  server-rendered context).
- Track GeoJSON data is loaded **on demand** when the user activates a
  track via the panel toggle.
- Loaded track data is **lazily cached** in `State.gpsTrackCache`
  (keyed by track ID as string).
- Track bounds are stored in `State.gpsTrackBounds` for the fly-to-track
  feature.

### GPX import

New tracks are imported via `API.importGPX(formData)` which hits
`PUT /api/v1/import/gpx/`. The server converts GPX to GeoJSON for storage.

### Panel behavior

- The panel positions itself below the project panel (expanded or
  minimized), observing DOM mutations to reposition dynamically.
- Each track item shows: color dot, name (truncated at 30 chars),
  loading spinner (when fetching), and a toggle switch.
- Clicking the track card body activates the track and flies to its
  bounds (`fitBounds` with padding 50, maxZoom 16).
- Colors are assigned via `Colors.getGPSTrackColor(trackId)`.

### Visibility control

`Layers.toggleGPSTrackVisibility(trackId, isVisible, trackUrl)` handles
both fetching (if not cached) and showing/hiding the track layer.

---

## 5. Cylinder Installs

Cylinder installs track **safety cylinders** (e.g., breathing gas
cylinders placed underground for emergency use).

### Data model

- **Cylinder Fleet** — a fleet/group of cylinders.
- **Cylinder** — an individual physical cylinder.
- **Cylinder Install** — a placement record linking a cylinder to a
  geographic location (with a station or standalone coordinates).
- **Pressure Check** — a timestamped pressure reading for an installed
  cylinder.

### Map integration

Cylinder installs render as a dedicated `cylinder-installs-layer`.
GeoJSON is fetched via `API.getAllCylinderInstallsGeoJSON()` at
`GET /api/v1/cylinder-installs/geojson/`.

Cylinder installs support:
- Click to view details (`onCylinderInstallClick` handler).
- Drag-to-move with magnetic snap-to-line behavior (same as stations).
- Right-click context menu.
- Write permission is checked per project for drag operations.

### API surface

| API method                          | HTTP   | Description                              |
|-------------------------------------|--------|------------------------------------------|
| `getCylinderInstalls(params)`       | GET    | List installs, optional query filters    |
| `getCylinderInstallsGeoJSON()`      | GET    | GeoJSON for map rendering                |
| `createCylinderInstall(data)`       | POST   | Create new install                       |
| `getCylinderInstallDetails(id)`     | GET    | Single install detail                    |
| `updateCylinderInstall(id, data)`   | PATCH  | Update install                           |
| `deleteCylinderInstall(id)`         | DELETE | Remove install                           |
| `getCylinderPressureChecks(id)`     | GET    | List pressure checks for an install      |
| `createCylinderPressureCheck(id, d)`| POST   | Record a pressure check                  |
| `updateCylinderPressureCheck(...)`  | PATCH  | Update a pressure check                  |
| `deleteCylinderPressureCheck(...)`  | DELETE | Remove a pressure check                  |

---

## 6. Drag-and-Drop System

**Module:** `map/interactions.js`, `map/geometry.js`

The drag system handles repositioning of stations, landmarks, cylinder
installs, and exploration leads on the map.

### Drag threshold

A `DRAG_THRESHOLD` of 10 pixels prevents accidental drags from firing on
simple clicks. The threshold is calculated as Euclidean pixel distance
from the mousedown point.

### Drag types and snap behavior

| Drag type            | Snaps to survey lines | Visual feedback during drag          |
|----------------------|-----------------------|--------------------------------------|
| `station`            | Yes                   | Color change: green (snapped) / amber (free) |
| `cylinder-install`   | Yes                   | Highlight circle: green/amber        |
| `exploration-lead`   | Yes                   | Highlight circle: green/amber        |
| `landmark`           | No                    | Free drag, no snap indicator         |

The `SNAPPABLE_TYPES` constant defines which types participate in
magnetic snapping: `['station', 'cylinder-install', 'exploration-lead']`.

### Magnetic snap-to-line

**Module:** `map/geometry.js`

`Geometry.findMagneticSnapPoint(coords, excludeFeatureId)` searches
cached survey line endpoints for the nearest point within
`MAGNETIC_SNAP_RADIUS` (default 10 meters). Distance is computed using
the Haversine formula.

Snap points are cached per project in `snapPointsCache`. The cache is
populated by `Geometry.cacheLineFeatures(projectId, geojsonData)` which
extracts start and end vertices of every `LineString` feature.

The snap indicator (a visual dot on the map) is shown/hidden via
`Geometry.showSnapIndicator(coords, map, isSnapped)` /
`Geometry.hideSnapIndicator()`.

### Confirmation flow

On drag end, a confirmation modal is presented:
1. **Snapped position** — shows which survey line endpoint the feature
   snapped to.
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

**Module:** `components/context_menu.js`

A right-click context menu provides actions on map features.

### Supported targets

| Target               | `type` string        | Data passed to handler         |
|----------------------|----------------------|--------------------------------|
| Subsurface station   | `'station'`          | `{ id, feature, stationType }` |
| Surface station      | `'surface-station'`  | `{ id, feature, stationType }` |
| Landmark             | `'landmark'`         | `{ id, feature }`              |
| Cylinder install     | `'cylinder-install'` | `{ id, feature }`              |
| Exploration lead     | `'exploration-lead'` | `{ id, feature }`              |
| Map background       | `'map'`              | `{ coordinates }`              |

### Menu item structure

Each item can have: `label`, `subtitle`, `icon` (HTML markup),
`disabled` (boolean), `onClick` (callback). The separator `'-'` renders
a visual divider.

### Icon caching for performance

Icons referenced in menu item markup (via `src=` attributes) are
prefetched and converted to data-URLs at initialization
(`prefetchKnownIcons`) and before each `show()` call
(`prefetchIconsFromItems`). Cached data-URLs are stored in
`iconDataUrlCache` (a `Map`). The `getCachedIconMarkup(markup)` method
rewrites `src` attributes to use cached data-URLs, eliminating
redundant network fetches.

### Positioning

`getClampedPosition(clickX, clickY, menuRect, viewportPadding)` ensures
the menu stays within viewport bounds, flipping near edges before
clamping.

### Dismissal

The menu hides on any document click or the Escape key.

---

## 8. Component Library

### 8.1 Modals

**Module:** `components/modal.js`

Confirmation and input modals used by the drag system, deletion
confirmations, and CRUD workflows. Modals are rendered as fixed overlays
with backdrop blur.

### 8.2 Notifications

**Module:** `components/notification.js`

Toast-style notifications for success/error/info feedback after
operations (station created, drag confirmed, API errors, etc.).

### 8.3 Upload with Progress

**Module:** `components/upload.js`

File upload component used for station resources, log entry attachments,
and GPX imports. Supports FormData submission with progress tracking via
the `isFormData` flag in `apiRequest`.

### 8.4 Project Panel

**Module:** `components/project_panel.js`

Left-side panel listing all projects the user has access to. Supports
expand/collapse with state memory. The GPS Tracks panel positions itself
relative to this panel.

### 8.5 GPS Tracks Panel

**Module:** `components/gps_tracks_panel.js`

See Section 4. Positioned below the project panel, auto-repositions on
project panel expand/collapse via MutationObserver.
