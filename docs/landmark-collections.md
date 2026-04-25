# Landmark Collections

## Intent

Landmark Collections are the ownership boundary for all Landmarks. A user's
private Landmarks live in that user's personal Landmark Collection, created
lazily at first need. Shared Landmark Collections remain collaborative GIS
datasets. The same permission model governs viewing, editing, import
assignment, deletion, and authenticated exports.

## Design

`LandmarkCollection` follows the existing fleet and surface-network pattern:
an active aggregate row, an opaque `gis_token`, creator metadata, and a
separate `LandmarkCollectionUserPermission` table with READ, WRITE, and ADMIN
levels. Collections now have a type: `PERSONAL` or `SHARED`. Personal
collections have exactly one `personal_owner`; shared collections have no
personal owner.

Collections also carry a model-backed `color` chosen from the same
`ColorPalette` used by projects and GPS tracks. The color is validated as
`#RRGGBB`, normalized to lowercase by the API serializer, and used as the map
marker/label color for every Landmark in the collection. Shared collections
default to a palette color; personal collections default to white (`#ffffff`).

Every Landmark has a required `collection` FK and a `created_by` email for
provenance. There is no Landmark owner FK; access always comes from the
collection permission row. Duplicate coordinates are scoped by collection, so a
personal collection and a shared collection can both contain a Landmark at the
same latitude/longitude.

Access is centralized in `speleodb.api.v2.landmark_access` and
`BaseAccessLevel`:

- Personal Landmark: the owner has ADMIN on their personal collection.
- Shared Landmark: active collection permission is authoritative.
- READ can view and export collection Landmarks.
- WRITE can create, update, move, delete, assign, and reassign collection
  Landmarks.
- ADMIN can manage permissions and regenerate the GIS token.

Soft deletion sets `is_active=False` and deactivates active collection
permissions. Member Landmarks keep their collection FK and are hidden because
the inactive collection no longer grants visibility through personal,
collection, export, or OGC views. Inactive collection object routes, exports,
permission routes, and member Landmark detail routes return 404; ordinary
authenticated permission denials against active collections remain 403.
Personal collections cannot be deleted or permission-managed through the public
collection management API. Personal collections can still regenerate their GIS
token through the owner's ADMIN permission, but the private details page does
not expose editable personal collection name, description, or color controls.

## API Surface

Authenticated management:

- `GET/POST /api/v2/landmark-collections/`
- `GET/PUT/PATCH/DELETE /api/v2/landmark-collections/<uuid>/`
- `GET/POST/PUT/DELETE /api/v2/landmark-collections/<uuid>/permissions/`
- `GET /api/v2/landmark-collections/<uuid>/landmarks/export/excel/`
- `GET /api/v2/landmark-collections/<uuid>/landmarks/export/gpx/`

Existing Landmark endpoints accept an optional `collection` UUID. Missing or
null collection values are assigned to the caller's personal collection.
Responses return `collection`, `collection_name`, `created_by`, `can_write`,
`can_delete`, and `collection_color`.

`LandmarkCollection.is_active` is internal lifecycle state and is not returned
by public collection or permission serializers. Creates always force active
collections, and update attempts containing `is_active` are rejected; the
soft-delete endpoint is the only normal API flow that flips a collection
inactive.

The authenticated export endpoints require READ access on the active
collection and use the same collection Landmark queryset as the private details
page. Excel export returns a worksheet with `Name`, `Longitude`, `Latitude`,
and `Created By` columns. GPX export emits GPX 1.1 with the standard
Topografix namespace/schema declaration, `creator="SpeleoDB"`, and one
waypoint per Landmark. Waypoint descriptions include Landmark description plus
creator email.

GPX/KML imports validate the target collection and WRITE permission before
creating objects. Landmark creation runs inside a transaction, so parser or
database failures do not leave partial imported Landmark rows behind.

Public OGC API Features for active collections:

- `/api/v2/gis-ogc/landmark-collection/<gis_token>/`
- `/api/v2/gis-ogc/landmark-collection/<gis_token>/conformance`
- `/api/v2/gis-ogc/landmark-collection/<gis_token>/collections`
- `/api/v2/gis-ogc/landmark-collection/<gis_token>/collections/landmarks`
- `/api/v2/gis-ogc/landmark-collection/<gis_token>/collections/landmarks/items`

User-scoped OGC API Features for all active collections the application-token
owner can READ:

- `/api/v2/gis-ogc/landmark-collections/user/<user_token>/`
- `/api/v2/gis-ogc/landmark-collections/user/<user_token>/conformance`
- `/api/v2/gis-ogc/landmark-collections/user/<user_token>/collections`
- `/api/v2/gis-ogc/landmark-collections/user/<user_token>/collections/<collection_uuid>`
- `/api/v2/gis-ogc/landmark-collections/user/<user_token>/collections/<collection_uuid>/items`

The OGC item endpoint returns dynamic Point GeoJSON with
`application/geo+json`, short public cache headers, ETag, and 304 support. It
does not use the project commit proxy, which remains SHA and LineString based.
Personal and shared collection GIS tokens are both public read secrets: anyone
with the token can read active Landmarks in that one collection until the token
is regenerated or the collection is deactivated. The private GIS tab exposes the
landing-page URL so QGIS can discover the standards-shaped `/collections`
resource. The older bare-token collection URLs remain as compatibility aliases.
The user-scoped Landmark Collection OGC service reuses the existing DRF
application token, like Personal GIS View for projects; regenerating that token
invalidates the all-collections Landmark OGC link.

## Frontend Behavior

Private pages mirror Surface Network management for shared collections:
listing, details, permissions, GIS integration, and danger zone. The shared
collection permissions page matches the established Project user-permission
design for its responsive cards, desktop table, Grant Access button, modal, and
edit/delete icon controls. It also uses the same permission ordering: ADMIN,
then READ_AND_WRITE, then READ_ONLY, with email as the tie-breaker. Personal collections now appear in **My GIS Landmark Collections** and can open the
details/table/export and GIS integration views, but do not show permission or
danger-zone management. Shared collection details and create pages reuse the
project color picker so WRITE users can select the collection color. Personal
collection details intentionally show only the Landmark table and export
actions; GIS OGC access stays on the GIS integration tab.

The main **My GIS Landmark Collections** listing also shows one
**All Landmark Collections GIS** card. Its copied URL is the user-scoped OGC
landing page and exposes every active Landmark Collection the user can read,
including the personal collection and shared READ/WRITE/ADMIN collections.
Because the URL uses the application token, it must be treated like a password.
The card can refresh the application token after a confirmation modal. Refresh
invalidates authentication for every connected app using that token, including
Ariane, Compass, mobile apps, GIS clients, API scripts, and Git integrations.

The map Landmark manager loads collections, groups landmarks by collection in
collapsed groups, exposes collection selectors when creating or importing
landmarks, colors markers from `collection_color`, and disables edit/delete/drag
behavior for read-only collection landmarks.

All user-provided collection and Landmark strings are inserted through Django
template escaping, DOM `textContent`, or map-viewer `Utils.safeHtml`.

## Testing

Coverage is split by ownership boundary:

- Model tests cover token generation, permission uniqueness/reactivation,
  personal collection helper behavior, personal collection constraints,
  collection-scoped uniqueness, and hard-delete cascade behavior.
- API tests cover collection CRUD, soft delete, permission flows, Landmark
  visibility/write matrices, import assignment guards, and Excel/GPX exports.
- OGC tests cover landing/conformance/collections/metadata/items, inactive or
  invalid tokens, Point GeoJSON, ETag, and 304 behavior.
- Frontend tests cover URL/view availability and map-viewer client/manager
  collection hydration, the details-page Landmark table, export links, and
  read-only movement guard.
- Color tests cover default generation, API validation/normalization, shared
  WRITE updates, shared view picker rendering, personal detail form hiding,
  Landmark GeoJSON `collection_color`, grouped Landmark manager rows, and map
  layer paint expressions.
