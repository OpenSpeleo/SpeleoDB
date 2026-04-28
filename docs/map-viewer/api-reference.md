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
- **Success (2xx)** — returns parsed JSON **verbatim**. v2 endpoints
  never wrap their payloads in a `{ data, success, url, timestamp }`
  envelope; list endpoints return the array directly, detail endpoints
  return the serialized object directly. The legacy `DRFWrapResponseMiddleware`
  still wraps `/api/v1/` responses for backward compatibility, but v2
  callers must read fields straight off the returned value.
- **Error (4xx/5xx)** — throws an `Error` with the server's
  `message`, `error`, or `detail` field. The error object is augmented
  with `.data` (full response body) and `.status` (HTTP status code).

### URL resolution

Endpoint URLs are resolved at runtime via Django's `Urls` global
(provided by `django-js-reverse`). Each API method references a named
URL pattern, e.g. `Urls['api:v2:project-stations'](projectId)`.

---

## 2. Backend Endpoint Groups

All endpoints live under the `/api/v2/` prefix. The root URL router is
`speleodb/api/v2/urls/__init__.py`.

### 2.1 Projects & GeoJSON

**URL file:** `speleodb/api/v2/urls/project.py`

| Method | URL Pattern                                         | Name                          | Description                        |
|--------|-----------------------------------------------------|-------------------------------|------------------------------------|
| GET    | `/api/v2/projects/`                                 | `projects`                    | List all accessible projects       |
| GET    | `/api/v2/projects/geojson/`                         | `all-projects-geojson`        | All projects as GeoJSON            |
| GET    | `/api/v2/projects/<id>/`                            | `project-detail`              | Single project detail              |
| GET    | `/api/v2/projects/<id>/geojson/`                    | `project-geojson-commits`     | Project GeoJSON with commits       |
| GET    | `/api/v2/projects/<id>/revisions/`                  | `project-revisions`           | Git revision history               |
| GET    | `/api/v2/projects/<id>/git_explorer/<hexsha>/`      | `project-gitexplorer`         | Browse project at specific commit  |
| GET    | `/api/v2/projects/<id>/permissions/user/`           | `project-user-permissions`    | List user permissions              |
| *      | `/api/v2/projects/<id>/permission/user/detail/`     | `project-user-permissions-detail` | Manage specific user permission |
| GET    | `/api/v2/projects/<id>/permissions/team/`           | `project-team-permissions`    | List team permissions              |
| *      | `/api/v2/projects/<id>/permission/team/detail/`     | `project-team-permissions-detail` | Manage specific team permission |
| POST   | `/api/v2/projects/<id>/acquire/`                    | `project-acquire`             | Acquire project mutex              |
| POST   | `/api/v2/projects/<id>/release/`                    | `project-release`             | Release project mutex              |
| PUT    | `/api/v2/projects/<id>/upload/<fileformat>/`        | `project-upload`              | Upload file to project             |
| GET    | `/api/v2/projects/<id>/download/blob/<hexsha>/`     | `project-download-blob`       | Download specific blob             |
| GET    | `/api/v2/projects/<id>/download/<fileformat>/`      | `project-download`            | Download project in format         |
| GET    | `/api/v2/projects/<id>/download/<fileformat>/<hexsha>/` | `project-download-at-hash` | Download project at commit         |

#### Project-scoped sub-resources

| Method | URL Pattern                                                | Name                                | Description                        |
|--------|------------------------------------------------------------|-------------------------------------|------------------------------------|
| GET/POST | `/api/v2/projects/<id>/stations/`                       | `project-stations`                  | List/create project stations       |
| GET    | `/api/v2/projects/<id>/stations/geojson/`                  | `project-stations-geojson`          | Project stations as GeoJSON        |
| GET/POST | `/api/v2/projects/<id>/exploration-leads/`              | `project-exploration-leads`         | List/create project leads          |
| GET    | `/api/v2/projects/<id>/exploration-leads/geojson/`         | `project-exploration-leads-geojson`  | Project leads as GeoJSON           |

### 2.2 Stations

**URL file:** `speleodb/api/v2/urls/station.py`

#### Global station endpoints

| Method    | URL Pattern                                        | Name                          | Description                          |
|-----------|----------------------------------------------------|-------------------------------|--------------------------------------|
| GET       | `/api/v2/stations/subsurface/`                     | `subsurface-stations`         | All subsurface stations              |
| GET       | `/api/v2/stations/subsurface/geojson/`             | `subsurface-stations-geojson` | All subsurface stations as GeoJSON   |
| GET       | `/api/v2/stations/surface/`                        | `surface-stations`            | All surface stations                 |
| GET       | `/api/v2/stations/surface/geojson/`                | `surface-stations-geojson`    | All surface stations as GeoJSON      |

#### Single-station endpoints (nested under `/api/v2/stations/<id>/`)

| Method      | URL Pattern                                           | Name                            | Description                           |
|-------------|-------------------------------------------------------|---------------------------------|---------------------------------------|
| GET/PATCH/DELETE | `/api/v2/stations/<id>/`                         | `station-detail`                | Station CRUD                          |
| GET/POST    | `/api/v2/stations/<id>/resources/`                    | `station-resources`             | List/create station resources         |
| GET/POST    | `/api/v2/stations/<id>/logs/`                         | `station-logs`                  | List/create station log entries       |
| POST/DELETE | `/api/v2/stations/<id>/tags/`                         | `station-tags-manage`           | Assign/remove tag from station        |
| GET/POST    | `/api/v2/stations/<id>/sensor-installs/`              | `station-sensor-installs`       | List/create sensor installs           |
| GET         | `/api/v2/stations/<id>/sensor-installs/export/excel/` | `station-sensor-installs-export`| Export sensor installs as Excel       |
| GET/PATCH   | `/api/v2/stations/<id>/sensor-installs/<install_id>/` | `station-sensor-install-detail` | Sensor install detail                 |
| GET         | `/api/v2/stations/<id>/experiment/<exp_id>/records/`  | `experiment-records`            | Experiment records for station        |

#### Surface network stations

**URL file:** `speleodb/api/v2/urls/surface_network.py`

| Method    | URL Pattern                                                      | Name                      | Description                          |
|-----------|------------------------------------------------------------------|---------------------------|--------------------------------------|
| GET       | `/api/v2/surface-networks/`                                      | `surface-networks`        | List all surface networks            |
| GET       | `/api/v2/surface-networks/<network_id>/`                         | `surface-network`         | Network detail                       |
| GET       | `/api/v2/surface-networks/<network_id>/permissions/`             | `surface-network-permissions` | Network permissions              |
| GET/POST  | `/api/v2/surface-networks/<network_id>/stations/`                | `network-stations`        | List/create network stations         |
| GET       | `/api/v2/surface-networks/<network_id>/stations/geojson/`        | `network-stations-geojson`| Network stations as GeoJSON          |

### 2.3 Station Tags

**URL file:** `speleodb/api/v2/urls/station_tag.py`

| Method    | URL Pattern                          | Name                | Description                |
|-----------|--------------------------------------|---------------------|----------------------------|
| GET/POST  | `/api/v2/station_tags/`              | `station-tags`      | List/create user tags      |
| GET       | `/api/v2/station_tags/colors/`       | `station-tag-colors` | Available tag color palette |
| GET/PATCH/DELETE | `/api/v2/station_tags/<id>/`  | `station-tag-detail` | Tag CRUD                   |

### 2.4 Exploration Leads

**URL file:** `speleodb/api/v2/urls/exploration_lead.py`

| Method         | URL Pattern                             | Name                           | Description                       |
|----------------|-----------------------------------------|--------------------------------|-----------------------------------|
| GET/PATCH/DELETE | `/api/v2/exploration-leads/<id>/`     | `exploration-lead-detail`      | Single lead CRUD                  |
| GET            | `/api/v2/exploration-leads/geojson/`    | `exploration-lead-all-geojson` | All leads as GeoJSON (cross-project) |

Project-scoped lead endpoints are under the project prefix (see Section 2.1).

### 2.5 Landmarks

**URL file:** `speleodb/api/v2/urls/landmark.py`

| Method         | URL Pattern                     | Name               | Description                   |
|----------------|---------------------------------|--------------------|-------------------------------|
| GET/POST       | `/api/v2/landmarks/`            | `landmarks`        | List/create accessible landmarks |
| GET            | `/api/v2/landmarks/geojson/`    | `landmarks-geojson`| Accessible landmarks as GeoJSON |
| GET/PATCH/DELETE | `/api/v2/landmarks/<id>/`     | `landmark-detail`  | Landmark CRUD                 |

All Landmarks belong to a Landmark Collection. Missing collection values on
create/import default to the user's personal collection. Collection READ access
controls visibility; WRITE access controls create, edit, delete, drag, and
reassignment behavior. Standard Landmark responses include `collection`,
`collection_name`, `created_by`, `collection_color`, `can_write`, and
`can_delete`; GeoJSON Landmark properties also include `collection_color`,
which the private map uses for marker and label color.

### 2.6 Landmark Collections

**URL file:** `speleodb/api/v2/urls/landmark_collection.py`

| Method         | URL Pattern                                         | Name                              | Description                    |
|----------------|-----------------------------------------------------|-----------------------------------|--------------------------------|
| GET/POST       | `/api/v2/landmark-collections/`                     | `landmark-collections`            | List/create collections        |
| GET/PUT/PATCH/DELETE | `/api/v2/landmark-collections/<collection_id>/` | `landmark-collection-detail` | Collection CRUD/soft delete    |
| GET/POST/PUT/DELETE | `/api/v2/landmark-collections/<collection_id>/permissions/` | `landmark-collection-permissions` | User permission management |

Collection responses include `color`. Shared collections can update name,
description, and color with WRITE access. Personal collections appear in
authenticated listings, but their private details page does not expose the
name, description, or color form. Permission and deletion management are
disabled for personal collections, but owners can still use the GIS integration
tab for that collection's tokenized OGC endpoint.
`is_active` is internal lifecycle state and is not part of collection or
permission response payloads. Create requests are forced active, update attempts
containing `is_active` are rejected, and inactive collection
object/export/permission routes return 404.

### 2.7 GPS Tracks

**URL file:** `speleodb/api/v2/urls/gps_track.py`

| Method    | URL Pattern                       | Name              | Description                    |
|-----------|-----------------------------------|--------------------|-------------------------------|
| GET       | `/api/v2/gps_tracks/`             | `gps-tracks`       | List user's GPS tracks        |
| GET       | `/api/v2/gps_tracks/<id>/`        | `gps-track-detail` | Single track detail/GeoJSON   |

#### GPX Import

**URL file:** `speleodb/api/v2/urls/file_import.py`

| Method | URL Pattern               | Name          | Description                |
|--------|---------------------------|---------------|----------------------------|
| PUT    | `/api/v2/import/gpx/`     | `gpx-import`  | Import GPX file as track   |
| PUT    | `/api/v2/import/kml_kmz/` | `kml-kmz-import` | Import KML/KMZ file     |

### 2.7 Cylinder Installs

**URL file:** `speleodb/api/v2/urls/cylinder_install.py`

| Method         | URL Pattern                                                        | Name                              | Description                          |
|----------------|--------------------------------------------------------------------|-----------------------------------|--------------------------------------|
| GET/POST       | `/api/v2/cylinder-installs/`                                       | `cylinder-installs`               | List/create cylinder installs        |
| GET            | `/api/v2/cylinder-installs/geojson/`                               | `cylinder-installs-geojson`       | All installs as GeoJSON              |
| GET/PATCH/DELETE | `/api/v2/cylinder-installs/<install_id>/`                        | `cylinder-install-detail`         | Install CRUD                         |
| GET/POST       | `/api/v2/cylinder-installs/<install_id>/pressure-checks/`          | `cylinder-install-pressure-checks`| List/create pressure checks          |
| GET/PATCH/DELETE | `/api/v2/cylinder-installs/<install_id>/pressure-checks/<check_id>/` | `cylinder-pressure-check-detail` | Pressure check CRUD              |

#### Cylinder Fleets (management)

| Frontend method                    | HTTP | Description                       |
|------------------------------------|------|-----------------------------------|
| `API.getCylinderFleets()`          | GET  | List cylinder fleets              |
| `API.getCylinderFleetDetails(id)`  | GET  | Fleet detail                      |
| `API.getCylinderFleetCylinders(id)`| GET  | Cylinders in a fleet              |

### 2.8 GIS Views

**URL file:** `speleodb/api/v2/urls/gis_view.py`

| Method | URL Pattern                    | Name           | Description                     |
|--------|--------------------------------|----------------|---------------------------------|
| GET    | `/api/v2/gis_view/<id>/`      | `gis-view-data`| Fetch GIS view configuration    |

GIS Views are saved map configurations (center, zoom, visible layers)
that can be shared via a public token.

### 2.9 Logs & Resources (standalone)

| Method         | URL Pattern                 | Name             | Description                |
|----------------|-----------------------------|------------------|----------------------------|
| GET/PATCH/DELETE | `/api/v2/logs/<id>/`      | `log-detail`     | Single log entry CRUD      |
| GET/PATCH/DELETE | `/api/v2/resources/<id>/` | `resource-detail`| Single resource CRUD       |

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

**URL file:** `speleodb/api/v2/urls/gis.py`
**Namespace:** `gis-ogc`
**Base path:** `/api/v2/gis-ogc/`
**Architecture:** all four families share a single `OGCFeatureService`
abstraction in `speleodb/api/v2/views/ogc_base.py`, with shared compliance
helpers in `speleodb/gis/ogc_helpers.py`. Each family (project view,
project user, landmark single, landmark user) is a ~60-line concrete
service binding to the same set of generic views.

These endpoints implement the [OGC API - Features 1.0 Core + GeoJSON](https://docs.ogc.org/is/17-069r4/17-069r4.html)
standard, enabling interoperability with GIS clients like QGIS and
ArcGIS Pro.

### Canonical URL surface (uniform across all four families)

Every OGC family exposes the same six routes:

* `<base>` — landing page (the URL users copy into their GIS client).
  **No trailing slash** — see
  `docs/map-viewer/ogc-url-and-geometry-contract.md` §1 for the
  reasoning. Pinned by
  `test_no_ogc_url_pattern_has_inconsistent_trailing_slash`.
* `<base>/conformance` — conformance declaration
* `<base>/collections` — collections list
* `<base>/collections/<id>` — single collection metadata
* `<base>/collections/<id>/items` — feature items
* `<base>/collections/<id>/items/<feature_id>` — single feature

The trailing-slash variants of the landing URL (`view/<token>/`, etc.)
return **404** — Django's `APPEND_SLASH` only adds slashes, so the
hard-break is by design. Users re-copy the URL from the integration
page (which renders the new format automatically through `{% url %}`)
and the next paste works.

**Removed in this release** (April 2026 — ws3a): the old bare-token
aliases (`view/<token>` for collections, `view/<token>/<sha>` for the
collection metadata, etc.) are gone. They violated the OGC discovery
convention by exposing a non-landing URL as the user-facing entry
point.

### Response shape (uniform across all four families)

Every `/items` response includes the OGC-mandated envelope:

```json
{
  "type": "FeatureCollection",
  "links": [
    {"href": "...", "rel": "self", "type": "application/geo+json"},
    {"href": "...", "rel": "collection", "type": "application/json"},
    {"href": "...", "rel": "next"}
  ],
  "timeStamp": "2026-04-26T15:11:31Z",
  "numberMatched": 32,
  "numberReturned": 10,
  "features": [{"type": "Feature", "id": "...", ...}]
}
```

`numberMatched` is the total after `bbox`/`datetime` filtering;
`numberReturned` is the page size. The envelope is built per-request,
NOT cached — `timeStamp` reflects the response generation time per OGC
Req 29, and the `self` href reflects the actual request URL and any
representation-changing query parameters (proxies that rewrite
host/scheme are honoured).

Every collection metadata document includes:

```json
{
  "id": "...",
  "title": "...",
  "itemType": "feature",
  "crs": [
    "http://www.opengis.net/def/crs/OGC/1.3/CRS84",
    "http://www.opengis.net/def/crs/OGC/0/CRS84h"
  ],
  "storageCrs": "http://www.opengis.net/def/crs/OGC/0/CRS84h",
  "extent": {"spatial": {"bbox": [[-180, -90, 180, 90]], ...}},
  "links": [...]
}
```

`CRS84h` (the 3-D variant) is advertised because cave-survey data
carries `Z = depth in metres` as the third coordinate; without it,
ArcGIS Pro silently drops the Z values when it builds the layer schema.

### Query parameters (OGC core)

| Parameter  | Required | Behavior                                                                |
|------------|----------|-------------------------------------------------------------------------|
| `limit`    | optional | `1 <= limit <= 10_000`. Defaults to 10,000. Drives `numberReturned`. Emits `rel:next` link. |
| `offset`   | optional | Non-negative integer. Combines with `limit` for paging.                 |
| `bbox`     | optional | 4 (`min_x,min_y,max_x,max_y`) or 6 numbers (CRS84). Antimeridian-crossing longitudes are supported. Filters features. |
| `datetime` | optional | RFC 3339 instant or `start/end` interval. Validator only — pass-through. |

Malformed values return `400 Bad Request`. Unknown parameters are
silently ignored per OGC §7.15 (server-defined extensions are allowed).
The default response is bounded to 10,000 features; larger collections
must be traversed through the emitted `rel:next` pagination links.

### Geometry-typed collections (one per geometry group)

Each project commit is exposed as **up to two** OGC collections,
one per geometry group actually present in the underlying GeoJSON:

* `<commit-sha>_points` — `Point`, `MultiPoint`
* `<commit-sha>_lines` — `LineString`, `MultiLineString`

A geometry-typed collection is only listed in `/collections` when
the corresponding group has at least one feature in the GeoJSON
(no empty layers in QGIS / ArcGIS Pro). Polygons are intentionally
not part of the contract — SpeleoDB cave-survey data does not
produce them; a stray polygon is dropped with a structured warning.

This split is the universal GIS-client convention: **1 OGC
collection = 1 GIS layer = 1 uniform geometry type**. Every major
platform (QGIS, ArcGIS Pro, GeoServer, pygeoapi, MapServer) enforces
it at the layer-schema level. Serving a mixed-geometry collection
caused QGIS to silently drop one geometry type per layer — the
original empty-layer regression documented in
`tasks/lessons/ogc-arcgis-empty-layers.md`.

The pre-split collection URL `<base>/collections/<sha>` (without
`_points` or `_lines` suffix) returns **`410 Gone`** with a
`Link: rel="alternate"` header listing the geometry-typed
replacements. The body is written for the human user (QGIS /
ArcGIS Pro display it) and asks them to re-add the layer from
their OGC connection. See
`docs/map-viewer/ogc-url-and-geometry-contract.md` §2 for the full
contract and migration story.

### `service-desc` points to a focused OGC OpenAPI document

OGC API - Features 1.0 §7.2.4 (Req 2 `/req/core/root-success`) requires
every landing page to advertise a `rel:service-desc` link to the API
definition. Every OGC family in this service points the link to the
**same** static document at:

```
GET /api/v2/gis-ogc/openapi/
```

(URL name: `api:v2:gis-ogc:openapi`).

This endpoint is **not** the global `/api/schema/` document — that one
is 684 KB and explicitly omits the OGC routes (every OGC view sets
`schema = None`), so advertising it would cost every connecting
ArcGIS Pro / QGIS client a useless ~700 KB download per session.
Instead, the focused document covers ONLY the OGC route surface
(landing / conformance / collections / collection / items / feature
across all four families) and is **pre-built once at import time**.
Every request serves the same bytes from memory.
The document uses `/api/v2/gis-ogc` as its OpenAPI server base so
generated clients resolve `/view/...`, `/user/...`, and Landmark paths
to the real mounted API URLs.

Caching:

* `Cache-Control: public, max-age=31536000, must-revalidate` — clients
  hold the document for one year.
* Strong `ETag` derived from the SHA-256 of the canonical JSON bytes.
  Across deploys, if the document content does not change, the ETag
  does not change, and conditional requests (`If-None-Match`) return
  `304 Not Modified` immediately.
* `Content-Type: application/vnd.oai.openapi+json;version=3.0` (the
  media type required by OGC Req 6).

The document also conforms to the
`http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/oas30`
conformance class (already declared at every family's
`/conformance` endpoint).

### 3.1 View endpoints (public, `gis_token`-based)

Used by the **public map viewer** and external GIS clients. Access is
granted via a `gis_token` embedded in the URL — no session authentication
required.

| Method | URL Pattern                                                                            | Name                                | Description                                          |
|--------|----------------------------------------------------------------------------------------|-------------------------------------|------------------------------------------------------|
| GET    | `/api/v2/gis-ogc/view/<gis_token>`                                                     | `view-landing`                      | OGC landing page (service discovery)                 |
| GET    | `/api/v2/gis-ogc/view/<gis_token>/conformance`                                         | `view-conformance`                  | OGC conformance declaration                          |
| GET    | `/api/v2/gis-ogc/view/<gis_token>/geojson`                                             | `view-geojson`                      | (NOT OGC) frontend map viewer GeoJSON                |
| GET    | `/api/v2/gis-ogc/view/<gis_token>/collections`                                         | `view-collections`                  | Collections list (one per geometry group present)    |
| GET    | `/api/v2/gis-ogc/view/<gis_token>/collections/<commit_sha>_<group>`                    | `view-collection`                   | Single collection metadata (`<group>` = `points`/`lines`) |
| GET    | `/api/v2/gis-ogc/view/<gis_token>/collections/<commit_sha>_<group>/items`              | `view-collection-items`             | Collection items                                     |
| GET    | `/api/v2/gis-ogc/view/<gis_token>/collections/<commit_sha>_<group>/items/<id>`         | `view-collection-feature`           | Single feature (OGC Req 31-33)                       |
| GET    | `/api/v2/gis-ogc/view/<gis_token>/collections/<commit_sha>` (legacy mixed)             | `view-collection-legacy-gone`       | **410 Gone** + `Link: rel=alternate` header — old setups must re-add the layer |

### 3.2 User endpoints (public, `user_token`-based)

Provide per-user access to all projects the token owner can see. Intended
for personal QGIS connections.

| Method | URL Pattern                                                                          | Name                                | Description                                          |
|--------|--------------------------------------------------------------------------------------|-------------------------------------|------------------------------------------------------|
| GET    | `/api/v2/gis-ogc/user/<key>`                                                         | `user-landing`                      | OGC landing page                                     |
| GET    | `/api/v2/gis-ogc/user/<key>/conformance`                                             | `user-conformance`                  | OGC conformance declaration                          |
| GET    | `/api/v2/gis-ogc/user/<key>/collections`                                             | `user-collections`                  | Collections list (one per geometry group, per project) |
| GET    | `/api/v2/gis-ogc/user/<key>/collections/<commit_sha>_<group>`                        | `user-collection`                   | Single collection metadata (`<group>` = `points`/`lines`) |
| GET    | `/api/v2/gis-ogc/user/<key>/collections/<commit_sha>_<group>/items`                  | `user-collection-items`             | Collection items (GeoJSON)                           |
| GET    | `/api/v2/gis-ogc/user/<key>/collections/<commit_sha>_<group>/items/<id>`             | `user-collection-feature`           | Single feature                                       |
| GET    | `/api/v2/gis-ogc/user/<key>/collections/<commit_sha>` (legacy mixed)                 | `user-collection-legacy-gone`       | **410 Gone** + `Link: rel=alternate` header          |

### 3.3 Experiment endpoint (NOT OGC)

| Method | URL Pattern                                   | Name         | Description                            |
|--------|-----------------------------------------------|--------------|----------------------------------------|
| GET    | `/api/v2/gis-ogc/experiment/<gis_token>`      | `experiment` | Single flat GeoJSON FeatureCollection  |

The experiment endpoint is a single-document download, **not** an
OGC API - Features service. It has no landing/conformance/collections
discovery and ArcGIS-Pro-style "Add OGC Server" workflows will not
follow it. Documented as a known limitation; wrapping it in a full
OGC tree is out of scope for this PR.

### 3.4 Landmark Collection endpoints (public, `gis_token`-based)

Landmark Collections expose a single OGC collection named `landmarks`.
`/items` is generated dynamically from the database and returns Point
GeoJSON with stable per-feature UUIDs.

| Method | URL Pattern                                                                                | Name                                       | Description                                   |
|--------|--------------------------------------------------------------------------------------------|--------------------------------------------|-----------------------------------------------|
| GET    | `/api/v2/gis-ogc/landmark-collection/<gis_token>`                                          | `landmark-collection-landing`              | OGC landing page                              |
| GET    | `/api/v2/gis-ogc/landmark-collection/<gis_token>/conformance`                              | `landmark-collection-conformance`          | OGC conformance declaration                   |
| GET    | `/api/v2/gis-ogc/landmark-collection/<gis_token>/collections`                              | `landmark-collection-collections`          | Collections list (always one: `landmarks`)    |
| GET    | `/api/v2/gis-ogc/landmark-collection/<gis_token>/collections/landmarks`                    | `landmark-collection-collection`           | Single Landmark layer metadata                |
| GET    | `/api/v2/gis-ogc/landmark-collection/<gis_token>/collections/landmarks/items`              | `landmark-collection-collection-items`     | Landmark Point GeoJSON FeatureCollection      |
| GET    | `/api/v2/gis-ogc/landmark-collection/<gis_token>/collections/landmarks/items/<uuid>`       | `landmark-collection-collection-feature`   | Single Landmark Feature                       |

User-scoped Landmark Collection OGC uses the existing application token and
lists every active Landmark Collection the token owner can READ. Each collection
UUID becomes one OGC collection id.

| Method | URL Pattern                                                                                       | Name                                            | Description                                  |
|--------|---------------------------------------------------------------------------------------------------|-------------------------------------------------|----------------------------------------------|
| GET    | `/api/v2/gis-ogc/landmark-collections/user/<key>`                                                 | `landmark-collections-user-landing`             | OGC landing page                             |
| GET    | `/api/v2/gis-ogc/landmark-collections/user/<key>/conformance`                                     | `landmark-collections-user-conformance`         | OGC conformance declaration                  |
| GET    | `/api/v2/gis-ogc/landmark-collections/user/<key>/collections`                                     | `landmark-collections-user-collections`         | Readable Landmark Collection list            |
| GET    | `/api/v2/gis-ogc/landmark-collections/user/<key>/collections/<uuid>`                              | `landmark-collections-user-collection`          | Single Landmark Collection metadata          |
| GET    | `/api/v2/gis-ogc/landmark-collections/user/<key>/collections/<uuid>/items`                        | `landmark-collections-user-collection-items`    | Landmark Point GeoJSON FeatureCollection     |
| GET    | `/api/v2/gis-ogc/landmark-collections/user/<key>/collections/<uuid>/items/<uuid>`                 | `landmark-collections-user-collection-feature`  | Single Landmark Feature                      |

### 3.5 Conformance and verification

Declared conformance classes (also returned at `/conformance`):

* `http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/core`
* `http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/geojson`
* `http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/oas30`

Test coverage:

* `pytest speleodb/api/v2/tests/test_ogc_compliance.py` — happy-path,
  cross-tenant security, ArcGIS Pro 3.6.1 replay, OGC schema
  validation, snapshots, query-count invariants.
* `pytest speleodb/api/v2/tests/test_gis_view_api.py` — project
  family integration tests.
* `pytest speleodb/api/v2/tests/test_landmark_collection_ogc.py` —
  landmark family integration tests.
* `make test-ogc-coverage` — 100 % line + branch coverage gate on
  the OGC core (`ogc_helpers.py`, `ogc_base.py`, the four service
  modules).
* `make test-ogc-mutations` — `mutmut`-based mutation testing on
  the OGC core (run ad-hoc; `uv pip install mutmut` first).

External conformance suite (optional, post-merge):

* `make test-ogc-teamengine` — runs the official OGC API - Features
  1.0 Core + GeoJSON conformance suite via the
  [OGC Team Engine](https://github.com/opengeospatial/teamengine)
  docker-compose harness against a local SpeleoDB instance. Slow
  (~5 min); intended for weekly CI or pre-release smoke.

### 3.6 Manual smoke test (post-deploy)

Before announcing a release, run the four-step smoke test below
against a staging or production-clone environment. Each step pins
one of the live ArcGIS Pro 3.6.1 regression dimensions.

1. **QGIS connection** (validates landing-page discovery and
   geometry-typed layers):

   * In QGIS, *Layer ▸ Add Layer ▸ Add WFS Layer ▸ New ▸ Service URL*
     and paste the personal-GIS-View landing URL from
     `/private/gis_views/`.
   * Choose the first project's `_points` and `_lines` layers, add
     both to the map.
   * Pin: point and line features visible,
     attribute table populated, no error in QGIS log.

2. **ArcGIS Pro 3.6+** (validates the live regression fix):

   * *Insert ▸ Connections ▸ Add OGC API Server* and paste the
     personal-GIS-View landing URL.
   * Drag the project's `_points` and `_lines` layers onto the map.
   * Pin: features visible, attribute table populated. The
     pre-fix behavior was an empty layer; if ArcGIS still shows no
     features the `links[*][rel=self]` / `numberMatched` /
     `crs` / `CRS84h` envelope is regressed.

3. **`curl` envelope sanity** (validates per-request semantics):

   ```sh
   # Landing URL is slash-free now; collection IDs are <sha>_<group>.
   curl -s "https://staging.speleodb.org/api/v2/gis-ogc/user/$KEY" | jq '.links[].rel'
   curl -s "https://staging.speleodb.org/api/v2/gis-ogc/user/$KEY/collections" | jq '.collections[].id'
   curl -s "https://staging.speleodb.org/api/v2/gis-ogc/user/$KEY/collections/${SHA}_lines/items" | jq '{numberMatched, numberReturned, timeStamp, links: [.links[].rel]}'

   # Legacy mixed <sha> URL must 410 with a Link header.
   curl -si "https://staging.speleodb.org/api/v2/gis-ogc/user/$KEY/collections/$SHA" | grep -E '^(HTTP|Link)'
   ```

   * Pin: landing has `self`, `conformance`, `data`, `service-desc`.
   * Pin: every collection id matches `^[0-9a-f]{6,40}_(?:points|lines)$`.
   * Pin: items has `numberMatched`, `numberReturned`, `timeStamp`,
     and `links` containing `self` and `collection`.
   * Pin: legacy `<sha>` URL returns `HTTP/1.1 410 Gone` with a
     `Link: ...; rel="alternate"` header listing the geometry-typed
     replacements.

4. **Pagination round-trip**:

   ```sh
   curl -s "$ITEMS_URL?limit=1" | jq '{nM: .numberMatched, nR: .numberReturned, next: [.links[] | select(.rel=="next") | .href]}'
   ```

   * Pin: `numberReturned == 1`, `next` link present (assuming the
     collection has > 1 feature). Following the `next` link returns
     200 with the second feature.

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
   `GET /api/v2/gis-ogc/view/<gis_token>/geojson`.

### OGC/QGIS access (token-based)

External GIS clients (e.g., QGIS) connect via:

- **View tokens** (`gis_token`) — access a single shared view.
- **User tokens** (`user_token`) — access all projects the user has
  permission to see.
- **Landmark Collection tokens** (`gis_token`) — read-only public access
  to one active Landmark Collection as Point GeoJSON.
- **User Landmark Collection tokens** (`user_token`) — the same application
  token pattern as Personal GIS View, but for all active Landmark Collections
  the user can READ.

Both token types are embedded in the URL path, not as headers or query
params. The OGC endpoints follow the OGC API - Features standard,
providing landing pages, conformance declarations, collections lists,
and item endpoints that QGIS auto-discovers. Landmark Collection tokens work
for active personal and shared collections; treat both as public read secrets.
Refreshing the application token from a user-scoped OGC card invalidates every
app currently authenticating with that token, not only the GIS URL.
