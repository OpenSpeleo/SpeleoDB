# Private GIS Layers

GIS Layers are private map overlays created by an email address and shared through
direct-user permissions. The model deliberately stays small: metadata, an
original source file, one directly renderable GeoJSON file, and timestamps.

## Files and upload behavior

- GeoJSON is uploaded once. `source_f` and `data_f` reference that same object;
  the server does not parse, hash, count, copy, or preprocess it.
- KML, KMZ, TopoJSON, and zipped Shapefiles keep the original in `source_f` and
  are converted once to GeoJSON in `data_f` because Mapbox cannot render those
  formats directly. Shapefile ZIPs must contain one matching `.shp`, `.shx`,
  `.dbf`, and `.prj` dataset; coordinates are converted to WGS84.
- Files use UUID-scoped keys: `gis_layers/<id>/source_<safe original name>` and
  `gis_layers/<id>/data.geojson`. For direct GeoJSON, both model fields point
  to the one source object.

The browser sends the selected file in one multipart request. It performs no
file reading or transformation. The list API includes a signed `file` URL for
display, and activation refreshes the authenticated detail response before
adding its current URL as a Mapbox GeoJSON source. There is no render-manifest
request, revision lookup, artifact table, job state, or polling.

## Ownership and permissions

`created_by` is the creator's email and is provenance, not a foreign key.
Access is represented only by active `GISLayerUserPermission` rows. Creation
adds one ADMIN permission for the authenticated creator. That row has no
special status after creation; active permission rows alone authorize access
and can be changed or revoked by an administrator.

Deletion is soft: the layer and its active permissions become inactive. Stored
files remain available for retention and administrative recovery.

## API

- `GET/POST /api/v2/gis-layers/` lists accessible layers or uploads one.
- `GET/PATCH/DELETE /api/v2/gis-layers/<id>/` reads, edits metadata, or soft-deletes.
- `GET/POST/PUT/DELETE /api/v2/gis-layers/<id>/permissions/` manages sharing.
- `GET /api/v2/gis-layers/<id>/source/` redirects to the signed original source.

The list/detail serializer returns `file` as the signed renderable GeoJSON URL
and derives `source_format` from the original filename.
