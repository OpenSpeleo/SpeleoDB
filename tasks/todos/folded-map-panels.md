# Consistent folded map cards

- [x] Share one folded-card width, height, and content alignment across
      Projects, GPS Tracks, GIS Layers, and GIS Geometry.
- [x] Verify the production CSS in Chromium, run container frontend checks, and
      document the result.

Production CSS verified in Chromium: all four cards measure 160 × 48 px, their
chevrons start 14 px from the edge and labels start 38 px from the edge, and no
label overflows. Clean Vite build passes. Updated the existing GIS Layer test to
reflect the shared dimensions; other frontend regressions remain unchanged.

- [x] Follow-up: halve GIS Geometry fill opacity (saved 35% → 17.5%; draft 18% →
      9%) through centralized render constants, without adding a UI setting.
