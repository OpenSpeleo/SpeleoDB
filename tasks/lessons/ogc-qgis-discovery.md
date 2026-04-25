# OGC QGIS Discovery

When adding an OGC API - Features endpoint for QGIS, expose the landing page to
users and make the landing page advertise standards-shaped discovery links.

QGIS should be able to follow:

- `/<service>/`
- `/<service>/conformance`
- `/<service>/collections`
- `/<service>/collections/<collection_id>`
- `/<service>/collections/<collection_id>/items`

Do not expose a collections document as the user-facing URL. Do not rely on
internal bare-token aliases unless they are only retained for backward
compatibility.

When the product asks for an "all accessible GIS" link, reuse the existing
application-token user OGC pattern before adding another token system. The
landing URL should still be the copied URL, with the access scope documented as
all active resources the token owner can currently read.
