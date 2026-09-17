# Private map toolbar and Settings

## Agreed design

Four equal-width actions: **Create Geometry → Import GPS → Managers →
Settings**. Import GPS is green. Managers provides direct access to Survey
Stations, Surface Stations, and Landmarks. Settings contains compact color
controls and five marker visibility categories, with five survey-station types.
Its footer has danger **Reset** and **Close** buttons. It does not contain
map-source, linework, overlay, or manager controls. The existing map-canvas
source picker and per-item panels remain. Preferences persist locally; old
removed preference fields are ignored. Explicit Go to reveals the target and its
parent gates. Public controls stay intact.

This revision incorporates the user's visual review: separate entity management
from map appearance, remove excessive controls and explanatory copy, and make
the toolbar uniform. The earlier three-button/all-categories design is
superseded.

## Implementation checklist

- [x] Centralize display preferences, persistence, and composed layer
      visibility.
- [x] Implement responsive toolbar and accessible Settings dialog.
- [x] Integrate color, separate manager menu, reset, and initial hydration.
- [x] Preserve navigation, geometry drafts, manager focus, and fullscreen flows.
- [x] Add meaningful state, rendering, template, and browser regression
      coverage.
- [x] Run JavaScript tests/lint/build and relevant Python tests in the existing
      container.
- [x] Verify authenticated desktop/mobile/fullscreen browser behavior and served
      assets.
- [x] Document architecture, extension procedure, performance, and verification.
- [x] Complete independent review and record results.

## Ownership

- Architecture agent: configuration, state, persistence, layers, depth legend.
- Interface agent: private template, map stylesheet, Settings component.
- Integration agent: navigation/panels, editor keyboard isolation,
  manager/overlay lifecycle.
- Root: initialization, fullscreen configuration, documentation, integration and
  final QA.

## Verification baseline

Planning baseline: 89 tests across eight relevant suites passed inside
`speleodb_local_django`. Authenticated browser inspection confirmed mobile
toolbar wrapping, duplicate landmark handlers in source, manager accessibility
gaps, and fullscreen excluding toolbar/managers. No product mutations were made
during planning.

## Review

### Final adversarial review and commit

- [x] Highlight the selected color mode in blue/purple.
- [x] Complete the requested review-agent adversarial review and fix actionable
      findings.
- [x] Run the full JavaScript and Python suites inside the existing container.
- [x] Inspect GitLab creation/cleanup audit and run `prek run -a` to completion.
- [x] Verify the selected color treatment in the browser using final built
      assets.
- [x] Commit all reviewed changes and record the result.

The principal-engineer adversarial review found no runtime correctness,
security/escaping, persistence, shared public/private, navigation, or modal
ownership regressions. Full-suite verification then found a **P2 stale toolbar
integration test** in `test_gis_geometry_views.py`: it indexed a removed CSS
wrapper and expected redundant accessible-name attributes. The corrective plan
was reviewed and implemented: use the stable `page-actions` anchor, retain
Create Geometry / Import GPS order checks, and verify their visible native
names. The reviewer accepted the correction with no remaining findings. The
first complete Python run also found a pre-existing stale Compose assertion: the
documented worker-name change still had a test expecting no container name.
Updated only that assertion to the existing instance-prefix naming contract.
Initial run: 4,918 passed, 181 skipped, and those two stale assertions failed.
Its GitLab audit `74c71ec90d114427b567b4bd6f05de1f` recorded 9 creations, 10
creation requests, no violations or unresolved outcomes, and confirmed deletion
marking for all nine created repositories. The fresh full run passed: **4,920
Python tests, 181 skipped**; JavaScript passed **1,258 tests across 81 files**.
Final audit `a41be1b945aa4492ba0731efc60027a1` again recorded 9 creations, 10
creation requests, no violations/unresolved outcomes, and confirmed deletion
marking for every created repository. Chromium verified that only the selected
mode has indigo fill/white text at 1440px and 390px, using served
`style-map-viewer-CQdyjpyH.css`.

Final `prek run -a`: all checks passed. Final browser checks passed again.
Commit: `Redesign map viewer toolbar and display settings`.

### Hover and action-color follow-up

- [x] Remove the obsolete Survey Stations fixed-width rule that truncates its
      row hover.
- [x] Give Managers blue and Settings purple backgrounds, including hover/open
      states.
- [x] Rebuild assets and verify full-row hover, equal widths, and button colors
      in Chromium.
- [x] Run container JavaScript checks and document the correction.

Removed `#station-manager-button { width: 10rem; }` from the shared private
stylesheet. Chromium verified all three rows have identical 210px hit/highlight
widths at 1440px and 390px, including hover at both horizontal edges. Verified
blue/purple idle, hover, and expanded colors and equal toolbar widths. The page
serves `style-map-viewer-xpHZy_Ep.css`. Clean build, template formatting, and
all 1,258 JavaScript tests passed. Independent CSS audit found no further ID
overrides.

Initial redesign verification (before the color follow-up):

Implemented the revised design and independently reviewed architecture, keyboard
behavior, and desktop visuals. Final container verification:

- JavaScript: **1,258 tests across 81 files**, full lint passed.
- Python: **80 tests** covering rendered templates and Webviewer restrictions;
  ruff, mypy, djLint, and Django system checks passed.
- GitLab audit: **0 repositories, 0 creation POSTs, 0 violations**; no cleanup
  required. Audit `479b5af2918944bd96c46064174a9f0f`.
- Clean production Vite build passed after stopping the watcher. All 106
  manifest records resolve to emitted files; both viewer entrypoints are valid.
  Authenticated page served `style-map-viewer-CFFFrY7k.css` and private
  `main-CY6pyFmB.js`; public entrypoint is `gis_view_main-DAd6sahV.js`.
- Real Chromium checks passed at 1440, 768, 767, 641, 390, and 320px, plus short
  landscape and reduced motion. All four toolbar buttons are equal width; Import
  GPS is green; desktop labels remain on one line. Settings contains five marker
  switches, five station types, compact color mode, and Reset/Close.
- Verified focus containment/restoration, category effects on existing Mapbox
  layers, persistence/reload/reset, no toggle-induced API calls or
  camera/project selection changes, geometry draft keyboard isolation, and
  fullscreen toolbar, Settings, managers, and GPS import.
- Manager checks cover all three managers, shared child-dialog focus and Escape,
  parent restoration, real surface-station Details/Back, and real
  surface/landmark Go to. There were no survey-station records in the browser
  session; unit tests cover survey subtype/project/country reveal. Legacy
  bespoke station editors retain existing behavior; this task does not rewrite
  every editor.

Browser review caught and fixed initial reverse-Tab escaping Settings, parent
focus fallback after a child trigger disappears, and the station Back control
being removed during asynchronous detail rendering. These have regression tests.
The user reported stale live assets during implementation; the lesson in
`tasks/lessons/live-template-asset-coherence.md` records the prevention rule.
