# GIS Geometry: read-only technical specification

Audience: an agent implementing an authenticated GIS Geometry browser, map
overlay, or data consumer. This specification describes the current resource
contract and **GET requests only**. It contains no creation, modification,
deletion, or permission-management operations.

## 1. Resource and storage

A GIS Geometry is one named, colored, manually authored geographic shape: either
a line (`LineString`) or a simple polygon (`Polygon`). It is a standalone
private resource, identified by a UUID. It has no project, survey, country, or
GPS Track foreign key; displaying it in a survey viewer does not make it part of
that survey.

The record contains a name, creator email, color, GeoJSON document, content
revision, timestamps, and active/inactive state. Access comes from separate
direct-user permission records. Creator email is provenance, not authorization.

GeoJSON is stored directly in a database JSON field. Reading geometry does not
require S3, signed download URLs, source files, source formats, conversion jobs,
or polling. GIS Layers are a different resource with an imported-file workflow.
Do not use GIS Layer source/download endpoints to retrieve a GIS Geometry.

The private Survey Viewer initially hides saved geometries. It fetches metadata
first and retrieves coordinates when a geometry is requested. A visibility
toggle shows/hides an overlay; selecting its name also frames its full bounds.
There is no public sharing-token or Geometry-specific OGC endpoint.

## 2. Geometry data contract

`geojson` is a JSON object, not a JSON-encoded string, and has exactly two keys:
`type` and `coordinates`. It is a bare GeoJSON Geometry, not a `Feature` or
`FeatureCollection`. Display metadata belongs to the enclosing API record.

Coordinates are WGS84 decimal degrees in **longitude, latitude** order:

```json
{
  "type": "LineString",
  "coordinates": [
    [-87.5, 20.1],
    [-87.499, 20.1]
  ]
}
```

```json
{
  "type": "Polygon",
  "coordinates": [
    [
      [-87.5, 20.1],
      [-87.499, 20.1],
      [-87.499, 20.101],
      [-87.5, 20.1]
    ]
  ]
}
```

| Property          | Contract                                                                           |
| ----------------- | ---------------------------------------------------------------------------------- |
| Supported types   | `LineString`, `Polygon`, case-sensitive                                            |
| Position          | Exactly two finite JSON numbers: `[longitude, latitude]`                           |
| Longitude         | Inclusive range `[-180, 180]`                                                      |
| Latitude          | Inclusive range `[-90, 90]`                                                        |
| Line minimum      | Two distinct vertices                                                              |
| Polygon minimum   | Three distinct vertices plus the repeated closing position                         |
| Polygon rings     | Exactly one closed exterior ring; no holes                                         |
| Maximum vertices  | 100; polygon closure does not count                                                |
| Adjacent vertices | Must have different coordinates                                                    |
| Polygon topology  | No repeated vertices except closure, crossing/touching edges, or zero-area polygon |
| Polygon winding   | Either direction is accepted                                                       |
| Antimeridian      | Consecutive longitude differences greater than 180° are unsupported                |
| Precision         | Preserve received numeric coordinates; do not round stored/cached data             |

Standalone `Point`, all multipart types, `GeometryCollection`, altitude,
`Feature`, and `FeatureCollection` are unsupported resource shapes. Additional
GeoJSON keys such as `bbox`, `crs`, or `properties` are not part of this
contract. Line self-intersection is not prohibited by the polygon topology
rules.

### Bounding-box area and performance limits

**A geometry's bounding box cannot exceed 30 km² for performance reasons.** This
is the area of the latitude/longitude rectangle enclosing all vertices, not
polygon surface area, line length, a projected rectangle, or a geodesic
minimum-area box. A diagonal line can have a large bounding-box area. A
horizontal or vertical line can have area zero and still be valid.

| Bounding-box area          | Existing viewer feedback                                      |
| -------------------------- | ------------------------------------------------------------- |
| At most 8 km²              | Neutral                                                       |
| Above 8 km² through 30 km² | Orange warning                                                |
| Above 30 km²               | Invalid; no valid persisted geometry should exceed this limit |

The detail endpoint returns `bbox_area_m2`, measured in square metres, and
`vertex_count`. It does **not** return a bounding-box coordinate array. Compute
`[west, south, east, north]` from coordinate minima/maxima when fitting a map.
Do not substitute a shortest wrapped longitude interval.

The shared area formula is:

```text
R = 6371008.8 metres
area_m2 = R² × radians(east − west)
            × 2 × cos(radians((north + south) / 2))
            × sin(radians((north − south) / 2))
area_km2 = area_m2 / 1000000
```

This spherical rectangle measure is a performance policy, not a survey-grade
ellipsoidal area measurement. Compare full precision with thresholds and round
only presentation values.

Policy constants are owned by
[`speleodb/gis/geometry_contract.json`](../speleodb/gis/geometry_contract.json).
Python validation and JavaScript `DEFAULTS.GIS_GEOMETRY` consume that same
document. Cross-language tests verify agreement. Other agents working in this
repository must import the existing contract rather than duplicate its values.

## 3. Color and transparency constants

The API supplies `color` as `#RRGGBB`. Color is record-specific. Transparency is
a **global rendering constant**, not an API field, record property, user
preference, or query parameter.

Opacity ranges from `0` (invisible) to `1` (opaque). Transparency is its
complement: `transparency = 1 - opacity`.

| Rendering constant                         | Value   | Visual meaning                                             |
| ------------------------------------------ | ------- | ---------------------------------------------------------- |
| `DEFAULTS.GIS_GEOMETRY.FILL_OPACITY`       | `0.175` | Saved polygon fill: 17.5% opaque, 82.5% transparent        |
| `DEFAULTS.GIS_GEOMETRY.DRAFT_FILL_OPACITY` | `0.09`  | Existing editor preview fill: 9% opaque, 91% transparent   |
| `DEFAULTS.GIS_LAYER_RENDER.LINE_OPACITY`   | `0.95`  | Saved line and polygon outline: 95% opaque, 5% transparent |

Canonical rendering constants live in
[`config.js`](../frontend_private/static/private/js/map_viewer/config.js). The
read-only integration uses **`FILL_OPACITY`**, not `DRAFT_FILL_OPACITY`. The
draft value is documented to distinguish existing editor presentation; this
specification does not require implementing an editor.

For an external client, define the saved-fill constant once in its shared
rendering configuration:

```typescript
export const GIS_GEOMETRY_FILL_OPACITY = 0.175;
export const GIS_GEOMETRY_FILL_TRANSPARENCY = 1 - GIS_GEOMETRY_FILL_OPACITY;
```

Inside SpeleoDB, consume the existing `DEFAULTS` instead of adding those
aliases. Apply fill opacity to the polygon fill layer only. Do not apply 17.5%
opacity to the whole overlay: that would also fade its outline and line
geometries. The shared renderer uses a 1.5 px polygon outline and 2.5 px line,
from `DEFAULTS.GIS_LAYER_RENDER.OUTLINE_WIDTH` and `.LINE_WIDTH` respectively.
GIS Layer fills retain their separate 35% opacity; do not inherit that value for
GIS Geometry.

## 4. Common HTTP and authentication contract

Use the deployment's origin followed by `/api/v2/gis-geometries/`. The examples
below use a placeholder origin. Preserve the trailing slash on every URL.

Every GET requires an authenticated, active user. Supported authentication:

- `Authorization: Token <api-token>`.
- `Authorization: Bearer <api-token>` using the same API-token mechanism; this
  is not a JWT or a public map token.
- An existing authenticated Django session cookie for the same deployment.

Send `Accept: application/json`. These requests have no request body and need no
CSRF token. Authentication checks still apply. The configured session
authenticator runs before token authenticators, so use the intended account's
session or a token-only client rather than mixing credentials for different
users.

Successful responses are bare JSON arrays/objects. There is no `data`,
`success`, `results`, or pagination envelope. Field order is not significant.
Timestamps are ISO 8601 strings with timezone information; parse the offset,
rather than assuming every timestamp ends in `Z`.

There are no endpoint-specific query parameters for filtering, search, sorting,
pagination, bbox queries, field selection, or revision selection. Do not invent
`?bbox=`, `?page=`, `?project=`, or `?include_geojson=` behavior. No geometry
endpoint implements conditional requests or advertises a feature-specific ETag
contract. Revisions are JSON metadata, not HTTP validators. DRF's
framework-level `?format=json` negotiation remains available; it is not a
geometry filter.

GET does not modify geometry content or sharing. Existing token authentication
may update the user's `last_login`; that does not change geometry revisions.

### Read authorization

The geometry and the requesting user's direct permission must both be active.
All three supported levels can use all three GET endpoints:

| Integer level | Label            | `can_write` | `can_delete` | `can_manage_permissions` |
| ------------- | ---------------- | ----------- | ------------ | ------------------------ |
| `1`           | `READ_ONLY`      | `false`     | `false`      | `false`                  |
| `2`           | `READ_AND_WRITE` | `true`      | `false`      | `false`                  |
| `3`           | `ADMIN`          | `true`      | `true`       | `true`                   |

Capabilities are returned metadata; a read-only integration does not act on
them. Team membership, project access, creator-email equality, `WEB_VIEWER`
level `0`, and Django staff status alone do not authorize these API reads. The
collection omits inaccessible records. Detail and permission reads normally
return 404 for inaccessible records, avoiding disclosure of their existence.

## 5. GET collection: metadata only

```http
GET /api/v2/gis-geometries/
Accept: application/json
Authorization: Bearer <api-token>
```

Returns **200 OK** and every accessible active geometry's metadata. The result
is unpaginated and ordered by `modified_date` descending. Ordering between equal
timestamps is unspecified. No accessible records means `[]`, not 404.

```json
[
  {
    "id": "12345678-1234-4234-8234-123456789abc",
    "name": "Survey reference line",
    "color": "#377eb8",
    "created_by": "creator@example.com",
    "geometry_type": "LineString",
    "revision": 1,
    "user_permission_level": 1,
    "user_permission_level_label": "READ_ONLY",
    "can_write": false,
    "can_delete": false,
    "can_manage_permissions": false,
    "creation_date": "2026-09-17T08:00:00-04:00",
    "modified_date": "2026-09-17T08:00:00-04:00"
  }
]
```

### Common response fields

These fields appear in both collection items and detail responses:

| Field                         | JSON type | Meaning                                                             |
| ----------------------------- | --------- | ------------------------------------------------------------------- |
| `id`                          | string    | Geometry UUID; stable identity and detail-route identifier          |
| `name`                        | string    | Display name, maximum 255 characters; not unique                    |
| `color`                       | string    | Six-digit hexadecimal display color with leading `#`                |
| `created_by`                  | string    | Creator email captured as provenance; not a user ID or access grant |
| `geometry_type`               | string    | `LineString` or `Polygon`                                           |
| `revision`                    | integer   | Positive content revision, starting at 1                            |
| `user_permission_level`       | integer   | Requesting user's level: 1, 2, or 3                                 |
| `user_permission_level_label` | string    | Corresponding enum label                                            |
| `can_write`                   | boolean   | Requesting user's content-edit capability                           |
| `can_delete`                  | boolean   | Requesting user's deletion capability                               |
| `can_manage_permissions`      | boolean   | Requesting user's sharing-management capability                     |
| `creation_date`               | string    | Geometry creation timestamp                                         |
| `modified_date`               | string    | Geometry modification timestamp; sharing changes also update it     |

The list deliberately omits `geojson`, `bbox_area_m2`, and `vertex_count`,
keeping initial loading small. It also contains no source file, source format,
download URL, transparency field, project ID, or `is_active` field. Only active
records are returned. Do not attempt to render coordinates from list metadata.

The server annotates permission and geometry type in the listing query and
defers the GeoJSON document, avoiding per-record geometry reads.

## 6. GET detail: one complete geometry

```http
GET /api/v2/gis-geometries/{id}/
Accept: application/json
Authorization: Bearer <api-token>
```

`id` is a required UUID path parameter. Returns **200 OK** with one JSON object
containing all common fields plus:

| Field          | JSON type | Meaning                                                 |
| -------------- | --------- | ------------------------------------------------------- |
| `geojson`      | object    | Bare Geometry using the contract in section 2           |
| `bbox_area_m2` | number    | Derived bounding-box area in square metres; may be zero |
| `vertex_count` | integer   | Editable vertex count, excluding polygon closure        |

```json
{
  "id": "12345678-1234-4234-8234-123456789abc",
  "name": "Survey reference line",
  "color": "#377eb8",
  "created_by": "creator@example.com",
  "geometry_type": "LineString",
  "revision": 1,
  "user_permission_level": 1,
  "user_permission_level_label": "READ_ONLY",
  "can_write": false,
  "can_delete": false,
  "can_manage_permissions": false,
  "creation_date": "2026-09-17T08:00:00-04:00",
  "modified_date": "2026-09-17T08:00:00-04:00",
  "geojson": {
    "type": "LineString",
    "coordinates": [
      [-87.5, 20.1],
      [-87.499, 20.1]
    ]
  },
  "bbox_area_m2": 0.0,
  "vertex_count": 2
}
```

This example's area is zero because both positions share a latitude. The
response is authenticated JSON from the application, not a redirect or file
attachment. Fetch it only when coordinates are needed.

## 7. GET permissions: active direct-user grants

```http
GET /api/v2/gis-geometries/{id}/permissions/
Accept: application/json
Authorization: Bearer <api-token>
```

`id` is the geometry UUID. **READ_ONLY access is sufficient** to inspect this
endpoint. It returns all active direct-user permissions for that geometry,
including other collaborators, not just the requesting user's permission.

Returns **200 OK** with an unpaginated array, ordered by level descending
(`ADMIN`, `READ_AND_WRITE`, `READ_ONLY`) and then user email ascending.

```json
[
  {
    "user": "creator@example.com",
    "level": "ADMIN",
    "creation_date": "2026-09-17T08:00:00-04:00",
    "modified_date": "2026-09-17T08:00:00-04:00"
  },
  {
    "user": "reader@example.com",
    "level": "READ_ONLY",
    "creation_date": "2026-09-17T09:00:00-04:00",
    "modified_date": "2026-09-17T09:00:00-04:00"
  }
]
```

| Field           | JSON type | Meaning                                    |
| --------------- | --------- | ------------------------------------------ |
| `user`          | string    | Collaborator email; no nested user object  |
| `level`         | string    | `READ_ONLY`, `READ_AND_WRITE`, or `ADMIN`  |
| `creation_date` | string    | Permission-row creation timestamp          |
| `modified_date` | string    | Permission-row last-modification timestamp |

Unlike `user_permission_level` in geometry metadata, permission-list `level` is
a **string**, not an integer. Timestamps describe the permission, not the
geometry. Inactive/revoked rows and revocation history are not returned. Treat
collaborator emails as private account data. Filtering is on the permission
row's active flag; the endpoint does not additionally exclude a listed
collaborator whose user account is inactive.

## 8. Errors and response handling

| Status                  | Meaning and client handling                                                                           |
| ----------------------- | ----------------------------------------------------------------------------------------------------- |
| `200`                   | Parse the documented array/object; an empty collection is successful                                  |
| `403`                   | Authentication missing/invalid or object permission denied; stop automatic retries and resolve access |
| `404`                   | Unknown, inactive, or inaccessible geometry; remove its overlay and revalidate the collection         |
| `406`                   | Requested response media type cannot be served; request JSON                                          |
| `5xx` / network failure | Transient failure; show an error/retry without presenting stale data as freshly verified              |

With the current SessionAuthentication-first configuration, missing or invalid
credentials result in **403**, not an assumed 401. For example:

```json
{ "detail": "Authentication credentials were not provided." }
```

A missing/inaccessible UUID normally produces a JSON `detail` error on these
views. A malformed UUID fails URL routing and may return a Django HTML 404, even
when the client requested JSON. Validate the UUID and inspect status and content
type before parsing. Do not depend on exact human-readable error text. A
permission change between queryset lookup and object authorization can also
produce 403; handle both 403 and 404 as loss of usable access.

## 9. Client implementation requirements

1. Load the collection once for the authenticated account and show metadata
   rows. Keep each saved geometry hidden initially.
2. Retrieve detail lazily when the user requests display or inspection.
   Deduplicate concurrent detail requests for the same UUID.
3. If the map library requires a Feature, wrap `detail.geojson` locally:

   ```javascript
   const feature = {
     type: "Feature",
     properties: { name: detail.name },
     geometry: detail.geojson,
   };
   ```

   This is a rendering adapter, not the API response format.

4. Render the record's color with the constants in section 3. Derive bounds from
   coordinates and fit the entire shape into the visible map viewport, allowing
   for panels. Toggling visibility alone should not unexpectedly move the
   camera.
5. Preserve the most recent explicit visibility choice while requests are in
   flight. A late response must not reveal a geometry the user has hidden. A
   stale failure must not undo a newer successfully loaded record.
6. Cache by authenticated account and geometry UUID. Use `revision` to compare
   content versions and reject older responses. A revision is not an access
   token: sharing changes can leave it unchanged. Refresh capability metadata
   independently and clear account data on logout/account switch.
7. Treat list/detail/permissions calls as separate reads, not one atomic
   snapshot. A record may become unavailable between them. Permission-related
   disappearance must remove its cached visible overlay; a transient transport
   failure can offer retry but must not claim the cached data is current.
8. Render names, emails, and error text using text nodes or shared HTML
   escaping. Validate colors before using CSS and never interpolate raw data
   into HTML.
9. Retrieve the permission list only for a user-facing access-inspection need.
   It is unnecessary for deciding whether an already-returned geometry is
   readable.

The current content revision includes metadata such as name/color. Sharing can
change `modified_date` without changing `revision`, and there is no immutable
historical GET-by-revision endpoint. Treat revision numbers as monotonic version
indicators, not dense event counters or globally unique versions. Python stores
them as positive 64-bit integers; JavaScript consumers should detect unsafe
integer values rather than silently compare rounded numbers.

## 10. Read-only request examples

Use an existing credential; credential provisioning is outside this document.

```bash
curl --fail-with-body \
  -H "Authorization: Bearer ${SPELEODB_API_TOKEN}" \
  -H 'Accept: application/json' \
  'https://YOUR-SPELEODB-HOST/api/v2/gis-geometries/'

curl --fail-with-body \
  -H "Authorization: Bearer ${SPELEODB_API_TOKEN}" \
  -H 'Accept: application/json' \
  'https://YOUR-SPELEODB-HOST/api/v2/gis-geometries/12345678-1234-4234-8234-123456789abc/'

curl --fail-with-body \
  -H "Authorization: Bearer ${SPELEODB_API_TOKEN}" \
  -H 'Accept: application/json' \
  'https://YOUR-SPELEODB-HOST/api/v2/gis-geometries/12345678-1234-4234-8234-123456789abc/permissions/'
```

## 11. Acceptance checklist for the implementing agent

- All network operations in this integration use the three documented GET
  routes.
- Empty list, each supported permission level, and denied/revoked access work.
- Collection rendering does not assume coordinates or a pagination envelope.
- Both geometry types render with correct coordinate order, color, and constant
  fill transparency. Point is not presented as a supported Geometry type.
- Polygon closure is excluded from vertex count; bounding-box area is labeled
  correctly and converted from m² to km² only for display.
- Full extents remain visible when framing; show/hide state survives delayed
  responses and failed requests without stale updates winning.
- Permission-list string levels are not confused with numeric metadata levels.
- A same-revision permissions change updates access/capability presentation.
- Cache isolation, safe text/color rendering, malformed responses, non-JSON
  errors, and timezone offsets are covered.

## 12. Implementation authority and verification references

The repository implementation is authoritative if this document drifts:

- Routes: `speleodb/api/v2/urls/gis_geometry.py` and its parent URL include.
- GET handlers: `speleodb/api/v2/views/gis_geometry.py`.
- Response fields: `speleodb/api/v2/serializers/gis_geometry.py`.
- Auth: `speleodb/api/v2/authentication.py` and `config/settings/base.py`.
- Access selection: `speleodb/api/v2/gis_geometry_access.py`.
- Resource fields/order: `speleodb/gis/models/gis_geometry.py`.
- Shape policy: `speleodb/gis/geometry_contract.json` and
  `geometry_validation.py`.
- Rendering constants:
  `frontend_private/static/private/js/map_viewer/config.js`.
- Read integration: `map_viewer/config.js`, `state.js`, `map/layers.js`, and
  `map/vector_overlay.js` beneath the same private JavaScript directory.
- Contract tests: `speleodb/api/v2/tests/test_gis_geometry_api.py`,
  `speleodb/gis/tests/test_gis_geometry.py`,
  `map_viewer/config.geometry_contract.test.js`, and
  `map_viewer/map/layers.gis_geometries.test.js`.

Run tests inside the existing `speleodb_local_django` container at `/app`, as
required by `AGENTS.md`. The broader feature design is in
[`gis-geometries.md`](gis-geometries.md).
