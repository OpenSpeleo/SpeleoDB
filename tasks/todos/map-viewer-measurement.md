# Private map distance ruler

## Approved design

The user approved the implementation plan on 2026-09-17. Add a private-only
ruler below Map Source. Click/tap A then B to retain independent temporary
measurements, with a bowed geographic connector and simultaneous metric and
imperial distances. Right-click or Escape removes only the draft; turning the
ruler off clears everything. Keyboard placement uses a center reticle and Enter.
Geometry authoring ends measurement; ordinary dialogs and basemap changes retain
it. Distance is direct spherical distance with no snapping, terrain/depth
correction, persistence, editing, or export. Native labels declutter,
prioritizing the current/newest result.

Follow-up direction: remove the separate Cancel button and make every gesture
explicit in a more readable helper, with appropriate mouse/touch/keyboard copy.

## Implementation checklist

- [x] Inspect current viewer, lessons, and approve the complete design.
- [x] Extract shared geodesy and implement tested curve/formatting helpers.
- [x] Implement native draft/completed rendering and style lifecycle.
- [x] Implement ruler UI, temporary state, mouse/touch/keyboard accessibility.
- [x] Integrate exclusive interaction ownership and editor activity lifecycle.
- [x] Preserve basemap overlays, ordering, popup cleanup, and public behavior.
- [x] Run focused and full frontend tests, lint, and clean production build in
      the existing application container.
- [x] Verify actual authenticated browser behavior, responsive layouts,
      fullscreen, input methods, globe, labels, and served asset manifest.
- [x] Finish independent review and resolve findings.
- [x] Document architecture, extension boundaries, verification, and review.

## Final adversarial review and commit

User requested the review-agent skill, full testing, `prek run -a`, and a
commit.

- [x] Adversarially review the entire change set and resolve actionable
      findings.
- [x] Apply the user's helper revision: remove Cancel, explicitly explain each
      gesture, and improve visibility with mouse/touch/keyboard-specific text.
- [x] Run the full Python and JavaScript suites inside the existing container.
- [x] Verify GitLab creation accounting and cleanup for the Python run.
- [x] Run `prek run -a`, resolve changes/failures, and recheck affected
      behavior.
- [x] Record results and commit the complete change set.

## Implementation ownership

- Geometry/rendering agent: measurement geometry/renderer, shared geodesy, their
  tests, and new centralized defaults.
- Interface agent: measurement tool and tests, feature CSS.
- Root: shared interaction/editor/entrypoint/source/layer integration, tests,
  documentation, browser verification, and final checks.
- Independent reviewer: correctness, interaction ownership, lifecycle,
  accessibility, globe behavior, and regression review.

### Adversarial finding and user follow-up

The review-agent found a P2 keyboard-placement issue in
`frontend_private/static/private/js/map_viewer/measurement/tool.js:277`
(`centerPoint`): the canvas can extend below the visible viewport on short
screens, so its geometric center and the Enter target could be offscreen. The
correction uses the visible canvas intersection, keeps the target clear of the
helper, and positions the reticle and endpoint from the same calculation.
Resize, scroll, visual-viewport offsets, hidden canvases, and owned-DOM observer
feedback have regression coverage.

During review, the user requested removal of the Cancel button and clearer, more
visible gesture instructions. The revised helper explicitly explains placement,
live preview, navigation, draft cancellation, and exit/clear-all with separate
mouse/touch/keyboard copy. It uses stronger contrast and larger text. A separate
UX agent reviewed the copy and hierarchy. Final browser checks confirmed visible
crosshair arms and matching Enter placement at 320px, 390px, and 844px widths.
No actionable review findings remain. Suite/hook results are recorded below.

## Verification

All tests run in `speleodb_local_django` at `/app`. Reuse the existing
Playwright installation and Chromium for browser evidence. Required commands:
`npm run test:js`, `npm run lint:js`, and `npm run build`. No backend or
template changes are planned. The working tree was clean when implementation
began.

## Review

Implemented and independently reviewed on 2026-09-17. Browser review caught and
resolved tile-loading readiness, duplicate capsule padding, sibling-panel
positioning, and offscreen short-landscape controls. Continuous-pointer browser
evidence showed native symbol text fading; the changing readout now uses one
Mapbox-positioned DOM capsule while completed results retain native
collision-managed labels. Native labels are verified through rendered features
rather than GeoJSON alone. No actionable review findings remain.

Final verification in the existing application container:

- `npm run test:js -- --maxWorkers=1`: **1,315 passed across 85 files**. The
  standard parallel run encountered resource-pressure timeouts in existing
  suites; the complete single-worker run passed with unchanged time limits.
- `npm run lint:js`: passed.
- `npm run build`: passed; all **88 registered entries** and both private/public
  lazy entrypoints exist in the production manifest. Private chunk:
  `main-COQLwt55.js`; public chunk: `gis_view_main-COAi-cF1.js`.
- Authenticated Chromium: moving live readout, multiple pairs, right-click and
  Escape cancellation, keyboard placement, geometry/dialog ownership, basemap
  switching, complete style replacement during a pending draft, globe sky
  rejection, fullscreen, and served CSS manifest all passed without runtime or
  measurement errors.
- True mobile touch: tap endpoints, camera-changing pan and pinch, native touch
  cancellation, and ruler clear-all passed. Controls retain 44px touch targets.
  The separate Cancel button is absent at the user's request.
- Layouts: 320px and 390px phones, 844px landscape, and a 720 × 500 CSS viewport
  at DPR 2 equivalent to a 1440 × 1000 viewport at 200% zoom passed. Root and
  reviewer inspected final screenshots.
- 100 actual UI pairs completed in 1.78 seconds; native decluttering retained
  one label for overlapping measurements while keeping all 100 records.
- `git diff --check`: passed. No backend/template changes.
- First full Python invocation: **4,919 passed, 181 skipped, one failed** in
  Git-history idempotency because clone retry found a partial checkout directory
  while the container was under resource pressure. Audit
  `c41ca585caa64aca9865902623272371`: nine creations, ten POSTs, zero violations
  or unresolved outcomes, and verified deletion marking for all nine.
- Second full Python invocation: **4,919 passed, 181 skipped, one failed**. The
  original Git-history failure passed. All assertions for first-404 proxy
  recovery passed; its subsequent cleanup lifecycle encountered an actual GitLab
  deletion HTTP 502. Audit `ac71e90e2d8f406f9ad2dd270ba88248`: nine creations,
  ten POSTs, zero violations/unresolved outcomes, and verified deletion marking
  for all nine at final cleanup. Neither full invocation is represented as
  green. Independent review found no feature blocker or warranted backend change
  from these external GitLab failures.
- Focused rerun, `pytest speleodb/git_proxy/tests.py`: **48 passed**. Audit
  `984a8dee94104c3eb11926d2e922a6a1`: two creations, two POSTs, zero violations
  or unresolved outcomes, and verified deletion marking for both repositories.
- First `prek run -a`: all code/security/type/URL/lint/build checks passed; the
  Markdown formatter changed four owned documentation files. Changes were
  reviewed. Final `prek run -a`: **every hook passed**.

The repeatable browser runner and screenshots are local ignored artifacts in
`.artifacts/map-measurement/`, including `live-pointer-moving.png`,
`desktop-completed.png`, `touch-pair.png`, `layout-844x390.png`, and
`zoom-200-percent.png`. Design, APIs, ownership, performance, and extension
boundaries are documented in
[measurement.md](../../docs/map-viewer/measurement.md).
