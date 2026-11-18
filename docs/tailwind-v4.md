# Tailwind CSS Architecture

## Intent

SpeleoDB compiles CSS with `tailwindcss` and `@tailwindcss/vite` inside the Vite
graph. Exact versions belong to the root manifest and lockfile. The private
application is the visual/configuration reference. The public application
intentionally converges on its typography tokens while retaining namespaced
marketing components.

The CSS browser floor follows Tailwind's documented minimum Chrome, Safari, and
Firefox releases in its
[browser support contract](https://tailwindcss.com/docs/compatibility#browser-support).
Older browsers are unsupported. Compiler upgrades must not silently raise that
floor; dependency versions are owned by `package.json` and `bun.lock`.

Compiler and tooling changes must preserve the rendered product contract.
Private pages permit no unexplained visual or computed-style differences;
intentional design changes require their own product scope.

## Single-bundle ownership

`tailwind_css/style.css` is the only Tailwind source entrypoint. Vite registers
it as `style-app` and emits a hashed stylesheet under
`speleodb/common/static/speleodb/vite/assets/`. Every public and private
document that uses Tailwind requests that logical asset exactly once through the
Django manifest tags.

The neutral entrypoint imports `tailwind_css/private/style.css`. That file
remains the canonical theme, font, variant, private component, and private
source contract, but it is not built or shipped independently. The neutral
entrypoint adds public templates, top-level public TypeScript, the people
template tags, public animations, and `tailwind_css/public/components.css`.

Automatic detection stays disabled by the imported private reference. All
sources remain explicit, stylesheet-relative `@source` directives. Compiler
contracts build a mirrored union tree and prove all supported public/private
sentinels are present while unsupported nested trees remain absent.

Runtime source directives select `.ts` at the original directory depth. The
private theme and component reference stays intact, and tests within the
explicit source patterns are scanned. Type declarations live outside these
source roots. Use clean production CSS when comparing the generated source set.

The shared design system registers forms and typography once. The forms plugin
uses its base strategy because SpeleoDB owns `.form-*` components. JavaScript
configs, `@config`, automatic detection, CLI `-c`, and a second generated
Tailwind asset are prohibited.

## Layers and stylesheet composition

The bundle uses explicit Tailwind `theme`, `base`, `components`, and `utilities`
layers. The unchanged private reference loads its font, shared design system,
private components, and utility overrides in their established order. Namespaced
public components join the components layer without redefining `.btn`, `.h*`, or
`.form-*`.

The stylesheet order in the rendered templates is:

1. Public pages: unified Tailwind, then public custom CSS.
2. Private pages: unified Tailwind, then private custom CSS.
3. Public GIS: unified Tailwind, public shell, private shell, shared modal, then
   map-viewer CSS.
4. Private map: unified Tailwind, private shell, the base template's extracted
   responsive style entry, shared modal, map-viewer CSS, then geometry and
   import styles.

The map-viewer stylesheet imports MapLibre's CSS before its application rules;
there is no separate Mapbox GL stylesheet. Route and included-template styles
retain their template positions.

Public GIS is the strongest cascade regression case because it combines both
application custom layers with one Tailwind asset. Page-level static styles are
Vite entries rendered at their former Django block location and participate in
the ordinary cascade. Inspect the actual rendered order, including renderer
styles, when diagnosing a cascade issue.

## Public convergence boundary

Public headings, buttons, and authentication inputs use durable `site-*`
components. Button/form geometry and marketing colors remain public-owned;
typography resolves through the private `text-*` and `tracking-*` tokens. The
public document separately requests Inter 800, so adding that weight does not
change private font rendering. Public GIS map and welcome-modal controls retain
the private `.btn` contract.

Public font-size, line-height, and letter-spacing derive from the private
tokens. This convergence permits the resulting text reflow and consistent public
header components on GIS, not unrelated layout or color changes. Public geometry
and marketing components remain separately owned; changes to shared tokens
require reviewing both public and private consumers.

## Design-system foundation

`tailwind_css/shared/design-system.css` is shared, product-owned Tailwind CSS.
Its values define SpeleoDB's visual contract. It owns:

- the complete product RGB palette, including explicit sRGB-alpha tokens where
  Tailwind's default OKLab mixing changes rendered color;
- product radius, shadow, drop-shadow, blur, default-border, and default-ring
  tokens;
- placeholder, pointer cursor, disabled cursor, dialog, option, and form browser
  normalization;
- hidden-aware sibling flow and row-divider utilities, including reverse mode;
- literal gradients, grid backgrounds, exact ring stacks, transform helpers, and
  transition surfaces required by the application.

When Tailwind core cannot express one of those contracts, the custom utility
gets a durable semantic name such as `srgb-*`, `flow-*`, `row-divide-*`, or
`grid-pattern-*`. Production classes and variables must not carry a
migration-version prefix.

Class-controlled dark mode, unguarded hover/group-hover behavior, and the
private `sidebar-expanded` variant remain in the imported private reference.
Feature selectors and stable project variables remain in their application
stylesheet. Only compiler-facing utilities may couple to Tailwind's private
implementation variables, and that coupling must stay inside the design-system
boundary.

## Document color scheme

Every SpeleoDB-owned root document declares the standard dark color scheme and
the Dark Reader lock before loading stylesheets. The shared design system also
sets `color-scheme: dark` on `:root`; the standalone error stylesheet owns the
same declaration for error documents. The private root retains `.dark` because
private variants are class-controlled. Public roots deliberately do not gain
that class: the unified bundle contains the private class-controlled variants,
and activating them would change the public cascade.

The rendered-document tests inspect HTML metadata attributes and their order
before stylesheets, accepting either spelling of void tags (`>` or `/>`). They
also retain the private/public root class distinction and unified stylesheet
count and cascade checks. This keeps the theme contract independent of template
formatter output.

## Utility and application CSS boundaries

Handwritten CSS must use literal declarations or stable project variables.
Application CSS and runtime JavaScript must not depend on Tailwind's private
`--tw-*` implementation variables. In particular, permission colors, map rings,
and public decorative gradients are owned by stable declarations.

The Git-browser action surface uses
`bg-linear-to-b/srgb from-white to-gray-100`; `.git_btn` owns responsive sizing.
The design-system stylesheet may use compiler internals only when implementing a
compiler-facing utility.

## Verification and performance

Use a clean finite build when inspecting generated CSS. Stop the local webserver
and its watcher before `bun run build` in the existing application container,
then verify the asset manifest actually served by Django. Watch output can
contain older hashed assets; its presence alone does not prove current delivery.

Compiler contracts cover explicit source inclusion, plugin selectors, theme
metadata, and stylesheet count/order. Rendered Django tests protect dark-scheme
metadata and the private/public root distinction. Relevant frontend tests
protect application behavior. `make test` runs backend, frontend, and browser
targets; see the Makefile and `tests/browser/README.md` for their execution
boundaries. Browser tests protect complex UI/UX workflows, not static styling or
exhaustive pixel comparisons. Do not introduce screenshot comparisons, GPU
capture, or performance benchmarks as routine browser coverage.

For a visual change, inspect the real rendered page and affected responsive and
interaction states. Raw template source or hand-built markup cannot reproduce
Django inheritance, permissions, includes, and controller composition. Report
only the routes, states, and browsers actually inspected. Keep task-specific
captures, timings, and results outside the checkout.

Automatic source discovery is disabled, bounding compilation to the explicit
source set. The shared design system adds no runtime JavaScript or DOM scans. A
generated stylesheet's size alone does not establish rendering performance; any
separately authorized benchmark needs comparable builds and environments. Remove
a custom rule only after identifying its consumers and verifying that the
intended replacement preserves their behavior. Similar utility names do not
establish equivalence.

Contributor guidance:
[CSS candidate rewrites](agent-practices.md#css-candidate-rewrites).
