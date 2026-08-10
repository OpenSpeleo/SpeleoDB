# GPS Tracks

## Intent

GPS Tracks are private, authenticated GeoJSON datasets imported from GPX files.
They can be shared with other SpeleoDB users and exported back to GPX without
introducing a second storage representation. The stored GeoJSON remains the
source of truth used by the private map viewer and by export.

The original `GPSTrack.user` relationship is creator provenance. Access is
authorized exclusively through active `GPSTrackUserPermission` rows so creator
and collaborator behavior follows the same permission model.

## Permissions and lifecycle

GPS Tracks use the three direct-user collaboration levels. `WEB_VIEWER` is not
valid because GPS Tracks have no public viewer or tokenized public endpoint.

| Level            | View/map/export | Rename/recolor | Manage users | Delete |
| ---------------- | :-------------: | :------------: | :----------: | :----: |
| READ_ONLY        |       Yes       |       No       |      No      |   No   |
| READ_AND_WRITE   |       Yes       |      Yes       |      No      |   No   |
| ADMIN            |       Yes       |      Yes       |     Yes      |  Yes   |

Every new track receives an active ADMIN permission for its creator. The data
migration establishes the same invariant for legacy tracks. Permission revokes
are soft deletes: the row remains as inactive history and POST owns
reactivation. PUT only updates an active row.

GPS Tracks are top-level collaborative entities and are never hard-deleted by
the product API or Django admin. DELETE marks the track inactive, deactivates
its active permissions, and retains the GeoJSON and audit history. All normal
list, object, permission, export, and map querysets filter inactive tracks.
Same-owner hash uniqueness applies to active tracks, so importing the same data
after deletion creates a new active track without mutating historical rows.

## API and query ownership

The API is mounted under `/api/v2/gps_tracks/` and the legacy `/api/v1/` mirror.

- `GET /` lists every active track the caller can read. Each item contains the
  signed GeoJSON URL, creator email, caller permission level/label, and
  authoritative `can_write` / `can_delete` capabilities.
- `GET|PUT|PATCH|DELETE /<id>/` applies the permission table above.
- `GET|POST|PUT|DELETE /<id>/permissions/` lists collaborators for readers and
  restricts mutations to administrators.
- `GET /<id>/export/gpx/` returns an authenticated GPX download for readers.

Accessible track selection uses an `Exists` predicate and a permission-level
`Subquery`. The serializer reads the annotation instead of querying once per
track. The signed GeoJSON URL is intentionally unchanged, allowing shared
tracks to flow through `Config.loadGPSTracks()` and the existing lazy map cache.

## GPX export contract

Exports are GPX 1.1 documents with the standard Topografix namespace/schema and
`creator="SpeleoDB"`. The response content type is `application/gpx+xml`; the
attachment filename contains a sanitized track name and the current local date.

One stored GPS Track becomes one GPX `<trk>` named from the current model name.
Each GeoJSON `LineString` becomes an ordered `<trkseg>`; every member of a
`MultiLineString` becomes a separate ordered segment. Coordinates are converted
from GeoJSON `[longitude, latitude]` to GPX points, with a third ordinate used
as elevation. Empty FeatureCollections produce a valid empty named track.
Unsupported geometry and malformed coordinates return a clear 400 response
rather than silently dropping data.

GPX import currently discards per-point timestamps and truncates elevations to
integers before storing GeoJSON. Export therefore preserves the geometry and
available elevation but cannot recover original timestamps. Changing that
import/storage contract is intentionally outside this feature.

## Web interface

The GPS Tracks page is the collaboration hub. It shows creator and caller
permission information on desktop and mobile. Every reader receives Export GPX
and Access Control links. Edit actions only exist for writers and administrators;
delete actions only exist for administrators. Hidden actions are omitted from
the DOM rather than rendered as disabled controls.

After an import succeeds, the modal reports that GPS tracks are being refreshed;
map-specific refresh wording remains owned by the GIS Survey Map import flow.

The per-track Access Control page reuses the shared permission modal,
autocomplete, responsive permission cards/table, CSRF handling, and error
modals. Readers may inspect collaborators, while only administrators receive
grant/edit/revoke controls. The public map viewer continues to exclude GPS
Tracks.

## Testing and performance

Coverage spans model invariants, migration backfill/rollback, admin behavior,
the full permission matrix, permission mutation negative cases, soft deletion,
re-import, GPX XML/geometry contracts, schema generation, Django routes/views,
JavaScript action gating, XSS escaping, dashboard counts, and private map
loading. List and permission-query tests protect against cross-track leakage,
inactive-row leakage, and N+1 regressions.

Run focused tests while developing, then the full Python and JavaScript suites,
strict type/lint checks, template and URL validation, and a clean production
Vite build. Repository tests must run inside the devcontainer.
