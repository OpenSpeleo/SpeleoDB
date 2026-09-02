# Private GIS Layers Implementation

## Goal

Provide private KML, KMZ, and GeoJSON overlays with the smallest practical model
and request path.

## Completed design

- [x] Store layer metadata, creator email, original source, and renderable data.
- [x] Store GeoJSON once and expose it directly without preprocessing.
- [x] Convert KML, KMZ, TopoJSON, and zipped Shapefiles to the single GeoJSON
      file required by Mapbox.
- [x] Use direct-user permission rows for list, detail, edit, delete, and
      sharing.
- [x] Add creator ADMIN permission explicitly at each creation entry point.
- [x] Keep GPS Track provenance as `created_by`; remove its user FK and hash.
- [x] Return signed display-file URLs in the normal list/detail serializers.
- [x] Render the returned URL directly with no manifest, revision, polling, or
      job.
- [x] Keep upload modals open unless explicitly dismissed.
- [x] Keep GIS Layer endpoints free of feature throttles.
- [x] Cover models, migrations, API permissions, direct GeoJSON,
      supported-format conversion, storage, admin, management UI, and map
      rendering.
