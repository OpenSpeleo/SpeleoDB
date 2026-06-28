# Tailwind 4.3.1 Adversarial Review and Repair

## Goal

Independently audit the staged Tailwind 4.3.1 migration against the exact
Tailwind 3.4.19 baseline, repair every proven regression at its owning layer,
and retain evidence for every completion claim.

The subsequent Tailwind correction is tracked in
`tasks/todos/tailwind-single-bundle-consolidation.md`, and its compiler/delivery
successor in `tasks/todos/vite-asset-pipeline.md`. Current production ownership
is one neutral Tailwind source inside the Vite graph, built from the unchanged
private reference plus namespaced public components; two-output evidence below
remains historical migration evidence only.

## Initial Git State

- Branch: `dsf` (approved-plan branch name was
  `codex/tailwind-v4-migration`; do not switch around the staged work).
- HEAD/baseline commit: `3334c10dde9a65c60f95f70f50c9aa9e78651cc4`.
- Initial index: 156 files, 1,168 hunks, 4,639 insertions, 2,116 deletions.
- Initial working tree: no unstaged tracked changes and no untracked files.
- Generated public/private CSS and JavaScript bundles are ignored and are not
  evidence until rebuilt from a clean process.
- Both migration prompt files were incorrectly staged and must remain
  preserved as untracked files.

## Review Checklist

- [x] Preserve the original staged migration while keeping review repairs
  unstaged.
- [x] Remove both prompt files from the index without deleting them.
- [x] Reproduce the v3 baseline twice from clean Node 22 installs.
- [x] Audit the root package graph and clean installs on Node 22 and Node 24.
- [x] Audit every staged file and hunk; remove unnecessary changes and repair
  every proven defect.
- [x] Verify the exact public/private source boundaries with compiler-backed
  inclusion, exclusion, overlap, and leakage sentinels.
- [x] Audit every shared design-system token, selector, layer, state, and
  emitted declaration in `tailwind_css/shared/design-system.css`.
- [x] Verify all template and runtime candidate rewrites against generated and
  computed behavior, including both map-viewer entrypoints.
- [x] Strengthen package, palette, source, cascade, runtime-string, and
  application-internal-variable contract tests.
- [ ] Replace synthetic raw-template evidence with real Django route captures
  from isolated baseline/candidate servers and cloned deterministic databases.
- [x] Clean-build and live-verify both Git-browser action controls across the
  required responsive, pointer, keyboard, and touch states.
- [ ] Run all repository, clean-install, watcher, Docker, Railway,
  accessibility, browser, and performance gates.
- [x] Update the migration task, architecture docs, and reusable lessons with
  only reproduced results.
- [x] Leave the migration incomplete if any required live case or residual
  difference remains unproven.

## Audit Ledger

For each area, record the contract, baseline evidence, staged evidence, risk,
smallest falsifying test, conclusion, narrow fix, and regression proof.

### Git and repository process — 7 files / 8 hunks

- Contract: preserve user work, the baseline commit, ignored generated assets,
  root-only workspace, and required prompt index state.
- Baseline evidence: HEAD and both prompt blobs were verified before index
  correction; generated outputs are ignored by explicit `.gitignore` rules.
- Candidate evidence: branch and index inventory captured above.
- Risk: staged prompts and stale ignored output can invalidate both process and
  browser claims.
- Test: Git status/index checks plus clean generated-artifact hashes.
- Conclusion: defective; prompt index state and existing evidence claims are
  already inconsistent.
- Fix: both prompt files were removed from the index and preserved untracked;
  the branch was not changed.
- Regression proof: the index now contains 154 files, 3,503 insertions, and
  2,116 deletions; `git diff --cached --check` remains clean.

### Root package workspace — 2 files / 77 hunks

- Contract: exact Tailwind/plugin versions, minimal v4 transitive graph, stable
  scripts, reviewed install scripts, Node 22/24 reproducibility.
- Baseline evidence: two fresh copies installed 250 packages independently
  with Node 22.22.2/npm 10.9.7 and reported zero vulnerabilities.
- Candidate evidence: the lockfile has 289 package nodes (83 cross-platform
  optional nodes), 13 direct development dependencies, and only three
  install-script nodes: `@parcel/watcher`, `esbuild`, and `fsevents`. The
  matching exact versions are the only entries in `allowScripts`. Clean
  Node 22.23.1/npm 11.17.0 and Node 24.18.0 installs each passed build, lint,
  and all 921 JavaScript tests. npm 11 reported no unreviewed scripts.
- Risk: unrelated lock drift, missing native optional packages, or
  non-reproducible installs.
- Test: lock graph comparison and clean installs/builds on both Node lines.
- Conclusion: pass; the v4 graph is root-only, platform-complete, and
  reproducible on both supported Node lines. npm 10 does not implement
  `approve-scripts`, so the approval check was run under npm 11 on both Node
  lines.
- Fix: no package source repair was necessary; package-lock and approval
  assertions were added to the contract suite.
- Regression proof: the clean installs, root-only manifest search, exact pin
  assertions, install-script-node assertions, and Node 22/24 build/lint/test
  results all pass. No generated output or Playwright package is tracked.

### Tailwind sources and design system — 9 files / 77 hunks

- Contract: exact source ownership, layer/cascade semantics, v3 palette,
  Preflight, variants, forms, typography, utilities, transforms, and effects.
- Baseline evidence: both independent v3 builds reproduced byte-identical
  public `7daf1d31…` (88,382 bytes/4,246 lines) and private `f58cd60b…`
  (116,935 bytes/5,786 lines) unminified CSS. Their minified hashes are
  `927f57af…` (68,420 bytes) and `5e7a0fd4…` (92,824 bytes).
- Candidate evidence: after CSS-native consolidation, the repaired unminified
  public output is `f46eb314…` (109,921 bytes/3,853 lines) and private is
  `5a5b81df…` (137,320 bytes/4,926 lines). Three independent minified builds
  reproduced public `6e4b5ec0…` (86,562 bytes) and private `a026197f…`
  (110,774 bytes). Public selectors changed 767→694, at-rules 14→84, media rules 8→8,
  keyframes 4→4, and custom properties 99→203. Private changed 1,041→949,
  12→86, 8→8, 3→3, and 109→338 respectively.
- Risk: this is the highest shared blast radius across both generated products.
- Test: compiler sentinels, structural inventory, computed styles, and exact
  pixels in every stylesheet composition.
- Conclusion: defective before review. Tailwind 4's `@apply leading-5`
  retained `--tw-leading` and overrode later responsive text line heights.
  The v4 Preflight/forms composition also omitted v3 search appearance and
  outline offset, file-selector reset details, multiple-select optgroup/option
  inheritance, and transparent checked-control borders.
- Fix: component line heights are literal `1.25rem`; the missing search, file
  selector, multiple-select, checked, and indeterminate declarations are
  centralized in the shared design system.
- Regression proof: 15 compiler-backed contract tests pass, including durable
  production naming, mirrored source-tree sentinels, the complete v3 token
  fixture, runtime strings,
  package approvals, stylesheet order, `--tw-*` ownership, Git output, and
  component line-height behavior. Focused cross-engine form/component
  fixtures and the Git control matrix produced zero differing pixels.
- CSS-native consolidation proof: both JavaScript configs and `@config` were
  removed. The unminified and minified outputs are byte-identical to the
  pre-consolidation artifacts after removing the single intentional dark
  color-scheme rule. The contract suite now has 15 tests; the CSS-aware dev
  wrapper repairs Tailwind CLI's failure to rebuild on input/imported CSS
  changes and was proven to restart both builds for shared changes and only
  the owning build for entrypoint changes.

### Handwritten browser CSS — 3 files / 5 hunks

- Contract: later custom/map styles preserve v3 winners without private
  Tailwind implementation-variable coupling.
- Baseline evidence: real rendered pages establish generated→custom and map
  composition order; the v3 generated CSS owns compiler implementation
  variables.
- Candidate evidence: application CSS contains no Tailwind-private `--tw-*`
  reference outside the documented shared design-system boundary. Four
  production stylesheet orders are frozen by contract/rendered tests.
- Risk: split ownership and later cascade order can hide generated-utility
  regressions.
- Test: real route compositions and winning-declaration capture.
- Conclusion: pass; no additional handwritten application-CSS defect was
  found after the shared design-system repairs.
- Fix: none in this area.
- Regression proof: repository-wide variable scan, contract tests, rendered
  stylesheet-order test, clean public/private builds, and public/private
  esbuild entrypoint builds pass.

### Runtime JavaScript and JavaScript tests — 22 files / 221 hunks

- Contract: runtime markup retains v3 computed behavior, source detection,
  public/private map parity, and XSS protections.
- Baseline evidence: source diff and v3 runtime tests establish event names,
  emitted classes, shared map-module ownership, and HTML-sink protections.
- Candidate evidence: all 20 runtime JavaScript files and 159 staged runtime
  hunks were inspected; compiler-owned JS/Python candidate strings are now
  checked against emitted output.
- Risk: class strings outside literal `class=` attributes can escape static
  audits or the owning source glob.
- Test: full source/candidate extraction, compiler output, JS tests, map entry
  builds, sink audit, and browser states.
- Conclusion: defective. The mechanical Tailwind rename changed the native
  JavaScript event name `'blur'` to the unrelated utility name `'blur-sm'`,
  preventing experiment-field validation on focus loss.
- Fix: restore the event name to `'blur'` and correct the misleading utility
  comment without altering map behavior.
- Regression proof: a focused blur regression passes (32 experiment tests),
  all 922 JavaScript tests and lint pass, both map-viewer entrypoints bundle,
  and no new unsafe HTML sink was introduced.

### Private templates and rendered-view tests — 92 files / 616 hunks

- Contract: exact private UX, Django branches, permission states, inline CSS,
  and responsive behavior.
- Baseline evidence: the v3 Git-browser route renders two action anchors whose
  generated `.git_btn` rule owns the white→gray-100 downward gradient.
- Candidate evidence: all 92 files/616 template hunks were reviewed. The
  candidate route renders exactly two anchors with native v4 gradient
  utilities and generated→custom→inline stylesheet order.
- Risk: mechanical renames can alter computed values or become valid only in
  v4; synthetic raw templates do not execute production composition.
- Test: per-hunk mapping audit, rendered tests, real authenticated routes, and
  the role/state/viewport matrix.
- Conclusion: the staged native-utility Git repair is correct for the focused
  route. No other proven private-template mapping defect remained after the
  runtime and shared-CSS fixes. Exhaustive role/route coverage is still open.
- Fix: add a rendered Django structure/order regression without reintroducing
  background ownership on `.git_btn`.
- Regression proof: rendered view suites pass 209/209. The external live
  harness verified both anchors in three engines, five widths, DPR 1/2, and
  six interaction states: 360 captures, zero failures, zero differing pixels.

### Public templates — 19 files / 162 hunks

- Contract: public/auth/webview UX converges only on private typography tokens;
  public GIS loads the unified Tailwind asset once before public/private custom
  and map styles.
- Baseline evidence: v3 public output, source ownership, and rendered template
  suites were reproduced from the baseline worktree.
- Candidate evidence: all 19 files/162 public-template hunks were reviewed;
  public-only, shared, excluded, and cross-build candidates are proven by real
  compiler runs over temporary mirrored trees.
- Risk: union-source omissions, typography/gradient changes, selector
  collisions, and GIS cascade changes.
- Test: per-hunk audit, rendered routes, union-source sentinels, private-rule
  subsequence proof, and browser matrix.
- Conclusion: no additional public-template defect was proven. The complete
  public live-route, auth-state, GIS, responsive, and accessibility matrix is
  not yet certified.
- Fix: none in this area.
- Regression proof: compiler contracts, Django template validation, full
  pytest, JavaScript tests/lint, and public production/esbuild builds pass.

## Verification Record

### Git checkpoints

- Initial: branch `dsf`, HEAD `3334c10d…`, 156 staged files/1,168 hunks,
  4,639 insertions/2,116 deletions, no unstaged or untracked work.
- After process repair: 154 staged files/1,166 hunks,
  3,503 insertions/2,116 deletions; both prompts preserved untracked.
- Naming-correction checkpoint: the current index contains 156 files/1,171
  hunks (4,126 insertions/2,118 deletions), with neither prompt staged. The
  semantic production rename occupies 138 unstaged tracked files/838 hunks
  (1,005 insertions/1,778 deletions). Five paths are untracked: the replacement
  design-system stylesheet, the naming lesson, both prompts, and this review.
  Generated CSS/bundles remain ignored. Both cached and unstaged
  `git diff --check` pass.

### Reproducible builds and structure

- Baseline: two isolated Node 22.22.2/npm 10.9.7 installs reproduced public
  unminified `7daf1d31…` (88,382 bytes/4,246 lines), private unminified
  `f58cd60…` (116,935/5,786), public minified `927f57af…` (68,420), and
  private minified `5e7a0fd4…` (92,824).
- Candidate: three clean minified builds after CSS-native consolidation
  reproduced public `6e4b5ec0…` (86,562, +26.5%) and private `a026197f…`
  (110,774, +19.3%). A timed full Node 22 build took 1.83 seconds.
- Candidate unminified hashes/sizes are `f46eb314…` (109,921 bytes/3,853
  lines, +24.4%) and `5a5b81df…` (137,320/4,926, +17.4%). Full structural
  counts are recorded in `/private/tmp/speleodb-tailwind-final/inventory.json`.
- The active watcher retains a deleted sole-source utility under both v3.4.19
  and v4.3.1; a clean one-shot build removes it under both versions. This is
  an inherited watch-cache limitation, not a v4 regression. All four v4
  watcher groups started, completed initial builds (455/517 ms for Tailwind),
  and terminated together; the final production hashes were then rebuilt.

### Live browser evidence

- Separate v3/v4 Django servers ran on ports 8001/8002 against cloned
  `speleodb_tailwind_v3` and `speleodb_tailwind_v4` databases. The external
  harness uses pinned Playwright 1.61.1 and no root dependency.
- The focused Git route proved served baseline/private CSS
  `5e7a0fd4…`/92,824 bytes and candidate `d2313d41…`/110,750 bytes plus each
  build's custom CSS. It exercised both real action anchors in Chromium,
  Firefox, and WebKit at 360/767/768/769/1440, DPR 1/2, and default, hover,
  focus, focus-visible, active, and touch-hover states: 360 captures, zero
  failures, zero differing pixels, and no masks.
- The only observed computed strings normalized were implicit versus explicit
  0%/100% gradient endpoints and order-only equality of the same transition
  property set. Each result records browser, property, values, and reason.
- A pinned-Chromium forced full-style-recalculation probe (20 passes/trial,
  nine trials) measured public-home median 10.00→9.86 ms for 292 nodes and
  private Git median 15.06→23.56 ms for 488 nodes. The private increase is
  about 0.43 ms per forced pass. Ablation traced the cost to Tailwind 4's
  generated registered/custom-property surface; no runtime JavaScript, DOM
  scan, or application runtime loop was added. Postprocessing compiler
  output was rejected because it would remove Tailwind's cross-engine
  fallback semantics. Map-page performance remains part of the open matrix.

### Repository and deployment gates

- Node 22 and Node 24 clean install/build/lint/test passed the 921-test
  migration suite. After adding the production-naming contract, the supported
  Node 22 run passes 45 files and 922 JavaScript tests. npm 11 reports no
  unreviewed install scripts.
- `npm run pre-commit`, full `prek`, Django template validation, both Tailwind
  and both esbuild builds, JavaScript lint, and cached/unstaged diff checks
  pass.
- Full pytest passes: 3,821 passed, 154 skipped in 252.35 seconds. A first
  isolated run exposed only unavailable GitLab integration dependencies;
  focused rerun passed 57 tests with four skipped, then the single full
  service-backed run passed.
- Railway's exact predeploy sequence passed inside the isolated Node
  22.23.1/npm 11.17.0 candidate container: clean install (215 installed
  packages, zero vulnerabilities), build, no-op migrations, and 889-file
  collectstatic against the cloned database.

## Review Result

### Severity-ordered findings

1. High — native experiment-field blur validation was disabled by an
   accidental `'blur'`→`'blur-sm'` event rename. Restored and regression-tested.
2. High — component `@apply leading-5` leaked Tailwind 4's `--tw-leading`
   state and defeated responsive line-height utilities. Replaced with a
   literal component line height and compiler regression.
3. Medium — v4 Preflight/forms output did not reproduce several native search,
   file, multiple-select, checked, and indeterminate details. Centralized v3
   declarations and cross-engine fixtures now cover them.
4. Medium — the old 591-capture claim was not live-route evidence; it used raw
   Django source, hand-written pre-fix Git markup, and stale ignored CSS. The
   lesson/docs now state the demonstrated causes, and focused Git evidence is
   live, hash-checked, and deterministic.
5. Maintainability — the product-owned CSS was incorrectly framed as a
   versioned compatibility file. It is now `design-system.css`; production
   tokens and utilities use semantic `srgb-*`, `flow-*`, `row-divide-*`, and
   `grid-pattern-*` names. Version labels remain only in baseline evidence.

### Completion decision

Incomplete by design. The focused regression, structural audit, builds, and
repository gates pass, but the required exhaustive live matrix has not covered
every public/private route, role/permission/lock state, interaction,
breakpoint triplet/device/DPR, pseudo-element, animation point, accessibility
behavior, public-GIS/private-map composition, and representative map-page
performance in all three engines. Installed-browser smoke coverage also was
not repeated. These are evidence gaps, not known product failures, but the
completion checkbox remains unchecked until they are reproduced without an
unexplained computed-style, behavioral, accessibility, responsive, or pixel
difference.
