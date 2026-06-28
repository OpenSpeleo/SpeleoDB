# Tailwind CSS 4 Architecture

## Intent

SpeleoDB compiles CSS with exact `tailwindcss@4.3.1` and
`@tailwindcss/vite@4.3.1` inside the Vite 8.1.0 graph. The migration is
required to retain the rendered
contract established by Tailwind 3.4.19; parity is a release condition, not an
assumption. The private application is the visual/configuration reference. The
public application intentionally converges on its typography tokens while
retaining namespaced marketing components.

The supported browser floor is Tailwind v4's official floor: Chrome 111+,
Safari 16.4+, and Firefox 128+.

## Single-bundle ownership

`tailwind_css/style.css` is the only Tailwind source entrypoint. Vite registers
it as `style-app` and emits a hashed stylesheet under
`speleodb/common/static/speleodb/vite/assets/`. Every public and private
document that uses Tailwind requests that logical asset exactly once through
the Django manifest tags.

The neutral entrypoint imports `tailwind_css/private/style.css` unchanged. That
file remains the canonical theme, font, variant, private component, and private
source contract, but it is not built or shipped independently. The neutral
entrypoint adds public templates, top-level public JavaScript, the people
template tags, public animations, and `tailwind_css/public/components.css`.

Automatic detection stays disabled by the imported private reference. All
sources remain explicit, stylesheet-relative `@source` directives. Compiler
contracts build a mirrored union tree and prove all supported public/private
sentinels are present while unsupported nested trees remain absent.

The shared design system registers forms and typography once. The forms plugin
uses its base strategy because SpeleoDB owns `.form-*` components. JavaScript
configs, `@config`, automatic detection, CLI `-c`, and a second generated
Tailwind asset are prohibited.

## Layers and stylesheet composition

The bundle uses explicit Tailwind `theme`, `base`, `components`, and
`utilities` layers. The unchanged private reference loads its font, shared
design system, private components, and utility overrides in their established
order. Namespaced public components join the components layer without
redefining `.btn`, `.h*`, or `.form-*`.

The migration-owned stylesheet order in the rendered templates is:

1. Public pages: unified Tailwind, then public custom CSS.
2. Private pages: unified Tailwind, then private custom CSS.
3. Public GIS: unified Tailwind, public custom, private custom, shared modal,
   map-viewer CSS, then Mapbox GL CSS.
4. Private map: unified Tailwind, private custom, the base template's extracted
   responsive style entry, Mapbox GL CSS, shared modal, then map-viewer CSS.

Public GIS is the strongest cascade regression case because it combines both
application custom layers even though Tailwind now loads once. Page-level
static styles are Vite entries rendered at their former Django block location
and participate in the ordinary cascade. A parity harness must use the rendered order,
including Mapbox, even when external traffic is deterministically stubbed.

## Public convergence boundary

Public headings, buttons, and authentication inputs use durable `site-*`
components. Button/form geometry and marketing colors remain public-owned;
typography resolves through the private `text-*` and `tracking-*` tokens. The
public document separately requests Inter 800, so adding that weight does not
change private font rendering. Public GIS map and welcome-modal controls retain
the private `.btn` contract.

The accepted public visual delta is limited to the private font-size,
line-height, and letter-spacing values, resulting text reflow, and consistent
public header components on GIS. Private pages permit no unexplained visual or
computed-style difference.

## Design-system foundation

`tailwind_css/shared/design-system.css` is shared, product-owned Tailwind CSS.
Its original values were verified against the clean Tailwind 3.4.19 baseline,
but their continuing owner is SpeleoDB's visual contract—not the previous
compiler. It owns:

- the complete product RGB palette, including explicit sRGB-alpha tokens where
  Tailwind's default OKLab mixing changes rendered color;
- product radius, shadow, drop-shadow, blur, default-border, and default-ring
  tokens;
- placeholder, pointer cursor, disabled cursor, dialog, option, and form
  browser normalization;
- hidden-aware sibling flow and row-divider utilities, including reverse mode;
- literal gradients, grid backgrounds, exact ring stacks, transform helpers,
  and transition surfaces required by the application.

When Tailwind v4 core cannot express one of those contracts, the custom
utility gets a durable semantic name such as `srgb-*`, `flow-*`,
`row-divide-*`, or `grid-pattern-*`. Production classes and variables must not
carry a migration-version prefix.

Class-controlled dark mode, unguarded v3 hover/group-hover behavior, and the
private `sidebar-expanded` variant remain in the imported private reference.
Feature selectors and stable project variables remain in their application
stylesheet. Only
compiler-facing utilities may couple to Tailwind's private implementation
variables, and that coupling must stay inside the design-system boundary.

## Document color scheme

Every SpeleoDB-owned root document declares the standard dark color scheme and
the Dark Reader lock before loading stylesheets. The shared design system also
sets `color-scheme: dark` on `:root`; the standalone error stylesheet owns the
same declaration for error documents. The private root retains `.dark` because
private variants are class-controlled. Public roots deliberately do not gain
that class: the unified bundle contains the private class-controlled variants,
and activating them would change the public cascade.

## Candidate migration rules

Legacy opacity utilities, `flex-shrink`/`flex-grow`, ellipsis, decoration,
important-prefix, gradient, radius, shadow, blur, and outline names were
converted to supported v4 candidates. Order-sensitive stacks were reversed
only where v4 changed nesting order. Processed `theme()` calls now use theme
variables; the ordinary inline `theme(...)` in the welcome modal remains
unchanged because v3 never processed it and the browser already used its
fallback.

Handwritten CSS must use literal declarations or stable project variables.
Application CSS and runtime JavaScript must not depend on Tailwind's private
`--tw-*` implementation variables. In particular, permission colors, map
rings, and public decorative gradients are owned by stable declarations. The
Git-browser action surface is intended to use the native
`bg-linear-to-b/srgb from-white to-gray-100` utility stack; `.git_btn` remains
only as its responsive sizing hook. A clean-build, hash-checked live-route
matrix proves both rendered anchors at 360/767/768/769/1440, DPR 1/2, and the
default, hover, focus, focus-visible, active, and touch-hover states in pinned
Chromium, Firefox, and WebKit. The design-system stylesheet may set v4
internals only when it is implementing a compiler-facing utility.

## Verification strategy

The migration baseline is a clean Tailwind 3.4.19 worktree. Baseline and final
candidate hashes, sizes, inventories, timings, and test counts belong in the
active adversarial review record only after they have been regenerated. Values
from the original migration handoff and existing `/tmp` artifacts are stale or
untrusted and must not be copied forward as release evidence.

Structural comparison covers selectors, at-rules, media queries, keyframes,
plugin selectors, custom properties, and source candidate inventories. Raw
selector text is expected to change because v4 emits native nesting,
registered properties, and range media syntax; keyframe and breakpoint sets
must remain behaviorally equivalent.

A temporary Playwright 1.61.1 harness must live outside the root workspace. It
must navigate separate live baseline and candidate Django servers with cloned,
deterministic databases and real authentication/permission fixtures. It must
verify served asset hashes, rendered DOM alignment, production stylesheet
order, computed styles including pseudo-elements, interactions, accessibility,
responsive states, and deterministic pixels in Chromium, Firefox, and WebKit.
Every serialization normalizer and screenshot mask requires structured,
reproducible justification. The temporary harness and browser dependencies are
not repository dependencies.

The original parity result is invalid as live-route evidence. Its broad capture
script sanitized raw Django template source and injected it through
`page.setContent`; Django inheritance, includes, conditionals, authentication,
and runtime composition were not executed. The focused Git-button follow-up
also used hand-written, pre-fix markup instead of both rendered controls, and
read an ignored candidate stylesheet retained by a running Tailwind watcher.
The old script did concatenate custom CSS, so the failure has not been shown to
come from omitting `custom.css`. The proven causes are synthetic template
rendering, hard-coded markup, and stale generated CSS.

Before any browser run, stop the watcher, run `npm run build` (or clean and
rebuild every output required by the route), start isolated servers on separate
ports, and prove that each server returns the expected fresh asset. A browser
manifest must fail rather than skip a route, role, state, viewport, or engine
that it claims to cover.

Required repository gates remain the root builds, JavaScript lint/tests,
Django template validation, pytest, pre-commit, clean installs on Node 22 and
Node 24, watcher isolation, and deployment build contracts.

The focused Git route is not a substitute for the release matrix. The active
adversarial review deliberately remains incomplete until every required
public/private route, role and permission state, breakpoint/device/DPR,
interaction and accessibility state, animation point, and map composition has
the same live, deterministic evidence. The superseded raw-template capture
total must not be quoted as that evidence.

## Performance and removal plan

Automatic source discovery is disabled, which bounds the single compiler to
the explicit union source set. The design-system foundation adds no runtime
JavaScript or DOM scans. Exact hashes, compressed sizes, structural
inventories, and environment details live in the active single-bundle review
rather than this architecture document.

A real-route Chromium probe over 20 forced full-style passes found public-home
style recalculation approximately flat (10.00→9.86 ms median for 292 nodes)
and the private Git route increased from 15.06 to 23.56 ms for 488 nodes,
about 0.43 ms per forced pass. An in-transit ablation attributed the private
increase to Tailwind 4's compiler-generated registered/custom-property surface,
not application runtime work. Removing or postprocessing that compiler-owned
cross-engine fallback would be a compatibility change and is not part of this
migration. Representative map-page timing remains an open release-evidence
item.

Tailwind watch mode retains a candidate after its sole template occurrence is
deleted. Restarting with a clean one-shot build removes it. Therefore watcher
output is useful during development but is never parity evidence; browser
certification begins from `npm run build` and a verified served manifest hash.
The Vite watcher does correctly rebuild imported CSS changes and deletions,
Tailwind source additions, shared modules, and route controllers. The isolated
watcher contract reproduces those boundaries without disturbing Django or a
developer's running watcher.

Custom design-system rules may be removed only after all consumers of the
affected product behavior have been intentionally redesigned and the same
structural, computed-style, and pixel suites approve the change. Do not remove
a rule just because a v4 utility has a similar name.
