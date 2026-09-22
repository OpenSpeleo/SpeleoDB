# Private GIS Layers

GIS Layers are private map overlays created by an email address and shared
through direct-user permissions. The model deliberately stays small: metadata,
an original source file, one directly renderable GeoJSON file, and timestamps.

## Files and upload behavior

- GeoJSON is uploaded once. `source_f` and `data_f` reference that same object;
  the server does not parse, hash, count, copy, or preprocess it.
- KML, KMZ, TopoJSON, and zipped Shapefiles keep the original in `source_f` and
  are converted once to GeoJSON in `data_f` because Mapbox cannot render those
  formats directly. Shapefile ZIPs must contain one matching `.shp`, `.shx`,
  `.dbf`, and `.prj` dataset; coordinates are converted to WGS84.
- Files use UUID-scoped keys: `gis_layers/<id>/source_<safe original name>` and
  `gis_layers/<id>/data.geojson`. For direct GeoJSON, both model fields point to
  the one source object.

The browser sends the selected file in one multipart request. It performs no
file reading or transformation. The list API includes a signed `file` URL for
display. The private Map Viewer refreshes the authenticated detail response on
first activation, fetches the current signed GeoJSON once, and passes that same
object unchanged to Mapbox. Parsing is limited to what display and bounding-box
zoom require; there is no transformation or feature interpretation. There is no
render-manifest request, revision lookup, artifact table, job state, or polling.

KML/KMZ compilation silently corrects the known exporter typo
`xmlns="xmlns='http://earth.google.com/kml/2.0'"` in the root namespace
declaration. Only a duplicated declaration wrapping a supported KML namespace is
repaired; arbitrary namespace values and malformed markup remain errors. The
repair applies to the parsing copy, preserving the uploaded original for
download. The existing missing-`xsi` repair still reports its inspection
warning.

The streaming scanner validates the root immediately and checks parser errors as
each chunk becomes available, including namespace errors that libxml would
otherwise delay until end of file. Invalid documents therefore stop before
unnecessary feature processing; a valid large document still needs full
synchronous conversion. DTD/entity, XInclude, size, depth, and geometry budgets
remain enforced.

XML rejection responses include `details.line`, `details.column` when reliable,
and a source-line excerpt capped at 240 characters. The upload dialog renders
these as text, never HTML. Diagnostics refer to the uploaded KML (the primary
KML member for KMZ); snippets are not added to server logs. Tests cover silent
repair and original-file preservation, early rejection, encoded XML diagnostics,
bounded excerpts, and malicious markup in the error display.

In the private Map Viewer, polygon zones and points retain the established GIS
feature popup. Content is constructed with DOM nodes and `textContent`; title,
description, and bounded source metadata are never inserted as raw HTML.

## Ownership and permissions

`created_by` is the creator's email and is provenance, not a foreign key. Access
is represented only by active `GISLayerUserPermission` rows. Creation adds one
ADMIN permission for the authenticated creator. That row has no special status
after creation; active permission rows alone authorize access and can be changed
or revoked by an administrator.

Deletion is soft: the layer and its active permissions become inactive. Stored
files remain available for retention and administrative recovery.

## Web interface

The shared desktop sidebar and mobile drawer label the entry **GIS Layers** and
place it in the second **GIS Tooling** disclosure, alphabetically between GIS
Landmark Collections and GIS Sensor Fleets. The listing heading remains **My GIS
Layers**. The group starts collapsed and automatically expands for its listing
and all layer settings tabs, using the existing current-route marker.

`/private/gis-layers/` remains the listing and upload entry point. Each desktop
row and mobile card provides the source download plus the same circular
right-arrow Open control used by Project and Surface Network listings. Open
leads to `/private/gis-layer/<uuid>/`; metadata editing and deletion are no
longer separate listing modals.

The opened layer uses the standard responsive settings workflow:

- Details displays name, description, color, and Download Source. It is
  read-only for readers and editable for writers and administrators.
- User Access at `/private/gis-layer/<uuid>/permissions/` is visible to every
  reader; only administrators receive grant/edit/revoke controls.
- Danger Zone is administrator-only and invokes the existing soft deletion.

GIS Layers and GPS Tracks share the settings shell, Details, User Access, and
Danger Zone templates. The pages reuse the common entity CRUD, permission modal,
danger-zone, and list-loader controllers.

## API

- `GET/POST /api/v2/gis-layers/` lists accessible layers or uploads one.
- `GET/PATCH/DELETE /api/v2/gis-layers/<id>/` reads, edits metadata, or
  soft-deletes.
- `GET/POST/PUT/DELETE /api/v2/gis-layers/<id>/permissions/` manages sharing.
- `GET /api/v2/gis-layers/<id>/source/` redirects to the signed original source.

The list/detail serializer returns `file` as the signed renderable GeoJSON URL
and derives `source_format` from the original filename.

The list and permission querysets annotate access in bulk and prefetch related
users, respectively. The new workflow does not add per-row requests or model
queries to listing rendering.
