# Map Viewer Data Flow

## GeoJSON Loading Pipeline

Data flows from the Django backend through two phases: metadata fetch, then
per-project GeoJSON loading.

### Phase 1: Metadata Fetch

```
Django Backend
  │
  ├─ GET /api/v1/projects/                    → Config.loadProjects()
  │   Response: { success, data: [{ id, name, permission, ... }] }
  │   Stored in: Config._projects
  │
  ├─ GET /api/v1/surface-networks/            → Config.loadNetworks()
  │   Response: { success, data: [{ id, name, user_permission_level, ... }] }
  │   Stored in: Config._networks
  │
  ├─ GET /api/v1/gps-tracks/                  → Config.loadGPSTracks()
  │   Response: { success, data: [{ id, name, file, ... }] }
  │   Stored in: Config._gpsTracks
  │
  └─ GET /api/v1/all-projects-geojson/        → API.getAllProjectsGeoJSON()
      Response: { success, data: [{ id, geojson_file, ... }] }
      Used for: Config.filterProjectsByGeoJSON()
      Purpose: Identify which projects have GeoJSON data, prune the rest
               from Config._projects so the UI only shows mappable projects
```

### Phase 2: Per-Project Data Loading (Parallel)

After metadata is fetched, data is loaded in parallel for all projects:

```
For each project in Config.projects (parallel via Promise.all):
│
├─ Stations: API.getProjectStations(projectId)
│   → StationManager.loadStationsForProject()
│   → Builds GeoJSON FeatureCollection from station records
│   → Layers.addSubSurfaceStationLayer(projectId, geojson)
│   → Features stored in State.allStations (Map by ID)
│
└─ Survey GeoJSON: fetch(geojsonUrl)     ← URL from metadata phase
    → Layers.addProjectGeoJSON(projectId, url)
    │
    ├─ fetch(url) → raw GeoJSON
    ├─ processGeoJSON(projectId, rawData)
    │   ├─ buildSectionDepthAverageMap()  Compute avg depth per section from Points
    │   ├─ computeProjectDepthDomain()    Extract {min: 0, max} range
    │   │   └─ State.projectDepthDomains.set(pid, domain)
    │   ├─ Stamp depth_val and depth_norm on each LineString feature
    │   └─ Force Z=0 on all coordinates
    │
    ├─ Geometry.cacheLineFeatures()       Extract start/end snap points
    │   └─ snapPointsCache.set(pid, snapPoints[])
    │
    ├─ map.addSource('project-geojson-{id}', data)
    ├─ map.addLayer('project-layer-{id}')       Survey lines
    ├─ map.addLayer('project-labels-{id}')      Section name labels
    ├─ map.addLayer('project-points-{id}')      Entry point stars (★)
    │
    ├─ computeGeoJSONBounds() → State.projectBounds.set()
    │
    └─ Layers.recomputeActiveDepthDomain()
        └─ mergeDepthDomains() across visible projects
        └─ Dispatch speleo:depth-domain-updated
```

### Public Viewer Data Flow

The public viewer has a simpler single-phase pipeline:

```
fetch /api/v1/gis-ogc/view/{gisToken}/geojson
  │
  └─ Response: { success, data: { view_name, projects: [{ id, name, geojson_file }] } }
      │
      ├─ Config.setPublicProjects(projects)    Set read-only project list
      │   All projects get permissions = 'READ_ONLY'
      │
      └─ For each project (parallel):
          └─ Layers.addProjectGeoJSON(projectId, geojsonUrl)
              (same pipeline as private viewer from here)
```

---

## CRUD Operation Flows

All entity types follow the same pattern:

```
User Action (UI)
  │
  ├─ 1. UI Modal opens (station create, landmark edit, etc.)
  │
  ├─ 2. User fills form → submit
  │
  ├─ 3. API call via api.js
  │     └─ apiRequest(url, method, body)
  │         ├─ Attaches CSRF token from cookie
  │         ├─ Sets Content-Type: application/json (or FormData)
  │         └─ Throws on non-2xx response with error.data and error.status
  │
  ├─ 4. On success:
  │     ├─ Update State (e.g., State.allStations.set(id, data))
  │     ├─ Dispatch refresh event (e.g., speleo:refresh-stations)
  │     └─ Show success notification via Utils.showNotification()
  │
  └─ 5. Refresh event handler in main.js:
        ├─ Re-fetch data from API (full reload for entity type)
        ├─ Rebuild map layer with new data
        └─ Layers.reorderLayers()
```

### Subsurface Station CRUD

| Action | API Method | Endpoint | Refresh Event |
|---|---|---|---|
| Create | `POST` | `/api/v1/projects/{projectId}/stations/` | `speleo:refresh-stations` |
| Read | `GET` | `/api/v1/stations/{stationId}/` | — |
| Update | `PATCH` | `/api/v1/stations/{stationId}/` | `speleo:refresh-stations` |
| Delete | `DELETE` | `/api/v1/stations/{stationId}/` | `speleo:refresh-stations` |
| Move (drag) | `PATCH` | `/api/v1/stations/{stationId}/` | `speleo:refresh-stations` |

Move flow includes magnetic snap: `Geometry.findNearestSnapPointWithinRadius()`
checks cached snap points within `MAGNETIC_SNAP_RADIUS` (default 10m). If
snapped, coordinates are adjusted to the nearest survey line vertex.

### Surface Station CRUD

| Action | API Method | Endpoint | Refresh Event |
|---|---|---|---|
| Create | `POST` | `/api/v1/networks/{networkId}/stations/` | `speleo:refresh-surface-stations` |
| Update | `PATCH` | `/api/v1/stations/{stationId}/` | `speleo:refresh-surface-stations` |
| Delete | `DELETE` | `/api/v1/stations/{stationId}/` | `speleo:refresh-surface-stations` |

### Landmark CRUD

| Action | API Method | Endpoint | Refresh Event |
|---|---|---|---|
| Create | `POST` | `/api/v1/landmarks/` | `speleo:refresh-landmarks` |
| Update | `PATCH` | `/api/v1/landmarks/{landmarkId}/` | `speleo:refresh-landmarks` |
| Delete | `DELETE` | `/api/v1/landmarks/{landmarkId}/` | `speleo:refresh-landmarks` |
| Move (drag) | `PATCH` via `LandmarkManager.moveLandmark()` | — | Inline source update |

### Exploration Lead CRUD

| Action | API Method | Endpoint | Refresh Event |
|---|---|---|---|
| Create | `POST` | `/api/v1/projects/{projectId}/exploration-leads/` | Layer refresh inline |
| Update | `PATCH` | `/api/v1/exploration-leads/{leadId}/` | Layer refresh inline |
| Delete | `DELETE` | `/api/v1/exploration-leads/{leadId}/` | Layer refresh inline |
| Move (drag) | `PATCH` via `ExplorationLeadManager.moveLead()` | — | Inline position update |

### Cylinder Install CRUD

| Action | API Method | Endpoint | Refresh Event |
|---|---|---|---|
| Create | `POST` | `/api/v1/cylinder-installs/` | `speleo:refresh-cylinder-installs` |
| Update | `PATCH` | `/api/v1/cylinder-installs/{installId}/` | `speleo:refresh-cylinder-installs` |
| Delete | `DELETE` | `/api/v1/cylinder-installs/{installId}/` | `speleo:refresh-cylinder-installs` |

---

## Refresh Event System

Five custom refresh events drive data reload. Each follows the same pattern:
event dispatched → listener in `main.js` re-fetches from API → layer rebuilt.

### `speleo:refresh-stations`

- **Payload**: `{ projectId }`
- **Dispatched by**: `Layers.refreshStationsAfterChange(projectId)`, called
  after station create/update/delete/move operations
- **Handler**: Re-calls `StationManager.loadStationsForProject(projectId)`,
  then `Layers.addSubSurfaceStationLayer()`, then `Layers.reorderLayers()`
- **Scope**: Single project — only re-fetches stations for the affected project

### `speleo:refresh-surface-stations`

- **Payload**: `{ networkId }`
- **Dispatched by**: `Layers.refreshSurfaceStationsAfterChange(networkId)`
- **Handler**: Re-calls `SurfaceStationManager.loadStationsForNetwork(networkId)`,
  then `Layers.addSurfaceStationLayer()`, then `Layers.reorderLayers()`
- **Scope**: Single network

### `speleo:refresh-landmarks`

- **Payload**: (none)
- **Dispatched by**: Landmark CRUD modules, GPX import
- **Handler**: Re-calls `LandmarkManager.loadAllLandmarks()`, then
  `Layers.addLandmarkLayer()`, then `Layers.reorderLayers()`
- **Scope**: Global — re-fetches all landmarks

### `speleo:refresh-gps-tracks`

- **Payload**: `{ deactivateAll? }`
- **Dispatched by**: GPX import (`upload.js`)
- **Handler**:
  1. `State.gpsTrackCache.clear()` — invalidate all cached GeoJSON
  2. If `deactivateAll`, hide all visible GPS track layers
  3. `Config._gpsTracks = null` — force metadata reload
  4. `Config.loadGPSTracks()` — re-fetch track list from API
  5. `GPSTracksPanel.refreshList()` or `GPSTracksPanel.init()` — rebuild UI
- **Scope**: Global — full cache invalidation and reload

### `speleo:refresh-cylinder-installs`

- **Payload**: (none)
- **Dispatched by**: `cylinders.js` after install/uninstall/pressure-check
  operations
- **Listener target**: `document` (not `window`, unlike other refresh events)
- **Handler**: `Layers.refreshCylinderInstallsLayer()` which calls
  `Layers.loadCylinderInstalls()` — full re-fetch of GeoJSON endpoint
- **Scope**: Global — re-fetches all cylinder installs

---

## Caching Strategies

### GPS Tracks — On-Demand Loading + Cache

GPS track GeoJSON is **not** loaded at initialization. Tracks default to OFF.

```
User toggles track ON
  │
  ├─ State.gpsTrackCache.has(trackId)?
  │
  ├─ NO (first load):
  │   ├─ Layers.setGPSTrackLoading(trackId, true)
  │   │   └─ Dispatches speleo:gps-track-loading-changed → spinner in panel
  │   ├─ fetch(trackUrl) → GeoJSON data
  │   ├─ State.gpsTrackCache.set(trackId, geojsonData)
  │   ├─ Layers.addGPSTrackLayer(trackId, geojsonData)
  │   └─ Layers.setGPSTrackLoading(trackId, false)
  │
  └─ YES (cached):
      └─ Layers.showGPSTrackLayers(trackId, true)
          (just toggles visibility on existing map layers)
```

- **Storage**: `State.gpsTrackCache` (`Map<string, GeoJSON>`)
- **Invalidation**: `State.gpsTrackCache.clear()` on `speleo:refresh-gps-tracks`
- **Persistence**: Session-only. No localStorage. All tracks reset to OFF on
  page reload.

### Snap Points — Computed Once Per Project

When project GeoJSON is loaded, `Geometry.cacheLineFeatures()` extracts the
start and end vertices of every `LineString` feature and caches them for
magnetic snap calculations.

```
Layers.addProjectGeoJSON()
  └─ Geometry.cacheLineFeatures(projectId, geojsonData)
      └─ For each LineString feature:
          ├─ Extract start coordinate (first vertex)
          └─ Extract end coordinate (last vertex)
      └─ snapPointsCache.set(projectId, snapPoints[])
```

- **Storage**: Module-level `snapPointsCache` (`Map<string, SnapPoint[]>`)
- **Used by**: `Geometry.findNearestSnapPointWithinRadius()` during drag
  operations for stations, exploration leads, and cylinder installs
- **Invalidation**: Overwritten when project GeoJSON is reloaded
- **Snap radius**: `MAGNETIC_SNAP_RADIUS = 10` meters (adjustable at runtime
  via `Geometry.setSnapRadius()`)

### Station Data — In-Memory Maps

All station data is kept in `State.allStations` and `State.allSurfaceStations`
as flat `Map<id, stationObject>` lookups.

- **Population**: During `StationManager.loadStationsForProject()` and
  `SurfaceStationManager.loadStationsForNetwork()`, each station is stored
  in the appropriate Map.
- **Used by**: Click handlers (to look up station metadata for modals),
  context menu (to check permissions), drag handlers (to read original coords).
- **Invalidation**: Overwritten on each `speleo:refresh-stations` /
  `speleo:refresh-surface-stations` event.

### Depth Domains — Per-Project + Merged

Depth data is computed during GeoJSON processing and cached at two levels:

```
processGeoJSON(projectId, rawData)
  │
  ├─ buildSectionDepthAverageMap(features)
  │   └─ Point features: group by section_name, compute avg depth
  │
  ├─ computeProjectDepthDomain(processed, sectionDepthAvgMap)
  │   └─ { min: 0, max: maxDepthAcrossAllSections }
  │   └─ State.projectDepthDomains.set(projectId, domain)
  │
  └─ For each LineString: stamp depth_val, depth_norm onto feature.properties
```

When project visibility changes or new projects load:

```
Layers.recomputeActiveDepthDomain()
  │
  ├─ Collect domains from visible projects only
  ├─ mergeDepthDomains(activeDomains) → { min: 0, max: globalMax }
  ├─ State.activeDepthDomain = merged
  │
  └─ Layers.emitDepthDomainUpdated()
      ├─ Dispatches speleo:depth-domain-updated
      └─ Dispatches speleo:depth-data-updated (legacy)
```

- **Per-project storage**: `State.projectDepthDomains` (`Map<string, {min,max}|null>`)
- **Merged storage**: `State.activeDepthDomain` (`{min, max}|null`)
- **Used by**: `Colors.getDepthPaint(depthDomain)` which produces a Mapbox
  `interpolate` expression mapping `depth_val` to a blue→yellow→red gradient
- **Recomputed when**: Project visibility toggled, new GeoJSON loaded, color
  mode switched to depth

### Project-Scoped Marker Visibility

Cylinder installs and exploration leads are stored in global layers but
scoped to projects via a `project_id` property on each feature. When project
visibility changes:

```
Layers.applyProjectScopedMarkerVisibility()
  │
  ├─ Build list of visible project IDs
  ├─ Construct Mapbox filter expression:
  │   ['any',
  │     ['!', ['has', 'project_id']],     ← markers without project scope stay visible
  │     ['==', ['get', 'project_id'], null],
  │     ['in', ['to-string', ['get', 'project_id']], [...visibleIds]]
  │   ]
  │
  └─ Apply filter to: cylinder-installs-layer, cylinder-installs-labels,
                       exploration-leads-layer
```

This avoids rebuilding these layers when project visibility changes — only the
Mapbox filter expression is updated.
