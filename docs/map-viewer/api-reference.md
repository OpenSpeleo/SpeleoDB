# Map Viewer API Reference

> Agent-focused documentation covering the frontend API client and all
> backend endpoint groups consumed by the SpeleoDB map viewer.

---

## 1. Frontend API Client

**Module:** `frontend_private/static/private/js/map_viewer/api.js`

### Overview

The `API` object is a thin wrapper around `fetch`, providing a uniform
interface for all backend calls. Every method delegates to a private
`apiRequest(url, method, body, isFormData)` function.

### Authentication

- **CSRF tokens** — every request includes an `X-CSRFToken` header
  obtained via `Utils.getCSRFToken()` (reads the `csrftoken` cookie).
- **Session auth** — `credentials: 'same-origin'` is set on every
  request, relying on Django's session middleware.
- No Bearer/JWT tokens are used in the private viewer.

### Request handling

- `Content-Type` defaults to `application/json`; when `isFormData` is
  `true` the header is omitted so the browser sets the multipart
  boundary automatically.
- Bodies are `JSON.stringify`'d unless `isFormData` is `true`, in which
  case the raw `FormData` object is passed.

### Response handling

- **204 No Content** — returns `{ ok: true, status: 204 }`.
- **Success (2xx)** — returns parsed JSON.
- **Error (4xx/5xx)** — throws an `Error` with the server's
  `message`, `error`, or `detail` field. The error object is augmented
  with `.data` (full response body) and `.status` (HTTP status code).

### URL resolution

Endpoint URLs are resolved at runtime via Django's `Urls` global
(provided by `django-js-reverse`). Each API method references a named
URL pattern, e.g. `Urls['api:v1:project-stations'](projectId)`.

---

## 2. Backend Endpoint Groups

All endpoints live under the `/api/v1/` prefix. The root URL router is
`speleodb/api/v1/urls/__init__.py`.

### 2.1 Projects & GeoJSON

**URL file:** `speleodb/api/v1/urls/project.py`

| Method | URL Pattern                                         | Name                          | Description                        |
|--------|-----------------------------------------------------|-------------------------------|------------------------------------|
| GET    | `/api/v1/projects/`                                 | `projects`                    | List all accessible projects       |
| GET    | `/api/v1/projects/geojson/`                         | `all-projects-geojson`        | All projects as GeoJSON            |
| GET    | `/api/v1/projects/<id>/`                            | `project-detail`              | Single project detail              |
| GET    | `/api/v1/projects/<id>/geojson/`                    | `project-geojson-commits`     | Project GeoJSON with commits       |
| GET    | `/api/v1/projects/<id>/revisions/`                  | `project-revisions`           | Git revision history               |
| GET    | `/api/v1/projects/<id>/git_explorer/<hexsha>/`      | `project-gitexplorer`         | Browse project at specific commit  |
| GET    | `/api/v1/projects/<id>/permissions/user/`           | `project-user-permissions`    | List user permissions              |
| *      | `/api/v1/projects/<id>/permission/user/detail/`     | `project-user-permissions-detail` | Manage specific user permission |
| GET    | `/api/v1/projects/<id>/permissions/team/`           | `project-team-permissions`    | List team permissions              |
| *      | `/api/v1/projects/<id>/permission/team/detail/`     | `project-team-permissions-detail` | Manage specific team permission |
| POST   | `/api/v1/projects/<id>/acquire/`                    | `project-acquire`             | Acquire project mutex              |
| POST   | `/api/v1/projects/<id>/release/`                    | `project-release`             | Release project mutex              |
| PUT    | `/api/v1/projects/<id>/upload/<fileformat>/`        | `project-upload`              | Upload file to project             |
| GET    | `/api/v1/projects/<id>/download/blob/<hexsha>/`     | `project-download-blob`       | Download specific blob             |
| GET    | `/api/v1/projects/<id>/download/<fileformat>/`      | `project-download`            | Download project in format         |
| GET    | `/api/v1/projects/<id>/download/<fileformat>/<hexsha>/` | `project-download-at-hash` | Download project at commit         |

#### Project-scoped sub-resources

| Method | URL Pattern                                                | Name                                | Description                        |
|--------|------------------------------------------------------------|-------------------------------------|------------------------------------|
| GET/POST | `/api/v1/projects/<id>/stations/`                       | `project-stations`                  | List/create project stations       |
| GET    | `/api/v1/projects/<id>/stations/geojson/`                  | `project-stations-geojson`          | Project stations as GeoJSON        |
| GET/POST | `/api/v1/projects/<id>/exploration-leads/`              | `project-exploration-leads`         | List/create project leads          |
| GET    | `/api/v1/projects/<id>/exploration-leads/geojson/`         | `project-exploration-leads-geojson`  | Project leads as GeoJSON           |

### 2.2 Stations

**URL file:** `speleodb/api/v1/urls/station.py`

#### Global station endpoints

| Method    | URL Pattern                                        | Name                          | Description                          |
|-----------|----------------------------------------------------|-------------------------------|--------------------------------------|
| GET       | `/api/v1/stations/subsurface/`                     | `subsurface-stations`         | All subsurface stations              |
| GET       | `/api/v1/stations/subsurface/geojson/`             | `subsurface-stations-geojson` | All subsurface stations as GeoJSON   |
| GET       | `/api/v1/stations/surface/`                        | `surface-stations`            | All surface stations                 |
| GET       | `/api/v1/stations/surface/geojson/`                | `surface-stations-geojson`    | All surface stations as GeoJSON      |

#### Single-station endpoints (nested under `/api/v1/stations/<id>/`)

| Method      | URL Pattern                                           | Name                            | Description                           |
|-------------|-------------------------------------------------------|---------------------------------|---------------------------------------|
| GET/PATCH/DELETE | `/api/v1/stations/<id>/`                         | `station-detail`                | Station CRUD                          |
| GET/POST    | `/api/v1/stations/<id>/resources/`                    | `station-resources`             | List/create station resources         |
| GET/POST    | `/api/v1/stations/<id>/logs/`                         | `station-logs`                  | List/create station log entries       |
| POST/DELETE | `/api/v1/stations/<id>/tags/`                         | `station-tags-manage`           | Assign/remove tag from station        |
| GET/POST    | `/api/v1/stations/<id>/sensor-installs/`              | `station-sensor-installs`       | List/create sensor installs           |
| GET         | `/api/v1/stations/<id>/sensor-installs/export/excel/` | `station-sensor-installs-export`| Export sensor installs as Excel       |
| GET/PATCH   | `/api/v1/stations/<id>/sensor-installs/<install_id>/` | `station-sensor-install-detail` | Sensor install detail                 |
| GET         | `/api/v1/stations/<id>/experiment/<exp_id>/records/`  | `experiment-records`            | Experiment records for station        |

#### Surface network stations

**URL file:** `speleodb/api/v1/urls/surface_network.py`

| Method    | URL Pattern                                                      | Name                      | Description                          |
|-----------|------------------------------------------------------------------|---------------------------|--------------------------------------|
| GET       | `/api/v1/surface-networks/`                                      | `surface-networks`        | List all surface networks            |
| GET       | `/api/v1/surface-networks/<network_id>/`                         | `surface-network`         | Network detail                       |
| GET       | `/api/v1/surface-networks/<network_id>/permissions/`             | `surface-network-permissions` | Network permissions              |
| GET/POST  | `/api/v1/surface-networks/<network_id>/stations/`                | `network-stations`        | List/create network stations         |
| GET       | `/api/v1/surface-networks/<network_id>/stations/geojson/`        | `network-stations-geojson`| Network stations as GeoJSON          |

### 2.3 Station Tags

**URL file:** `speleodb/api/v1/urls/station_tag.py`

| Method    | URL Pattern                          | Name                | Description                |
|-----------|--------------------------------------|---------------------|----------------------------|
| GET/POST  | `/api/v1/station_tags/`              | `station-tags`      | List/create user tags      |
| GET       | `/api/v1/station_tags/colors/`       | `station-tag-colors` | Available tag color palette |
| GET/PATCH/DELETE | `/api/v1/station_tags/<id>/`  | `station-tag-detail` | Tag CRUD                   |

### 2.4 Exploration Leads

**URL file:** `speleodb/api/v1/urls/exploration_lead.py`

| Method         | URL Pattern                             | Name                           | Description                       |
|----------------|-----------------------------------------|--------------------------------|-----------------------------------|
| GET/PATCH/DELETE | `/api/v1/exploration-leads/<id>/`     | `exploration-lead-detail`      | Single lead CRUD                  |
| GET            | `/api/v1/exploration-leads/geojson/`    | `exploration-lead-all-geojson` | All leads as GeoJSON (cross-project) |

Project-scoped lead endpoints are under the project prefix (see Section 2.1).

### 2.5 Landmarks

**URL file:** `speleodb/api/v1/urls/landmark.py`

| Method         | URL Pattern                     | Name               | Description                   |
|----------------|---------------------------------|--------------------|-------------------------------|
| GET/POST       | `/api/v1/landmarks/`            | `landmarks`        | List/create user landmarks    |
| GET            | `/api/v1/landmarks/geojson/`    | `landmarks-geojson`| All user landmarks as GeoJSON |
| GET/PATCH/DELETE | `/api/v1/landmarks/<id>/`     | `landmark-detail`  | Landmark CRUD                 |

Landmarks are **user-scoped** — each user sees only their own landmarks.

### 2.6 GPS Tracks

**URL file:** `speleodb/api/v1/urls/gps_track.py`

| Method    | URL Pattern                       | Name              | Description                    |
|-----------|-----------------------------------|--------------------|-------------------------------|
| GET       | `/api/v1/gps_tracks/`             | `gps-tracks`       | List user's GPS tracks        |
| GET       | `/api/v1/gps_tracks/<id>/`        | `gps-track-detail` | Single track detail/GeoJSON   |

#### GPX Import

**URL file:** `speleodb/api/v1/urls/file_import.py`

| Method | URL Pattern               | Name          | Description                |
|--------|---------------------------|---------------|----------------------------|
| PUT    | `/api/v1/import/gpx/`     | `gpx-import`  | Import GPX file as track   |
| PUT    | `/api/v1/import/kml_kmz/` | `kml-kmz-import` | Import KML/KMZ file     |

### 2.7 Cylinder Installs

**URL file:** `speleodb/api/v1/urls/cylinder_install.py`

| Method         | URL Pattern                                                        | Name                              | Description                          |
|----------------|--------------------------------------------------------------------|-----------------------------------|--------------------------------------|
| GET/POST       | `/api/v1/cylinder-installs/`                                       | `cylinder-installs`               | List/create cylinder installs        |
| GET            | `/api/v1/cylinder-installs/geojson/`                               | `cylinder-installs-geojson`       | All installs as GeoJSON              |
| GET/PATCH/DELETE | `/api/v1/cylinder-installs/<install_id>/`                        | `cylinder-install-detail`         | Install CRUD                         |
| GET/POST       | `/api/v1/cylinder-installs/<install_id>/pressure-checks/`          | `cylinder-install-pressure-checks`| List/create pressure checks          |
| GET/PATCH/DELETE | `/api/v1/cylinder-installs/<install_id>/pressure-checks/<check_id>/` | `cylinder-pressure-check-detail` | Pressure check CRUD              |

#### Cylinder Fleets (management)

| Frontend method                    | HTTP | Description                       |
|------------------------------------|------|-----------------------------------|
| `API.getCylinderFleets()`          | GET  | List cylinder fleets              |
| `API.getCylinderFleetDetails(id)`  | GET  | Fleet detail                      |
| `API.getCylinderFleetCylinders(id)`| GET  | Cylinders in a fleet              |

### 2.8 GIS Views

**URL file:** `speleodb/api/v1/urls/gis_view.py`

| Method | URL Pattern                    | Name           | Description                     |
|--------|--------------------------------|----------------|---------------------------------|
| GET    | `/api/v1/gis_view/<id>/`      | `gis-view-data`| Fetch GIS view configuration    |

GIS Views are saved map configurations (center, zoom, visible layers)
that can be shared via a public token.

### 2.9 Logs & Resources (standalone)

| Method         | URL Pattern                 | Name             | Description                |
|----------------|-----------------------------|------------------|----------------------------|
| GET/PATCH/DELETE | `/api/v1/logs/<id>/`      | `log-detail`     | Single log entry CRUD      |
| GET/PATCH/DELETE | `/api/v1/resources/<id>/` | `resource-detail`| Single resource CRUD       |

These complement the station-nested endpoints and allow direct access
by log/resource UUID.

### 2.10 Sensor Fleets

| Frontend method                         | HTTP | Description                  |
|-----------------------------------------|------|------------------------------|
| `API.getSensorFleets()`                 | GET  | List sensor fleets           |
| `API.getSensorFleetDetails(fleetId)`    | GET  | Fleet detail                 |
| `API.getSensorFleetSensors(fleetId)`    | GET  | Sensors in a fleet           |

### 2.11 Experiments

| Frontend method                              | HTTP | Description                       |
|----------------------------------------------|------|-----------------------------------|
| `API.getExperiments()`                       | GET  | List all experiments              |
| `API.getExperimentData(stationId, expId)`    | GET  | Experiment records for a station  |

---

## 3. OGC API Endpoints

**URL file:** `speleodb/api/v1/urls/gis.py`
**Namespace:** `gis-ogc`
**Base path:** `/api/v1/gis-ogc/`

These endpoints implement the [OGC API - Features](https://ogcapi.ogc.org/features/)
standard, enabling interoperability with GIS clients like QGIS.

### 3.1 View endpoints (public, `gis_token`-based)

Used by the **public map viewer** and external GIS clients. Access is
granted via a `gis_token` embedded in the URL — no session authentication
required.

| Method | URL Pattern                                          | Name                   | Description                            |
|--------|------------------------------------------------------|------------------------|----------------------------------------|
| GET    | `/api/v1/gis-ogc/view/<gis_token>/`                 | `view-landing`         | OGC landing page (service discovery)   |
| GET    | `/api/v1/gis-ogc/view/<gis_token>/conformance`      | `view-conformance`     | OGC conformance declaration            |
| GET    | `/api/v1/gis-ogc/view/<gis_token>`                  | `view-data`            | Collections list                       |
| GET    | `/api/v1/gis-ogc/view/<gis_token>/geojson`           | `view-geojson`         | GeoJSON for frontend map viewer        |
| GET    | `/api/v1/gis-ogc/view/<gis_token>/<commit_sha>`      | `view-collection`      | Single collection metadata             |
| GET    | `/api/v1/gis-ogc/view/<gis_token>/<commit_sha>/items` | `view-collection-items` | Collection items (filtered GeoJSON)   |

### 3.2 User endpoints (public, `user_token`-based)

Provide per-user access to all projects the token owner can see. Intended
for personal QGIS connections.

| Method | URL Pattern                                              | Name               | Description                        |
|--------|----------------------------------------------------------|--------------------|------------------------------------|
| GET    | `/api/v1/gis-ogc/user/<key>/`                            | `user-landing`     | OGC landing page                   |
| GET    | `/api/v1/gis-ogc/user/<key>/conformance`                 | `user-conformance` | OGC conformance declaration        |
| GET    | `/api/v1/gis-ogc/user/<key>`                              | `user-data`        | Collections list (user's projects) |
| GET    | `/api/v1/gis-ogc/user/<key>/<commit_sha>`                 | `user-collection`  | Single collection metadata         |
| GET    | `/api/v1/gis-ogc/user/<key>/<commit_sha>/items`           | `user-collection-items` | Collection items (GeoJSON)    |

### 3.3 Experiment endpoint

| Method | URL Pattern                                    | Name         | Description                   |
|--------|------------------------------------------------|--------------|-------------------------------|
| GET    | `/api/v1/gis-ogc/experiment/<gis_token>/`      | `experiment` | Experiment data via GIS token |

---

## 4. Authentication Model

### Private viewer (session-based)

The private map viewer (`main.js`) relies on Django session
authentication:

1. User logs in via the Django auth system (session cookie set).
2. Every API request includes `credentials: 'same-origin'` to send the
   session cookie.
3. A CSRF token is included via the `X-CSRFToken` header (read from the
   `csrftoken` cookie by `Utils.getCSRFToken()`).
4. Permission checks happen server-side per the project/network
   permission matrix. The frontend pre-loads the permission map into
   `Config` and uses `Config.hasProjectAccess()` /
   `Config.hasScopedAccess()` to gate UI actions client-side before
   making API calls.

### Public viewer (token-based)

The public map viewer (`gis_view_main.js`) uses token-based
authentication:

1. A **GIS view token** (`gis_token`) is embedded in the URL.
2. The token grants read-only access to the specific GIS view's data.
3. No session cookie or CSRF token is required.
4. The public viewer calls the OGC `view-geojson` endpoint:
   `GET /api/v1/gis-ogc/view/<gis_token>/geojson`.

### OGC/QGIS access (token-based)

External GIS clients (e.g., QGIS) connect via:

- **View tokens** (`gis_token`) — access a single shared view.
- **User tokens** (`user_token`) — access all projects the user has
  permission to see.

Both token types are embedded in the URL path, not as headers or query
params. The OGC endpoints follow the OGC API - Features standard,
providing landing pages, conformance declarations, collections lists,
and item endpoints that QGIS auto-discovers.
