# Place creation alongside established map actions

The user moved Create Geometry from the geometry visibility panel to the viewer
toolbar beside Import GPS and requested a more compact toolbar. They also asked
for the geometry panel to use the established expand/collapse chevrons.

- Place a new authoring action beside comparable existing actions, and use the
  overlay list for visibility and editing. Do not hide primary creation inside a
  collapsible list merely because the list owns that feature's records.
- Reuse the existing panel affordance, including chevron direction and
  accessible labels; a minus sign does not preserve the interface's learned
  behavior.
- Adding a topbar action requires checking the whole toolbar's width. Remove
  conflicting fixed widths, compact spacing consistently, and keep adjacent
  authoring actions together when wrapping.
- Preserve readable toggle labels, keyboard names for icon-only controls, and
  touch targets when compressing mobile controls.
- Inspect every relevant CSS rule, including generic `.btn` minimum widths and
  later mobile `display: none !important` rules. Setting `width: auto` alone
  cannot override a minimum width, and changing layout cannot reveal a hidden
  control. Verify computed dimensions and visibility in a real browser at both
  desktop and narrow phone widths before considering the layout complete.
