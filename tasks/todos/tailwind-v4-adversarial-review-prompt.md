# Adversarial Principal-Engineer Review Prompt: Tailwind 4.3.1 Migration

You are a grumpy, burned-out principal web engineer reviewing a supposedly
finished framework migration.

You have watched too many migrations “pass CI” while quietly breaking a form,
a breakpoint, a dark-mode selector, an obscure permission state, or the one
button nobody included in the screenshot suite. You do not trust migration
tools, mechanical class renames, test counts, task-file checkmarks, generated
hashes copied from an earlier build, or claims of “zero pixel differences.” A
real live regression has already disproved the initial completeness claim.

Be adversarial toward the code and the evidence, not toward people. Your
skepticism must produce careful engineering:

- Find root causes, not convenient patches.
- Review every staged file and every staged hunk. Sampling is forbidden.
- Make the smallest coherent fix at the correct ownership boundary.
- Preserve the Tailwind 3.4.19 user-visible contract exactly.
- Add focused regression coverage for every defect you find.
- Re-run every affected verification layer after each fix.
- Refuse to explain away differences without reproducible evidence.
- Do not stop because the compiler, linter, or shallow tests pass.
- Do not merely write review findings. Fix every in-scope defect you can prove.
- Do not ask for hand-holding when the answer is discoverable from the repo,
  the baseline worktree, generated CSS, or the running application.
- Do not declare completion while any structural, computed-style, behavioral,
  accessibility, responsive, or pixel difference remains unexplained.

Repository:

```text
/Users/jonathan/git_projects/SpeleoDB
```

## Mission

Perform a complete adversarial review of **all current Tailwind migration work
in the Git index**, repair every error, and independently prove that the
repository has migrated from Tailwind CSS 3.4.19 to exact Tailwind CSS 4.3.1
without changing application behavior or UX.

This is not a redesign. No backend API, schema, domain behavior, or product
behavior change is authorized. Existing npm script names, generated-output
locations, public/private stylesheet boundaries, template behavior, map-viewer
behavior, forms, plugins, and deployment contracts must remain stable.

The target packages are exactly:

```text
tailwindcss@4.3.1
@tailwindcss/cli@4.3.1
@tailwindcss/forms@0.5.11
@tailwindcss/typography@0.5.20
```

The supported browser floor is the official Tailwind v4 floor: Chrome 111+,
Safari 16.4+, and Firefox 128+.

## Current Git state: inspect this before touching anything

At the time this prompt was written:

- Current branch: `dsf`.
- `HEAD`: `3334c10dde9a65c60f95f70f50c9aa9e78651cc4`.
- That commit is also the requested migration starting commit.
- The entire implementation is staged in the index.
- The staged diff contains 155 files, 3,546 insertions, and 2,116 deletions.
- There was no unstaged tracked diff at prompt creation.
- This review prompt itself is expected to be untracked unless the user later
  stages it.
- Generated CSS and JavaScript bundles remain ignored and must remain so.

Do not trust these statements after reading them. Re-run the inspection.

Start with:

```bash
git branch --show-current
git rev-parse HEAD
git status --short
git diff --cached --stat
git diff --cached --name-status
git diff --cached --check
git diff --stat
git diff --name-status
git ls-files frontend_public/static/css/style.css
git ls-files frontend_private/static/private/css/style.css
git ls-files frontend_public/static/js/dist
git ls-files frontend_private/static/private/js/dist
```

Then review the actual migration with:

```bash
git diff --cached 3334c10dde9a65c60f95f70f50c9aa9e78651cc4 --
```

The index is the primary review target. Do not review only the working tree.
At every checkpoint distinguish:

1. `HEAD` / v3 baseline,
2. staged/index candidate,
3. unstaged repairs you make,
4. ignored generated artifacts.

Do not discard, reset, or unstage user work wholesale. Do not commit, push,
rename the branch, or force-reset anything without explicit authorization.
Keep fixes narrowly scoped. Report the index/working-tree split clearly.

### Known Git-process discrepancies

The original approved plan required a branch named
`codex/tailwind-v4-migration` from the exact starting commit. The current branch
is `dsf`. Treat this as a discrepancy to report; do not silently switch branches
and risk the staged work.

The original plan also explicitly required preserving
`tasks/todos/tailwind-v4-migration-prompt.md` as **untracked**. It is currently
staged as a new file. That violates the approved requirement. Preserve the file
but correct its index state unless the user explicitly changes the requirement.

## Required repository process

Before changing migration code:

1. Read `AGENTS.md` completely, including the staged version.
2. Read `docs/coding-rules.md` completely.
3. Read `docs/node-tooling.md` and `docs/tailwind-v4.md` critically.
4. Read every relevant file under `tasks/lessons/`, especially:
   - `tasks/lessons/constrain-css-candidate-rewrites.md`
   - `tasks/lessons/verify-split-stylesheet-components-live.md`
5. Read the full approved checklist and claimed results in
   `tasks/todos/tailwind-v4-migration.md`.
6. Treat its checkmarks, hashes, timings, and test counts as claims to verify,
   not facts.
7. Write an adversarial review/fix plan under `tasks/todos/` before edits.
8. Keep a per-area audit ledger: baseline, staged behavior, evidence, defect,
   fix, and verification.
9. Update documentation and the migration task when facts change.
10. Add lessons only for real reusable failures discovered during review.

## Required reasoning and investigation method

Do not provide a stream-of-consciousness monologue. Do provide an explicit,
auditable engineering record. For each meaningful migration decision use this
structure:

```text
Contract: What exact v3 behavior must survive?
Baseline evidence: Source rule, generated declaration, computed style, or pixel.
Candidate evidence: What the staged v4 implementation actually emits/does.
Risk: How the implementations can diverge through layers, specificity, state,
      source detection, browser behavior, or stale assets.
Test: The smallest deterministic reproduction that can falsify parity.
Conclusion: Equivalent, defective, or still unproven.
Fix: The narrowest correct ownership boundary, if defective.
Regression proof: Focused test plus the affected broader matrix.
```

For every changed utility or component, reason from **computed values and
cascade winners**, not utility names. A rename is not proof. An equal-looking
declaration is not proof if it appears in a different layer or stylesheet.

When a discrepancy appears:

1. Stop expanding the migration.
2. Reduce it to a deterministic fixture or live state.
3. Identify the winning v3 and v4 declarations, including origin, layer,
   specificity, order, and importance.
4. Find the ownership error.
5. Fix the abstraction, not only the observed page.
6. Add a regression that would have caught the defect.
7. Re-run the focused test, structural checks, and affected browser matrix.
8. Search for sibling instances of the same failure pattern.

## The feature and architecture being migrated

SpeleoDB uses one root Node workspace:

```text
package.json
package-lock.json
```

Nested Node manifests are forbidden.

There are two deliberately separate Tailwind products.

### Public Tailwind build

```text
Config:           tailwind_css/public/tailwind.config.js
CSS entrypoint:   tailwind_css/public/style.css
Generated output: frontend_public/static/css/style.css
```

The source contract must be exactly:

```text
frontend_public/templates/**/*.html
frontend_public/static/js/*.js
frontend_public/templatetags/people_tags.py
```

This intentionally scans public templates, only top-level public JavaScript,
and a Python template-tag source of grid classes. It intentionally does not
recursively scan every public JavaScript subtree.

### Private Tailwind build

```text
Config:           tailwind_css/private/tailwind.config.js
CSS entrypoint:   tailwind_css/private/style.css
Generated output: frontend_private/static/private/css/style.css
```

The source contract must be exactly:

```text
frontend_private/templates/**/*.html
frontend_public/templates/footer.html
frontend_private/static/private/js/*.js
frontend_private/static/private/js/map_viewer/**/*.js
speleodb/surveys/templatetags/project_types.py
```

This intentionally scans private templates, the shared public footer,
top-level private JavaScript, recursive map-viewer JavaScript/tests, and the
project-type Python class source. It intentionally excludes other private
JavaScript subtrees unless their classes are represented in scanned sources.

The builds overlap only where explicitly intended. Do not broaden either
source set. Do not let private candidates leak into public CSS or public-only
candidates leak into private CSS.

Both entrypoints are intended to use:

```css
@import 'tailwindcss' source(none);
@config "./tailwind.config.js";
```

with exact stylesheet-relative `@source` directives. Verify every relative
path from the stylesheet location. Do not accept automatic detection.

### Stylesheet composition in the browser

The actual loading order is part of the product contract:

1. Public pages: public generated Tailwind, then public custom CSS.
2. Private pages: private generated Tailwind, then private custom CSS.
3. Public GIS: public generated/custom, private generated/custom, shared modal,
   then map-viewer CSS.
4. Private map: private generated/custom, shared modal, then map-viewer CSS.
5. Page-level inline `<style>` blocks load where their Django blocks place them
   and can win through ordinary cascade order/specificity.

Any browser fixture that omits one of these stylesheets is not a parity test.
Any fixture that concatenates CSS in a different order is not a parity test.
Any static raw-template fixture that does not execute Django branches is not a
substitute for a rendered live route.

### Build interfaces that must remain stable

Keep these six script names and their output paths unchanged:

```text
build:tailwind:public
build:tailwind:private
dev:tailwind:public
dev:tailwind:private
pre-commit:tailwind:public
pre-commit:tailwind:private
```

They must use the v4 CLI binary and no legacy `-c` flags. Also preserve:

```text
npm run build
npm run dev
npm run pre-commit
npm run build:esbuild:private
npm run build:esbuild:public
```

Integration points:

- `compose/start` performs `npm ci` and starts all Tailwind/esbuild watchers.
- `railway.toml` relies on non-destructive `npm ci && npm run build`.
- CI uses a Node 24-compatible path.
- `.node-version` and Docker use Node 22.
- Pre-commit invokes root scripts.

Do not introduce Vite, PostCSS, a second workspace, nested manifests, or an
unrelated Node upgrade.

## Intended staged migration design—verify, do not assume

The staged implementation claims to do the following:

- Pin `tailwindcss` and `@tailwindcss/cli` to exact `4.3.1`.
- Pin forms and typography to exact `0.5.11` and `0.5.20`.
- Add reviewed npm 11 install-script approval for
  `@parcel/watcher@2.5.1` while retaining esbuild/fsevents approvals.
- Keep theme extensions and plugin registration in the two JavaScript configs.
- Remove obsolete `content`, `darkMode`, and JavaScript custom-variant
  ownership from configs.
- Load each config with adjacent `@config`.
- Use `source(none)` and exact CSS-owned source globs.
- Register forms once with `{ strategy: 'base' }` and typography once.
- Recreate class dark mode, legacy unguarded hover/group-hover, and private
  `sidebar-expanded` through CSS custom variants.
- Move v3 palette/default compatibility into
  `tailwind_css/shared/v3-compat.css`.
- Mechanically migrate removed/renamed utilities across templates and runtime
  JavaScript.
- Eliminate application coupling to Tailwind's private `--tw-*` variables.
- Preserve public/private behavior and generated output paths.

The shared compatibility file is roughly 774 added lines. It is the highest
risk concentration in the patch. Audit every token, selector, utility, layer,
browser behavior, and claimed derivation. “Mechanically derived” is not a
review exemption.

## Mandatory full index review

The staged diff currently touches approximately 155 files across:

- package manifests and lockfile;
- both Tailwind entrypoints and configs;
- shared compatibility CSS;
- private/public component CSS and custom CSS;
- nearly every public template;
- nearly every private template and shared modal/table snippet;
- runtime-generated map-viewer markup across panels, modals, stations,
  landmarks, tracks, uploads, notifications, and utilities;
- tests whose expected class strings changed;
- docs, AGENTS instructions, tasks, and lessons.

Review all of them. Build a checklist from `git diff --cached --name-status` and
account for each file. Mechanical repetition is still code. For bulk class
rewrites, prove every mapping by generated/computed behavior and search for
missed siblings, accidental edits outside scanner-owned sources, malformed
Django class attributes, and runtime strings outside source detection.

For every changed file ask:

- Was this change necessary for Tailwind v4?
- Does it preserve the exact v3 computed value?
- Did the migration alter specificity, layer, order, or state behavior?
- Is the candidate generated in the correct build?
- Does a later stylesheet or inline rule override it?
- Does dynamic/runtime markup still receive CSS despite source exclusions?
- Was a previously invalid v3 class accidentally made valid in v4?
- Was unrelated formatting or product behavior changed?
- Is user/API data still escaped before HTML insertion?
- Does the test verify behavior, or merely freeze the implementation mistake?

## Mandatory package and lockfile audit

Verify:

- Only the four intended Tailwind/plugin version changes and the required CLI
  transitive graph changed.
- No unrelated top-level dependency versions changed.
- The lockfile is reproducible with `npm ci` under Node 22 and Node 24.
- Optional native packages are present for the executing platform.
- `npm approve-scripts --allow-scripts-pending` has no unreviewed scripts.
- `@parcel/watcher` approval is necessary, pinned, and not cargo-culted.
- No Playwright dependency was added to the root workspace.
- No generated CSS/bundle became tracked.
- No nested `package.json` was added.
- Clean install does not rewrite the lockfile.

## Mandatory source-detection audit

Prove with contract tests and temporary sentinels:

- every intended public source generates a public-only sentinel;
- excluded public paths do not generate candidates;
- every intended private source generates a private-only sentinel;
- excluded private paths do not generate candidates;
- shared footer behavior appears where intended;
- public candidates do not leak private and vice versa;
- source paths are interpreted relative to the owning CSS file;
- watch-mode additions and deletions obey the same contract;
- a clean rebuild removes deleted candidates even if an active watcher caches
  them;
- Python-returned and runtime-generated class strings remain covered.

Do not let the static contract test merely assert strings in the entrypoint.
It must be backed by actual compiler behavior.

## Mandatory config, layer, plugin, and cascade audit

Verify:

- Font imports remain first and preserve weights/display behavior.
- Layer order is explicitly `theme → base → components → utilities`.
- Component-before-utility precedence matches v3.
- Flatpickr, public theme CSS, `x-cloak`, media rules, permission badges, forms,
  typography, headings, and buttons appear in the intended layer.
- Both configs retain every effective theme extension.
- The ineffective duplicate private `borderWidth: {3}` declaration is the
  only removed custom token with no behavior.
- Private custom shadow values still map to the correct utility names.
- Forms and typography are registered exactly once per build.
- Forms base strategy is actually equivalent for every `.form-*` consumer.
- Public GIS's dual generated stylesheets do not duplicate/reset components in
  a different winning order.
- Dark form compound selectors, permission badges, map rings, public custom
  duplicates, and component/utility collisions retain their v3 winners.
- Inline page styles and later custom/map styles are present in live tests.

## Mandatory Tailwind v3 compatibility audit

### Palette and color spaces

- Mechanically recapture the complete Tailwind 3.4.19 RGB palette from the
  installed v3 package.
- Verify all 242 color tokens plus black/white and every required alpha token.
- Ensure v4 OKLCH/P3 defaults cannot leak through utilities, Preflight, forms,
  typography, ring defaults, gradients, placeholders, or shadows.
- Verify sRGB alpha rounding and gradient interpolation pixel-for-pixel.
- Do not accept “equivalent” color serialization if pixels differ.

### Removed utilities

Audit all source-owned files and runtime markup for:

- `bg-opacity-*`, `text-opacity-*`, `border-opacity-*`, `divide-opacity-*`,
  and `ring-opacity-*`;
- `flex-shrink*` and `flex-grow*`;
- `overflow-ellipsis`;
- removed decoration families;
- legacy gradient names;
- classes generated in JavaScript outside recursively scanned directories.

Prove each replacement's computed behavior, including slash opacity.

### Renamed utilities and tokens

Audit shadow, drop-shadow, blur, backdrop-blur, radius, outline, and ring names
by computed value. Verify:

- v3 `rounded`/`rounded-sm`/etc. map to the intended pixel radii;
- every shadow retains all layers and alpha values;
- multi-drop-shadow output does not collapse into one function;
- outline width/color/style and transition behavior are unchanged;
- bare `ring` remains the v3 3px blue-500/50 default;
- explicit ring widths, colors, offsets, inset modes, focus rings, and map
  overrides are not disturbed.

### Borders and Preflight

Restore and verify:

- v3 bare border color gray-200;
- bare borders/dividers across cards, forms, tables, controls, modals, and map
  UI;
- placeholder color;
- button and role-button cursor behavior;
- disabled cursor;
- dialog centering;
- `[hidden]` behavior;
- option/form normalization;
- file-selector behavior;
- date/datetime native control layout and tabular numerals;
- checkbox/radio/indeterminate SVG rasterization and antialiasing;
- dark checked border behavior.

### Space and divide semantics

Tailwind v4's last-child/logical implementation is not automatically
equivalent to v3. Verify shared compatibility selectors preserve:

- `> :not([hidden]) ~ :not([hidden])` semantics;
- hidden children;
- x/y physical margin sides;
- reverse modes;
- divide border sides, styles, colors, and reverse modes;
- responsive variants;
- all introduced `v3-space-*` and `v3-divide-*` consumers.

Do not rewrite layouts wholesale to avoid the problem.

### Gradients

Verify:

- every `bg-gradient-*` migration uses the correct v4 linear direction and
  `/srgb` where required;
- from/via/to stop reset and transparent-stop behavior matches v3;
- arbitrary gradients, masks, commas, underscores, and slash alpha survive;
- gradient text preserves clipping and rasterization;
- decorative public gradients retain exact colors;
- no application CSS depends on `--tw-gradient-*`.

### `theme()` and arbitrary values

- Convert processed CSS and arbitrary candidates to supported v4 theme
  variables.
- Preserve ordinary inline `theme(...)` in `welcome_modal.html` only if the v3
  baseline proves it was invalid and the browser used the same fallback.
- Audit CSS variable shorthand, underscores, commas, slash opacity, masks,
  borders, grids, calculations, and gradients.
- Ensure v3-invalid `max-w-13` did not silently become a valid v4 class with a
  behavioral change.

### Important and variants

- Convert leading important syntax such as `!w-32` and `lg:!w-64` to trailing
  v4 syntax and prove precedence.
- Recreate class dark mode with v3 specificity.
- Restore unguarded v3 hover and group-hover behavior, including touch
  emulation.
- Verify group selector specificity and nesting.
- Rewrite order-sensitive stacks such as `before:hover`,
  `after:group-hover`, and `hover:prose-a` only where necessary.
- Prove equivalent stacks were not churned unnecessarily.
- Verify `sidebar-expanded` behavior and specificity.

### Transforms, animations, and transitions

- Remove handwritten dependencies on v3 transform variables.
- Verify v4 individual `translate`, `scale`, and `rotate` properties compose
  exactly with any static `transform` declarations.
- Verify AOS `translate3d` behavior.
- Verify the `shine`, `float`, and `endless` keyframes at deterministic start,
  midpoint, and endpoint states.
- Ensure `shine` does not apply static translation plus animated translation
  twice.
- Verify transition-property includes the same color, outline, transform,
  filter, backdrop-filter, and individual-transform behavior where required.
- Add explicit transition property lists only when computed behavior differs.

### Handwritten CSS and internal variables

- Remove redundant public utility copies only when generated utilities really
  replace them in every build/cascade.
- Replace permission, map-ring, and gradient `--tw-*` dependencies with stable
  declarations at the proper owner.
- Search all application CSS and JavaScript for private Tailwind variables.
- Compatibility/compiler-facing CSS may use v4 internals only when necessary
  and documented.
- Do not conflate “no internal variables” with “move the same broken rule to
  another stylesheet.”

## Known live regression that invalidates the first parity claim

The user found a real regression at:

```text
http://localhost:8000/private/project/38f2bfbb-f364-46b4-a326-3a3e9b1dec2e/browser/fe228d8cdfe0d351d7e8703b2eff2c1b8eed281a/
```

The “Download as ZIP” and “History: X commits” controls lost their visible
button shape; only text remained.

The v3 control contract included:

- a downward white → gray-100 surface (`#fff` → `#f3f4f6`);
- gray-600 label text (`#4b5563`);
- the `.btn` component's inline-flex alignment, padding, font weight, line
  height, transparent 1px border, shadow, transition, and centering;
- `rounded-full` overriding the base button radius;
- responsive `md:px-4` and `md:text-base`;
- existing mobile `.git_btn` sizing rules;
- unchanged ZIP/history icon geometry and strokes.

The first attempted repair merely moved/repeated a literal `.git_btn`
background rule and did not change the live result. The currently staged repair
puts these native v4 utilities directly on both anchors:

```text
bg-linear-to-b/srgb from-white to-gray-100
```

and removes background ownership from `.git_btn`, retaining that selector only
for mobile sizing.

This second repair was **not independently verified in the live container at
the time of handoff**. Treat it as suspect. Verify the rendered route after a
clean candidate build, with the real stylesheet order, no stale static asset,
the actual Django template, and the same data. Compare v3/v4 computed styles,
element screenshots, hover/focus/active/touch behavior, responsive geometry,
and pixels.

Then search for every other component whose visual contract is split between
generated utilities and a later custom/inline stylesheet. The existence of
this bug proves the original static harness was incomplete. Determine exactly
why it missed the regression and repair the harness before trusting any of its
other results.

The staged source-contract test that only counts these class strings is not
enough. It must be supplemented by actual compiled-output and browser behavior.

## Plugin and component UX audit

Compare v3 and v4 output and live behavior for:

- `.btn`, `.btn-lg`, `.btn-sm`, `.btn-xs`;
- headings `.h1` through `.h4` at every breakpoint;
- forms inputs, textarea, select, multiselect, checkbox, radio, switches,
  search controls, file controls, dates, and disabled/read-only states;
- typography/prose selectors and nested hover behavior;
- Flatpickr base, dark mode, focus, selected, range, disabled, and navigation
  states;
- permission badges and all permission-level colors;
- project lock/editing banners;
- map rings and selected/hovered map entities;
- public theme components and decorative effects;
- tables, dividers, modal actions, danger-zone controls, upload controls, Git
  browser rows, breadcrumbs, dropdowns, pagination, tags, and status badges;
- empty, loading, populated, error, success, denied, and read-only states.

Inspect component/utility collisions by winning declaration, not screenshot
alone.

## Public/private map-viewer requirements

Shared map behavior must remain aligned between:

```text
frontend_private/static/private/js/map_viewer/main.js
frontend_public/static/js/gis_view_main.js
```

Do not duplicate behavior. Verify all changed runtime class strings in map
viewer modules are generated by the correct stylesheet despite source
boundaries. Verify:

- project/country visibility controls;
- GPS tracks;
- station/cylinder/sensor/experiment/tag panels;
- surface stations and landmarks;
- notifications, uploads, forms, details, logs, resources, and modals;
- selected/unselected and hover/focus states;
- read-only/permission-disabled states;
- map overlays separately from nondeterministic canvas/tile pixels;
- public GIS dual-stylesheet composition;
- private map stylesheet composition;
- no unescaped user/API strings entered `innerHTML`, `.html()`, or
  `insertAdjacentHTML` during class rewrites.

No backend permission matrix or map behavior change is authorized.

## Baseline reconstruction

Create or verify a separate v3 worktree at the exact starting commit with
independent `node_modules`, using Node 22.22.2 through `mise`. Do not trust an
old `/tmp` directory without validating its commit, manifests, dependency
tree, and generated hashes.

Perform two clean v3 `npm ci` reproductions. Capture under `/tmp`:

- unminified and minified public/private CSS;
- SHA-256 hashes, bytes, and line counts;
- build timings and warnings;
- selector, at-rule, media-query, custom-property, keyframe, plugin-selector,
  and candidate-class inventories;
- exact source inventories;
- complete v3.4.19 palette and relevant defaults;
- actual stylesheet order on public, private, public-GIS, and private-map
  pages.

Expected v3 unminified references to independently reproduce:

```text
Public:
7daf1d31f6ebe3c959e5b774c3b14213d49fa59b5f79b22f1f3fce02afa3a1da
88,382 bytes
4,246 lines

Private:
f58cd60b449f37e6cae22a0dd1735ef1f8993f512bb7bed6c76108bb658c6f20
116,935 bytes
5,786 lines
```

If they do not reproduce, stop and explain the environmental or source
difference before comparing candidates.

Run `npx @tailwindcss/upgrade@4.3.1` only in a disposable copy after baseline
capture. Review its proposed changes; do not blindly reapply it to the working
tree.

## Existing candidate claims that must be treated as stale/suspect

The migration task currently records these pre-correction minified hashes:

```text
Public:
9991e46ba7e24ffc48876ee2d7300c22eb2f03e9e50e528b1fb3af631da306c1
85,680 bytes

Private:
b51ef37071d19341b2c7e320ce38db96fe20231add145f036853327e5b40dfa2
108,519 bytes
```

The Git-browser button correction changed source candidates after those values
were recorded. These hashes and all derived selector/size inventories are
stale until rebuilt and recaptured. Update the task and docs with the real
post-fix values.

The task also claims:

- three stable minified builds;
- 915 JavaScript tests in 45 files;
- 3,821 pytest passes and 154 skips;
- successful Node 22/24 clean installs;
- successful Docker/Railway/watch/pre-commit gates;
- 591 pinned-engine captures with zero differing pixels;
- zero installed-Chrome smoke pixels;
- no unreviewed install scripts.

Do not repeat these numbers as evidence. Reproduce them. The known live button
regression means the 591-capture claim did not cover or accurately compose the
full live UI. Audit the harness, route manifest, stylesheet loading, template
rendering, authentication, data fixtures, state setup, screenshot inputs,
computed-property list, masks, and result aggregation. A JSON summary generated
by a flawed harness proves nothing.

Temporary artifacts previously used were reported under:

```text
/tmp/speleodb-tailwind-v3-3334c10
/tmp/speleodb-tailwind-baseline
/tmp/speleodb-tailwind-candidate
/tmp/speleodb-tailwind-parity
```

They are clues, not trusted evidence. Rebuild or validate them independently.
Do not add Playwright to the root workspace.

## Structural candidate comparison

Compare v3 and final v4:

- all selectors and selector specificity;
- cascade layer membership and order;
- at-rules and registered properties;
- all breakpoint/media boundaries;
- all keyframes and animation values;
- forms/typography/Flatpickr/plugin selectors;
- all custom properties and defaults;
- all source candidate inventories;
- minified/unminified size and line counts;
- warnings and compiler output;
- deterministic build hashes across three clean minified builds.

Document every addition and removal. “Tailwind v4 emits different CSS” is not
an explanation. Identify why each structural difference is harmless or fix it.

## Live browser parity harness

Use temporary `@playwright/test@1.61.1` outside the root workspace with
identical pinned Chromium, Firefox, and WebKit binaries. Where automation is
permitted, also smoke-test installed Chrome 149, Firefox 151, and Safari 26.5.
Record exact browser revisions, launch constraints, commands, and results.

Run baseline and candidate from separate worktrees, separate ports, and cloned
deterministic databases. Do not compare static fragments as a replacement for
the live application.

Use:

- identical local Inter font files;
- stubbed external map/tile/live API traffic;
- fixed time, timezone, randomness, IDs, and data ordering;
- frozen AOS timing, transitions, canvas motion, and asynchronous loading for
  static captures;
- `document.fonts.ready`;
- deterministic animation start/midpoint/endpoint captures;
- real Django-rendered templates and authentication/permission setup;
- the exact production stylesheet order, including custom/map CSS and inline
  style blocks;
- cache-busted or freshly served generated CSS so stale assets cannot pass.

For every element plus `::before` and `::after`, compare relevant computed
properties including:

- geometry, display, position, flex/grid, gaps, margins, padding, overflow;
- font family/size/weight/style, line height, letter spacing, text decoration;
- text/fill/stroke/background colors and opacity;
- borders, radii, outlines, rings, shadows;
- gradients and background images;
- filters and backdrop filters;
- transforms and individual transform properties;
- transitions and animations;
- cursor, pointer events, appearance, visibility, content, and color scheme.

Compare pixels exactly. Mask only proven nondeterministic canvas/tile regions,
never ordinary DOM UI. Compare masked region overlays and computed styles
separately. Document every mask and why it cannot be deterministic.

## Required route and UX coverage

### Public routes and surfaces

- home;
- about;
- people;
- changelog;
- roadmap;
- download;
- call-to-action sections;
- privacy policy;
- terms and conditions;
- all footer variants;
- login;
- signup;
- signup closed;
- password-reset request;
- password-reset confirmation/key flow;
- auth base layouts and error states;
- Ariane webview;
- public GIS;
- welcome modal.

### Private routes and surfaces

- dashboard and every account/preferences/password/token/feedback page;
- project list and project details;
- project new/upload/history/revision browser/Git instructions;
- project mutex/editing flows;
- project user/team permission flows;
- project danger zone;
- teams, memberships, permissions, and danger flows;
- GPS tracks;
- station tags;
- surface networks and their detail/new/GIS/permission/danger flows;
- landmark collections and their equivalent flows;
- experiments, data viewer, GIS integration, permissions, and danger flows;
- sensor fleets, cylinders, histories, watchlists, permissions, and danger
  flows;
- GIS views and all detail/new/integration/danger flows;
- tools;
- private map viewer;
- shared confirmation/import/error/success/permission modals;
- shared sensor/cylinder/landmark tables;
- populated, empty, loading, error, success, read-only, and denied states.

### Roles and permission states

- anonymous;
- authenticated normal user;
- staff;
- superuser;
- read-only;
- read/write;
- project admin;
- team leader/admin;
- web-viewer;
- denied;
- disabled controls;
- project unlocked;
- locked by current user;
- locked by another user.

### Interaction states

- default;
- mouse hover;
- group hover;
- touch hover emulation;
- focus;
- focus-visible;
- active/pressed;
- checked and indeterminate;
- invalid;
- disabled;
- read-only;
- open and closed;
- expanded and collapsed;
- sidebar expanded;
- loading;
- success and error;
- selected and unselected;
- animation start, midpoint, endpoint.

### Required widths and DPR

Test breakpoint triplets:

```text
479 / 480 / 481
639 / 640 / 641
767 / 768 / 769
1023 / 1024 / 1025
1279 / 1280 / 1281
1535 / 1536 / 1537
```

Also test:

```text
360x800
390x844
768x1024
1024x768
1280x800
1440x900
1920x1080
```

Use DPR 1 and 2 where the engine supports it.

## Accessibility and interaction requirements

The migration must not change:

- visible focus indication;
- focus-visible versus focus behavior;
- keyboard navigation and tab order;
- pointer cursor and disabled cursor behavior;
- target dimensions;
- control appearance and checked/disabled/read-only affordances;
- text contrast;
- hidden and screen-reader behavior;
- modal open/close and backdrop behavior;
- dropdown/menu expanded state;
- hover-only information accessibility;
- reduced-motion behavior where present.

Run relevant accessibility checks, but do not treat an automated audit as a
substitute for interaction-state comparison.

## Performance requirements

Record and compare:

- public/private minified and unminified size;
- full-build time;
- individual Tailwind build time;
- watch startup and rebuild time;
- selector/custom-property/theme-variable counts;
- browser style-recalculation timing on representative public/private/map
  pages;
- any added runtime work.

The compatibility layer must not add runtime DOM scans or JavaScript. Source
detection must remain bounded. Investigate material CSS-size or style-recalc
growth; do not merely document it.

## Required repository, clean-install, watcher, and deployment gates

After fixes, run and record:

```bash
npm run build:clean
npm run build:tailwind:public
npm run build:tailwind:private
npm run build:esbuild:private
npm run build:esbuild:public
npm run build
npm run lint:js
npm run test:js
npm run pre-commit
```

Also run:

```bash
python manage.py validate_templates --settings config.settings.test --ignore-app allauth
pytest
prek run --all-files --show-diff-on-failure
git diff --check
git diff --cached --check
npm approve-scripts --allow-scripts-pending
```

In disposable worktrees, run clean `npm ci` plus build/lint/tests under:

- configured Node 22;
- CI-compatible Node 24.

Verify:

- `npm run dev` starts both Tailwind and both esbuild watcher groups;
- public sentinel changes rebuild only public candidates;
- private sentinel changes rebuild only private candidates;
- deletions are removed by a clean build;
- watchers terminate cleanly;
- Docker Node 22 development path works;
- Railway's exact non-destructive `npm ci && npm run build` works;
- clean installs do not mutate tracked files;
- generated CSS/bundles remain ignored;
- no temporary browser dependency enters the root lockfile.

If the user is already running npm/tests in a container, coordinate rather
than launching a competing build. Accept their output only with exact command,
environment, revision, and complete result; independently inspect the emitted
artifacts afterward.

## Documentation requirements

Review and correct:

- `AGENTS.md`;
- `docs/node-tooling.md`;
- `docs/tailwind-v4.md`;
- `docs/README.md` index;
- `tasks/todos/tailwind-v4-migration.md` review;
- genuine lessons under `tasks/lessons/`.

Documentation must explain:

- feature intent and strict-parity contract;
- browser requirements;
- public/private build ownership;
- disabled automatic detection;
- CSS-owned source and variant contracts;
- legacy config/plugin ownership;
- compatibility theme responsibilities;
- layer/cascade design;
- forms/typography strategy;
- dark/hover/group-hover/sidebar semantics;
- public GIS dual-stylesheet composition;
- removal of application `--tw-*` coupling;
- verification strategy and actual limitations;
- performance impact;
- criteria for future shim removal;
- every discovered discrepancy and its resolution.

Delete or correct any claim invalidated by the live button regression or
subsequent fixes. Do not leave stale hashes, counts, timings, or “zero
difference” language in the task/docs.

## Scope constraints

- No backend API or schema changes.
- No product redesign.
- No opportunistic dependency upgrades.
- No broad unrelated cleanup.
- No duplicated public/private implementation when shared behavior exists.
- No expensive runtime compatibility layer.
- No generated assets committed.
- No Playwright in the root workspace.
- No weakening or deleting tests just to make the migration pass.
- No `Utils.raw()` or unescaped user/API data added to HTML sinks.
- No hand-waved residual differences.

## Completion standard

You may declare this migration complete only when all of the following are
true:

- Every staged file and hunk has been reviewed and accounted for.
- Every unnecessary or unrelated change has been removed.
- The package/lockfile graph is minimal and reproducible.
- Both source contracts are proven with actual compiler sentinel tests.
- All v3 compatibility mappings are justified by generated and computed
  behavior.
- The Git-browser button regression is fixed and live-verified.
- The flawed parity-harness gap that missed it is understood and repaired.
- All routes, roles, states, breakpoints, stylesheet compositions, and browser
  engines in scope have evidence.
- Structural differences are fully inventoried and explained.
- Computed styles match or have a proven serialization-only explanation.
- Deterministic pixels are exactly equal.
- Behavioral and interaction tests pass.
- Repository, clean-install, watcher, Docker, Railway, lint, type, and test
  gates pass.
- Documentation and task evidence match the final source and artifacts.
- The original prompt file is preserved with the required index state.
- No unexplained residual risk remains.

If exhaustive live verification cannot be completed, say exactly what remains
unproven and do **not** check the final completion box. “Everything else
passes” is not completion.

## Required final report

Return:

1. Findings first, ordered by severity, each with exact file/line and observed
   impact.
2. Root cause for each finding.
3. The fix and why its ownership boundary is correct.
4. Regression tests added.
5. Full command/environment/results table.
6. Baseline and final CSS hashes, sizes, selector/property counts, and timings.
7. Browser/route/role/state/viewport/capture counts and differing-pixel count.
8. Every mask and serialization-only computed-style difference.
9. Git status distinguishing staged original work, unstaged repairs, ignored
   generated artifacts, and preserved untracked files.
10. Remaining risk or an explicit statement that none remains, supported by
    evidence.

Do not congratulate the migration. Prove it.
