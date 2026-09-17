# GIS Geometries collection labels

- [x] Search application labels, accessibility text, errors, and documentation;
      distinguish collections from individual geometry records.
- [x] Pluralize map card/header/controls and management collection states;
      retain singular entity labels and record actions.
- [x] Update affected assertions/docs and verify container JavaScript tests,
      template checks, lint, build, and folded-card layout.

The sidebar and management page title already say My GIS Geometries. The map
card, its accessible controls, and collection loading/empty/error states still
use singular wording. Keep the existing shared card dimensions and styles.

## Verification

All 1,185 JavaScript tests and ten private Geometry page tests passed inside the
existing application container. JavaScript/template lint and the clean Vite
build passed. Chromium rendered the current collapsed-card markup using the
production CSS: the longer label fits at 1440, 390, and 320 px viewport widths
without changing the shared 160 × 48 px dimensions. The focused Python audit
recorded zero GitLab creations, POSTs, violations, or unresolved outcomes.

The remaining singular labels describe individual records, editor actions,
permissions for a record, or the feature/data type. They remain singular; no
schema or API changes were needed.
