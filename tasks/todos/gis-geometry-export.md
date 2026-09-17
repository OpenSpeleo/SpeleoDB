# GIS Geometry account exports

- [x] Reuse the centralized active READ_ONLY-or-higher geometry queryset in the
      existing generation-start snapshot.
- [x] Stage each database GeoJSON as `geometries/<name>--<uuid>.geojson`,
      preserving coordinates and recording revision, creator, color, timestamps,
      checksum, and size through the existing manifest pipeline.
- [x] Rename the exported GIS layer directory/category to `layers/` and mark the
      changed archive layout as format version 2.
- [x] Update the export page's included datasets, archive README, and feature
      docs.
- [x] Verify real ZIP contents, permissions, and concurrent edit/revocation
      snapshot behavior with focused database tests; run container
      export/frontend regression checks and lint/type/build checks as
      appropriate.

Design: export the stored bare LineString/Polygon directly, without rounding,
conversion, or a second source-storage copy. Reuse archive staging, filenames,
progress, checksums, and permission semantics. The existing ZIP upload remains
unchanged; geometry's source of truth remains the database. Each retry captures
fresh permissions and data. No schema migration or new export API is needed.

## Review

- 69 container Python tests passed across archive contents/permissions, geometry
  snapshots, consumer behavior, and account export APIs/rendering.
- All 1,158 JavaScript tests and the clean production build passed.
- Scoped pre-commit passed every applicable hook, including Ruff, mypy, template
  lint, JavaScript lint, and the asset build.
- An authenticated HTTP request to the running server confirmed the six-dataset
  listing and geometry description. The temporary QA user/session were removed.
- GitLab audit `9e66754d13214de59c9aaf3bba80827a`: two creations / two POSTs,
  zero violations or unresolved outcomes; both resources received deletion
  marks.
- Existing completed archives retain their original format. Newly generated
  archives use version 2 with `geometries/` and `layers/`.
