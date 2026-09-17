# Backend GIS menu order

Historical order, superseded by
[GIS navigation section](gis-navigation-section.md).

- [x] Order the backend links My GIS Geometries, My GIS Layers, My GPS Tracks.
- [x] Check template lint, frontend regressions, and the running server's menu
      order.

Verified the authenticated HTTP response from the running development server: My
GIS Geometry precedes My GIS Layers, which precedes My GPS Tracks. Existing
links, icons, and active-route highlighting stay with their complete menu
blocks. Template lint and all 1,158 frontend tests pass. Temporary verification
user and session were removed.
