# A precedent feature is not a refactoring target

## Correction

The GIS Layer work was told to follow GPS Tracks as its design and interaction
precedent. Instead, it migrated GPS Tracks to a new lifecycle, modified Project
panel APIs, and introduced a new cross-feature mobile drawer. The GIS management
page then approximated the GPS page with a separate visual language rather than
reusing its established table, cards, modals, colors, permission pills, and
actions.

## Rule

- “Follow feature X” means preserve feature X and copy or extract only proven,
  explicitly shared contracts. It is not authorization to refactor X.
- A new feature must not change its precedent's state, cache, refresh, layout,
  breakpoint, or DOM behavior unless that change is separately required and
  regression-reviewed.
- Start from the actual precedent template/controller/test structure. Visual
  resemblance is insufficient when the repository already has concrete UI
  contracts and helpers.
- Do not invent cross-feature navigation or mobile interaction as a side effect
  of one feature. A holistic viewer redesign requires its own product scope.
- Accepted parser diagnostics are internal evidence, not product lifecycle or UI
  state. Users see actionable errors; operators get structured logs.
