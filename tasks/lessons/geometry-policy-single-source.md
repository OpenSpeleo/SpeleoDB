# Keep geometry policy in one shared contract

The user refined GIS Geometry to support lines and polygons only and raised the
bounding-box ceiling to 30 km² while retaining the orange warning above 8 km².
Supported types, warning thresholds, and rejection thresholds are independent
product choices; changing one does not imply changing the others.

- Keep these choices in `speleodb/gis/geometry_contract.json`. Backend
  validation, frontend validation, controls, and help text must consume the same
  policy.
- Derive displayed thresholds and raw GeoJSON type help from the contract rather
  than repeating numeric literals in templates or controllers.
- When policy changes, audit creation tools, raw editing, API/admin validation,
  fixtures, documentation, and positive as well as rejection tests together.
- Distinguish a standalone GeoJSON Point from a vertex: GPS point entry still
  places or changes vertices within an allowed line or polygon.
- Keep the warning and hard-limit checks separate and compare unrounded area.
  Verify that the orange range remains saveable and only an invalid or
  over-limit candidate disables Save.
