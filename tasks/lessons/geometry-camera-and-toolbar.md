# Fit geometry to the usable map and preserve established controls

The user found that geometry zoom clipped its bounding box, requested creation
beside Import GPS, and expected the same chevron as other overlay sections.

- Frame the complete coordinate extent inside the visible map after the editor
  has rendered. The canvas dimensions alone do not account for panels, an
  offscreen map tail, or the mobile sheet. Derive transient camera padding from
  those bounds and verify projected corners in a real browser.
- Keep primary creation actions in the established viewer toolbar. Compact the
  existing controls and wrap at narrow widths without hiding readable labels or
  reducing touch targets.
- Keep Create Geometry immediately before Import GPS. Choose new draft colors
  from the server-provided palette when opening, not during subsequent renders;
  editing must retain the saved color.
- Verify template changes through the running server, not just the source or
  asset build. Django's cached template loader retains old markup when runserver
  uses `--noreload`; use automatic reload for development and confirm actual
  desktop/mobile button positions before reporting a UI change complete.
- Match existing expand/collapse affordances rather than inventing a different
  control for a sibling panel.
- Reuse the existing visibility toggle markup and styles for every map overlay
  panel. A native checkbox without the shared slider is a visible inconsistency;
  verify the rendered control as well as its on/off behavior.
- Keep GIS Geometries and GIS Layers in the second navigation section, without
  My prefixes, in alphabetical order with the other GIS entries. This replaces
  the earlier request to put them before My GPS Tracks. Update the shared
  desktop/mobile sidebar and move complete blocks so icons and active-page
  highlighting stay with their links.
- The second section is now a collapsed-by-default GIS Tooling disclosure that
  opens on its contained pages. Keep GIS Survey Map outside it, directly below
  Survey Tools. Use current-page markers to expand the group instead of
  duplicating the route registry, and include special fleet watchlist pages.
- Keep the label GIS Tooling (without Advanced) and visually indent its
  children. Allow long nested link names to wrap rather than clipping them at
  narrow widths. Use the requested 290px sidebar width to keep ordinary GIS
  labels on one line; increase drawer width together with its full-width hidden
  translation.
- Treat folded overlay cards as one visual component: share their width, height,
  and chevron alignment so a longer label does not change the stack's
  dimensions.
- When polygon fills obscure the basemap, reduce fill opacity consistently in
  saved and draft rendering; keep the outlines clear and avoid adding a control
  when the user explicitly requests a simpler fixed appearance.
- Test mobile Save/Cancel against the visual viewport, including scrolling,
  keyboard changes, and fullscreen. A sheet can fit its map container while
  remaining below the screen.
