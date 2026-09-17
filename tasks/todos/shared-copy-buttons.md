# Shared copy button styling

- [x] Inventory template and dynamic copy buttons and conflicting styles.
- [x] Add a shared info-style copy control and place the profile control inside
      its field.
- [x] Apply the shared class to all 12 copy buttons and preserve it during
      feedback.
- [x] Update docs and lessons; verify clipboard behavior, disabled state, style
      precedence, and responsive field layout.
- [x] Run container frontend tests, relevant Python tests, lint, and clean
      build; independently review results.

Plan: centralize copy-button presentation in the shared Tailwind design system.
Preserve clipboard handlers and labels. Remove per-feature button color resets
and exclude copy buttons from conversion-modal generic button rules. Keep
geometry-editor action hooks while assigning copy controls the shared class. The
token field uses a positioned inner button with reserved input padding.

## Inventory

Ten template buttons cover the profile token, personal GIS views, two GIS view
integration URLs, experiment and surface integration, landmark collection list
and integration, and two converter result modals. The remaining two are the
station note viewer and geometry draft conflict control. Independent inventory
found no public-specific copy buttons. Coordinate context-menu items and table
cells remain their existing non-button interaction types.

## Review

Centralized presentation in `copy-button`, preserved info styling during copy
feedback, restored each integration button's original SVG on reset, and removed
conflicting converter/feature button styles. Added behavioral regressions for
integration icon/style reset, disabled surface copying, and note copy/reset.

Verification in the running application container:

- 64 targeted Python view/template tests passed. GitLab audit: zero creations,
  POSTs, violations, or unresolved outcomes; no remote cleanup needed.
- JavaScript coverage: 1,194 tests exercised. Initial run had an unrelated
  experiment timeout under container load; rerun passed it and 1,192 other
  tests, with only the asset-build test timing out. Both asset graph tests then
  passed independently in 2.14 seconds. No test deadlines were relaxed.
- JavaScript lint, all nine changed templates' formatting/lint, clean production
  Vite build, and `git diff --check` passed.
- Independent Chromium verification checked all 12 controls with the production
  app, map, modal, geometry, and converter styles loaded: matching blue/white
  colors, 6px radius, 14px font, 8px/12px padding, zero border. The unavailable
  surface-network button stays disabled with opacity 0.6.
- The live profile field contains the button at 1440px, 390px, and 320px widths;
  its 96px right padding prevents label overlap. Profile and station-note copy
  success/reset keep info styling. Screenshots use a synthetic token only.
- Verified live manifest stylesheet: `style-app-iGb_ujKG.css`.
