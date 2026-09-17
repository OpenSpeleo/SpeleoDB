# Geometry creation defaults

- [x] Place Create Geometry before Import GPS in the existing toolbar group.
- [x] Pick a random server-provided palette color for each new draft; retain
      stored colors when editing and the shared fallback for an empty palette.
- [x] Verify creation behavior and run container frontend checks; document
      results.

Review: all 1,158 JavaScript tests, lint, and the clean Vite build pass inside
the application container. Tests cover new draft selection, selected swatch,
unchanged initial draft state, stored edit colors, empty-palette fallback, and
saving the chosen color. Toolbar source order is Create Geometry, Import GPS.
