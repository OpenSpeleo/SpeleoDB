# Tailwind CSS 4.3.1 Strict-Parity Migration

## Goal

Upgrade Tailwind CSS from 3.4.19 to exact `tailwindcss@4.3.1` and
`@tailwindcss/cli@4.3.1` while preserving public/private source boundaries,
build interfaces, rendered behavior, and cascade semantics.

## Adversarial review status

The implementation checkmarks below describe the original migration handoff;
they are not a current parity certificate. A live Git-browser regression
invalidated the old candidate hashes, generated-output inventories, timings,
test totals, browser totals, and zero-difference claims. Evidence-bearing work
has been reopened below and is tracked in
`tasks/todos/tailwind-v4-adversarial-review.md`. Only independently reproduced
checkmarks and metrics have been restored; the exhaustive live-matrix items
and final completion remain open.

## Repository Setup and Baseline

- [ ] Create `codex/tailwind-v4-migration` from starting commit
  `3334c10dde9a65c60f95f70f50c9aa9e78651cc4`. The current branch is `dsf`;
  retain it during review and report the approved-plan mismatch.
- [x] Preserve the pre-existing untracked
  `tasks/todos/tailwind-v4-migration-prompt.md`.
- [x] Read `AGENTS.md`, `docs/coding-rules.md`, `docs/node-tooling.md`, and the
  relevant UI/frontend lessons.
- [x] Create a separate v3 worktree with independent `node_modules` under
  `/tmp` using Node 22 through `mise`.
- [x] Reproduce and independently validate the v3 baseline twice from clean
  `npm ci` installs.
- [x] Capture unminified/minified CSS, hashes, sizes, line counts, timings,
  warnings, selectors, at-rules, custom properties, keyframes, plugin output,
  source inventories, and the complete v3.4.19 palette under `/tmp`.
- [x] Record independently regenerated baseline hashes and inventories in the
  adversarial review. Previous values and `/tmp` artifacts are clues only.
- [x] Capture effective stylesheet order for public, private, public GIS, and
  private map pages.
- [x] Run `npx @tailwindcss/upgrade@4.3.1` only after the baseline exists and
  review every resulting change.

## Build and Configuration

- [x] Pin `tailwindcss` and `@tailwindcss/cli` to 4.3.1 without unrelated
  dependency upgrades.
- [x] Update all six Tailwind production/watch/pre-commit commands and remove
  legacy `-c` flags while keeping script names and output paths stable.
- [x] Keep JavaScript configs for theme extensions and plugins, loading them
  through stylesheet-relative `@config` directives.
- [x] Disable automatic source detection with `source(none)`.
- [x] Register the exact public source set with stylesheet-relative `@source`
  directives.
- [x] Register the exact private source set with stylesheet-relative `@source`
  directives.
- [x] Remove obsolete config `content` arrays and keep plugins registered once.
- [x] Remove the ineffective duplicate private `borderWidth: {3}` declaration
  without introducing a `border-3` utility.
- [x] Preserve font imports, Flatpickr, public theme CSS, `x-cloak`, permission
  badges, and component-before-utility precedence with explicit layers.

## Tailwind v4 Compatibility Audit

Every item in this section requires fresh adversarial evidence, even where the
implementation is already present.

- [x] **CLI package split:** build, watch, and pre-commit commands all use the
  v4 CLI package.
- [x] **Imports/layers:** verify theme, base, components, utilities, and
  post-utility overrides preserve v3 cascade winners.
- [x] **Source detection:** prove included, excluded, and public/private
  cross-build source boundaries with contract tests and sentinel builds.
- [x] **Legacy config:** preserve all effective theme values, plugins, custom
  animations, breakpoints, shadows, widths, spacing, z-index, and outlines.
- [x] **Removed utilities:** migrate opacity families, `flex-shrink-*`,
  `flex-grow-*`, ellipsis, and decoration utilities in templates and runtime
  markup.
- [x] **Renamed utilities:** migrate shadow, drop-shadow, blur,
  backdrop-blur, radius, and outline names by computed value.
- [x] **Default borders:** restore v3 gray-200 bare border/divide behavior.
- [x] **Default rings:** restore v3 3px blue-500 bare ring behavior without
  disturbing explicit rings, offsets, forms, or map overrides.
- [x] **Preflight:** preserve placeholders, button cursors, dialog centering,
  hidden behavior, forms, and file-selector normalization.
- [x] **Space/divide:** preserve v3 sibling/hidden-child/reverse selector
  behavior rather than accepting v4 last-child semantics.
- [x] **Gradients:** use v4 linear-gradient names with sRGB interpolation,
  preserve stop behavior, and express the git-browser action surface with
  native v4 gradient utilities.
- [x] **Palette:** derive and apply the complete v3 RGB palette centrally,
  including indirect forms/typography/Preflight usage.
- [x] **`theme()` usage:** migrate processed CSS/arbitrary utilities to v4
  theme variables while preserving the observed welcome-modal inline fallback.
- [x] **Important syntax:** migrate leading important modifiers to trailing
  syntax and verify precedence.
- [x] **Hover:** restore unguarded v3 hover and group-hover behavior and
  specificity, including touch emulation.
- [x] **Variant order:** reverse only order-sensitive stacked variants.
- [x] **Transforms:** remove handwritten v3 transform-variable coupling and
  prevent static/animated transforms from composing twice.
- [x] **Transitions:** verify outline-color and individual transform
  transition behavior.
- [x] **Arbitrary values:** audit variables, underscores, commas, opacity,
  masks, borders, grids, and gradients.
- [x] **Plugins/components:** compare forms, typography, `.btn*`, headings,
  Flatpickr, and prose output.
- [x] **Native cascade:** verify representative component/utility, dark-form,
  permission, map-ring, custom-CSS, and public-GIS collisions.
- [x] **Handwritten CSS:** remove/replace dependencies on v3 `--tw-*`
  implementation variables.

## Automated and Structural Verification

- [x] Add compiler-backed regression tests for exact source directives,
  `source(none)`,
  versions, scripts, plugin ownership, and absence of migrated legacy patterns.
- [x] Compare v3/v4 selectors, at-rules, media queries, keyframes, plugin
  selectors, custom properties, and candidate-class inventories.
- [x] Explain every relevant addition/removal rather than accepting raw diffs.
- [x] Build each minified stylesheet three times from a clean process and
  require stable candidate
  hashes.
- [x] Record public/private build sizes, full-build and watch-rebuild timings,
  selector/theme-variable counts, and representative style-recalculation time.

## Browser Parity

- [x] Replace the synthetic `page.setContent` harness with a temporary pinned
  `@playwright/test@1.61.1` live-route harness outside the root workspace.
- [x] Run baseline and candidate applications from separate worktrees, ports,
  and deterministic cloned databases.
- [ ] Reuse identical Inter fonts and stub external map/tile/live API traffic.
- [ ] Freeze timestamps, randomness, AOS timing, transitions, canvas motion,
  and loading races for static captures; wait for `document.fonts.ready`.
- [ ] Compare relevant computed styles for every element and pseudo-element.
- [ ] Require exact pixel equality, with only proven nondeterministic canvas
  regions masked and documented.
- [ ] Run deterministic animation captures at start, midpoint, and endpoint.
- [ ] Cover all specified public page families and public GIS composition.
- [ ] Cover all specified private page/entity/tool/map families.
- [ ] Cover anonymous, authenticated, staff, read-only, read/write, admin,
  team-leader, web-viewer, and denied/disabled roles where applicable.
- [ ] Cover default, hover, touch, focus, active, checked, invalid, disabled,
  read-only, open/closed, expanded/collapsed, loading, success/error, and
  selected/unselected states where applicable.
- [ ] Cover breakpoint -1/exact/+1 widths, representative device sizes, and
  DPR 1/2 where available.
- [ ] Run pinned Chromium/Firefox/WebKit and smoke-test installed
  Chrome/Firefox/Safari where automation permits.

## Repository, Install, Watcher, and Deployment Gates

- [x] `npm run build:clean`
- [x] `npm run build:tailwind:public`
- [x] `npm run build:tailwind:private`
- [x] `npm run build:esbuild:private`
- [x] `npm run build:esbuild:public`
- [x] `npm run build`
- [x] `npm run lint:js`
- [x] `npm run test:js`
- [x] `npm run pre-commit`
- [x] `python manage.py validate_templates --settings config.settings.test --ignore-app allauth`
- [x] `pytest`
- [x] `prek run --all-files --show-diff-on-failure`
- [x] `git diff --check`
- [x] Clean `npm ci` plus build/lint/tests under configured Node 22.
- [x] Clean `npm ci` plus build/lint/tests under CI-compatible Node 24.
- [x] `npm approve-scripts --allow-scripts-pending` reports no unreviewed
  install scripts.
- [x] `npm run dev` starts all watchers, rebuilds isolated public/private
  sentinels without leakage, and terminates cleanly.
- [x] Exercise the Docker Node 22 development path.
- [x] Exercise Railway's non-destructive `npm ci && npm run build` contract.

## Documentation and Completion

- [x] Update `docs/node-tooling.md`.
- [x] Add and index `docs/tailwind-v4.md` covering architecture, compatibility,
  verification, performance, browser requirements, and shim removal.
- [x] Update `AGENTS.md` for the CSS-owned source/variant contract.
- [x] Do not commit generated CSS/bundles or add Playwright to the root
  workspace.
- [x] Add a lesson only if a real correction or reusable failure occurs.
- [x] Complete the review below with regenerated evidence and residual risk.
- [ ] Declare completion only with zero unexplained structural, computed-style,
  behavioral, or pixel differences.

## Review

### Current status

- Branch `dsf` remains at the requested starting commit. Its name differs from
  the approved `codex/tailwind-v4-migration` branch; review must report the
  mismatch without switching around the staged migration.
- Both prompt files are preserved as untracked files. Migration repairs remain
  unstaged so the original index and review changes stay distinguishable.
- Exact Tailwind/plugin pins, six script interfaces, generated output paths,
  root-only Node workspace, and CSS-owned public/private source sets remain the
  implementation contract.
- `tailwind_css/shared/design-system.css` owns shared product tokens, browser
  normalization, and semantic compiler-facing utilities.
  Build-specific variants stay in their CSS entrypoint; feature selectors and
  stable project variables stay in their application stylesheet. Application
  code must not couple to Tailwind's private `--tw-*` variables.
- The public GIS cascade is public Tailwind/custom, private Tailwind/custom,
  shared modal, map-viewer CSS, then Mapbox GL CSS. The private map cascade is
  private Tailwind/custom, base inline responsive CSS, Mapbox GL CSS, shared
  modal, then map-viewer CSS.

The old parity harness is not live-application evidence. Its broad suite read
raw Django template files, stripped resources and scripts, and passed the
unexecuted source to Playwright with `page.setContent`; it did not execute
template inheritance, includes, branches, authentication, or real route
composition. The focused Git-browser follow-up hard-coded a pre-fix button
fragment rather than testing both rendered anchors. It also consumed ignored
candidate CSS retained by a running Tailwind watcher after the source rule had
been deleted. The old harness did concatenate custom CSS, so omission of
`custom.css` is not a proven cause. Synthetic rendering, hard-coded markup, and
stale watcher output are the demonstrated evidence failures.

Final browser evidence must follow a stopped watcher and clean production
build, prove the exact asset served by separate baseline/candidate Django
servers, and navigate real routes using deterministic database and role
fixtures. The manifest must fail on skipped cases, DOM misalignment,
unexplained computed-style differences, or deterministic pixel differences.

### Regenerated adversarial evidence

- Two clean v3 Node 22 builds reproduced public unminified `7daf1d31…`
  (88,382 bytes/4,246 lines), private unminified `f58cd60b…`
  (116,935/5,786), public minified `927f57af…` (68,420), and private minified
  `5e7a0fd4…` (92,824).
- Three clean candidate builds reproduced public minified `87f0682d…`
  (86,538 bytes) and private `d2313d41…` (110,750). Candidate unminified output
  is public `62ea39df…` (109,883/3,850) and private `4076eaf8…`
  (137,282/4,923). Full builds took 0.98–1.35 seconds.
- Structural counts are public selectors 767→693, at-rules 14→84, media
  8→8, keyframes 4→4, custom properties 99→203; private 1,041→949,
  12→86, 8→8, 3→3, and 109→338.
- The focused real Git route passed 360 exact-pixel captures: two anchors,
  three pinned engines, widths 360/767/768/769/1440, DPR 1/2, and six states.
  Served asset hashes were verified, no masks were used, and the only computed
  normalizations were equivalent gradient endpoint and transition-set
  serialization.
- Node 22/24 clean install/build/lint and 921-test runs pass; the final Node 22
  semantic-naming run passes 922 tests. npm 11 reports no unreviewed scripts.
  Full pytest passes with 3,821 passed/154 skipped. npm
  pre-commit, full prek, template validation, watcher startup/termination,
  Docker builds, and Railway's full isolated predeploy sequence pass.
- Tailwind's active watcher retains deleted candidates under both v3 and v4;
  clean builds remove them. The final browser assets were rebuilt after all
  watcher checks.
- The complete route/role/state/accessibility/animation/map/browser matrix is
  still pending. The completion checkbox stays unchecked; details and the
  severity-ordered review are in the adversarial-review task.

### Superseded handoff record — stale and untrusted

Everything below this heading records the original migration handoff. Its
hashes, sizes, counts, timings, checkmarks, browser totals, and zero-difference
language are retained only to show what the adversarial review must reproduce
or falsify. None is current evidence and none may be copied into the final
result without a fresh run against the repaired, clean-built candidate.

#### Result and versions

The repository now uses exact `tailwindcss@4.3.1` and
`@tailwindcss/cli@4.3.1`. Forms and typography remain pinned at `0.5.11` and
`0.5.20`. `@parcel/watcher@2.5.1` was reviewed and added to the npm 11
`allowScripts` list; the final approval audit reports no unreviewed scripts.
No generated stylesheet/bundle or Playwright dependency is tracked.

The branch starts at the requested
`3334c10dde9a65c60f95f70f50c9aa9e78651cc4`. The preserved prompt remains
untracked. The v3 worktree is `/tmp/speleodb-tailwind-v3-3334c10`; baseline
artifacts are in `/tmp/speleodb-tailwind-baseline`, candidate inventories are
in `/tmp/speleodb-tailwind-candidate`, and the temporary browser harness is in
`/tmp/speleodb-tailwind-parity`.

The exact upgrade CLI was run from a clean committed disposable v3 copy after
baseline capture. Its proposed output deleted the public JavaScript config,
moved that config into CSS, retained the private config, used unrestricted
source discovery, and did not address visual compatibility. Only reviewed,
behavior-preserving concepts were retained: v4 imports/layers, CSS config
loading, and candidate renames.

#### Architecture and migration

The six npm command interfaces and output paths are unchanged. CSS entrypoints
now own `source(none)`, exact relative `@source` lists, adjacent `@config`
loading, and dark/hover/group-hover/sidebar variants. Config files only own
effective theme extensions and one base-only forms plus one typography plugin
registration. Sentinel builds proved included, excluded, and cross-build
isolation.

`tailwind_css/shared/design-system.css` freezes all 242 v3 palette entries plus
black/white, sRGB alpha colors, radius/shadow/drop-shadow/blur values, default
border/ring behavior, Preflight differences, v3 space/divide sibling selectors,
gradient/grid helpers, exact ring stacks, form SVGs, and transform/transition
compatibility. Handwritten permission, map-ring, and gradient rules no longer
couple to v3 implementation variables. The git-browser action surface is owned
directly by native v4 gradient utilities. Runtime and template
candidates were migrated mechanically for opacity, grow/shrink, ellipsis,
decoration, gradients, important syntax, variant order, renamed effects, and
arbitrary theme values. The v3-invalid `max-w-13` candidate was removed rather
than silently accepting its new v4 meaning.

Actual stylesheet order was confirmed as public Tailwind/custom; private
Tailwind/custom; public GIS public Tailwind/custom then private Tailwind/custom,
shared modal, map viewer; and private map private Tailwind/custom, shared modal,
map viewer.

#### Baseline, structure, size, and performance

Two clean v3.4.19 reproductions were byte-identical. References:

- public unminified `7daf1d31f6ebe3c959e5b774c3b14213d49fa59b5f79b22f1f3fce02afa3a1da`,
  88,382 bytes/4,246 lines; minified `927f57af…`, 68,420 bytes;
- private unminified `f58cd60b449f37e6cae22a0dd1735ef1f8993f512bb7bed6c76108bb658c6f20`,
  116,935 bytes/5,786 lines; minified `5e7a0fd…`, 92,824 bytes.

Final v4 minified builds were stable across three runs:

- public `9991e46ba7e24ffc48876ee2d7300c22eb2f03e9e50e528b1fb3af631da306c1`,
  85,680 bytes (+25.2% from the v3 minified build), 0.21–0.64 seconds;
- private `b51ef37071d19341b2c7e320ce38db96fe20231add145f036853327e5b40dfa2`,
  108,519 bytes (+16.9%), 0.23–0.24 seconds.

The final unminified public output is 108,799 bytes/3,829 lines and private is
134,841 bytes/4,893 lines. CSS-tree inventory counts are public 767→692 unique
rule selectors and 99→203 custom properties; private 1,041→946 selectors and
109→338 custom properties. Both retain eight media-query boundaries and the
same keyframe sets (public four, private three). Selector removals are the
audited legacy candidates and v3 selector serialization; additions are their
v4/native-nesting or `v3-` compatibility forms. At-rule growth (14→84 public,
12→86 private) is explained by v4 layers, supports guards, and registered
properties.

The full root build took 2.42 seconds. Initial Tailwind watch builds took
114/122 ms; sentinel rebuilds took 11 ms public and 5–13 ms private. A
representative Chromium style-recalculation probe over 40 forced passes measured
11→12 ms for 190 public nodes and 12.5→17.1 ms for 202 private nodes (about
0.43 ms per private pass). The increase is the compatibility theme/property
surface; no runtime JavaScript or DOM scan was added.

#### Browser parity

The harness uses `@playwright/test@1.61.1` outside the workspace with Chromium
149.0.7827.55 revision 1228, Firefox 151.0 revision 1532, and WebKit 26.5
revision 2311. Remote imports/images/scripts were removed from deterministic
static fixtures; fonts, animation clocks, motion, and asynchronous effects were
held constant. No pixel region was masked.

Final pinned-engine results total 591 successful captures with zero differing
pixels:

- 348 full public/private template captures at 1440×900;
- six public-GIS/private-map composition captures;
- 192 public/private breakpoint and device captures at every requested
  -1/exact/+1 width plus DPR 1/2 devices;
- nine animation captures at 0, 2,500, and 5,000 ms;
- 36 state captures covering hover, group-hover, touch-hover, focus,
  focus-visible, active, checked controls/switches, invalid, disabled,
  read-only, and expanded sidebar behavior.

Installed Chrome 149.0.7827.199 also produced zero pixels on its smoke capture.
Installed Firefox 151.0.2 was detected but macOS application xattrs prevented
Playwright from launching that unpatched binary. Safari 26.5 was detected but
system Safari automation was not enabled; pinned Firefox/WebKit provide the
engine coverage.

Computed-style comparison included geometry, normal styles, `::before`,
`::after`, and WebKit date pseudo-elements. Remaining string-level differences
are explained representations with pixel equality: Firefox font-family quote
serialization, v4 individual transform properties versus v3 matrices, the
corresponding transition longhands, extra zero-area transparent shadow layers,
`90deg` versus `to right`, equivalent color-space serialization, and equivalent
forms SVG/data-URI encodings.

Discrepancies resolved during the comparison included sRGB alpha rounding,
hidden-aware space/divide, one-third width, physical `mx-auto`, dark forms,
native WebKit date numerals, exact Firefox ring stacks, AOS `translate3d`,
gradient text rasterization, orange alpha serialization, checked form SVG
antialiasing, and switch state selectors losing v3 specificity across layers.

After the initial handoff, live application review found that the project git
browser's “Download as ZIP” and “History” actions had lost their button
surface. The v3 surface was a white-to-gray-100 downward gradient. Retaining
that appearance behind the legacy `.git_btn` selector—even after moving the
selector between stylesheets—did not restore the live result. The two controls
now declare `bg-linear-to-b/srgb from-white to-gray-100` directly, and
`.git_btn` is retained only by the existing mobile sizing rules. A source
contract covers both controls and rejects a reintroduced background-owning
`.git_btn` rule. Per the user's request, the final container build/test and live
confirmation for this correction are pending their run.

The raw-template harness excludes `pages/teams.html`: unexecuted Django branches
split a class attribute across template tags and cannot form a valid standalone
DOM. Django template validation and rendered view tests cover that template; no
production change was made to appease malformed raw HTML.

#### Repository and deployment gates

- Clean Node 22.22.2 and Node 24.18.0 disposable installs each passed build,
  JavaScript lint, and 915 tests in 45 files.
- Full pytest passed: 3,821 passed, 154 skipped in 330.13 seconds with local
  rustfs and GitLab services running.
- Django template validation: zero errors. Final npm pre-commit, full prek
  (including ruff, format, bandit, mypy, URL checks, and map JS lint), and
  `git diff --check` pass.
- Watch mode started both Tailwind and both esbuild watcher groups, rebuilt
  public/private sentinels without cross-build candidates, and exited cleanly.
  Tailwind retains deleted candidates in an active watcher cache; a clean build
  correctly removed both sentinels.
- Docker image Node 22.23.1/npm 11.17.0 passed clean install and full build in a
  disposable bind mount. Railway's exact `npm ci && npm run build` contract
  passed under Node 24.18.0/npm 11.16.0.

#### Residual verification risk

Implementation, structural inventories, builds, tests, and deterministic CSS
fixtures are complete with no unexplained difference. The exhaustive live-app
matrix in the original plan was not executed from two running servers with
cloned databases, nor was every role/state combination captured through real
navigation. Those three Browser Parity checklist items remain open rather than
conflating static template/pytest coverage with a live end-to-end certification.
The final completion checkbox therefore remains intentionally unchecked.
