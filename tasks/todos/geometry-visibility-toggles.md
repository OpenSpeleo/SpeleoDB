# GIS Geometry visibility toggles

- [x] Reuse the existing map panel toggle markup and styles for geometry rows.
- [x] Verify label activation, visibility state, and disabled controls with
      tests.
- [x] Run container frontend tests, lint, and build; document the result.

Review: all 1,156 JavaScript tests, lint, and the clean Vite build pass in the
application container. Chromium verified the real panel with production styles:
both states render as the shared 33 × 18 px switches. No additional rendering
work or visibility/permission logic was introduced.
