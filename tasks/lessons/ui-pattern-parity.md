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
