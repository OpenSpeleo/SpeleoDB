# UI Pattern Parity

When a feature says it follows an existing UI pattern, copy the source pattern
first and change only domain-specific labels, endpoints, and data fields.

Do not invent near-equivalent controls for permission tables, modals, action
buttons, or responsive layouts. A close visual approximation is still a
regression because users compare these workflows side by side.

For Landmark Collections, the shared collection user-permission page must match
Project user permissions for:

- responsive card/table layout
- row ordering and tie-breakers
- Grant Access button styling and disabled state
- permission pill colors and text normalization
- modal structure and button chrome
- icon-only edit/delete actions

Only permission choices differ: Landmark Collections use no-WEB_VIEWER levels.

When a listing is explicitly aligned with Projects or Surface Networks, reuse
their Open control exactly: the same `right_arrow.svg`, circular container,
dimensions, colors, spacing, and responsive presentation. A newly drawn SVG or
near-equivalent chevron is a design regression even when it has the same
function.

Shared responsive markup must carry its essential breakpoint utilities at the
markup boundary. Do not make mobile-card/desktop-table visibility depend on an
optional route stylesheet: every consumer must render exactly one layout even if
its surrounding model shell or asset set differs.
