# Django template linting

HTML participates in pre-commit formatting and linting. djLint uses the existing
Django profile in `pyproject.toml`; rules remain enabled globally. Templates
keep the Vite asset registry and inert controller JSON contract.

## Markup and behavior

Keep opening and closing HTML tags balanced within Django branches. Prefer one
shared element with conditional attributes when branches differ only in styling;
this preserves permission decisions without relying on browser error recovery.
Navigation links must not contain buttons or forms, and buttons must not contain
links or checkboxes. Both map viewers use native checkbox labels; the checkbox's
change event owns the action, avoiding duplicate toggles from wrapper clicks.

Explicit button types preserve intent: form actions submit, while modal
controls, copy actions, and other JavaScript controls use `button`. SVG paths
self-close.

## Style ownership

Static presentation belongs in existing owning stylesheets or equivalent
Tailwind utilities. Check the cascade when replacing inline declarations:
unlayered CSS and responsive selectors can override utilities. Runtime inline
display and map size updates must remain able to override initial styles.

The private shell's `initially-hidden` class sets `display: none` without
`!important`, preserving existing jQuery show/hide and explicit flex display.
Git explorer and revision-history prototype rows instead use their original IDs
as CSS selectors: controllers already remove those IDs from visible clones.

Model-driven colors and palette swatches retain their server-rendered styles
with local, explained H021 exceptions. Moving model values into static CSS would
break the model-driven color contract. The export email retains its existing
inline style exception for mail clients.

## Verification and performance

Review files individually against HEAD, check the relevant controller when
markup or visibility changes, run djLint lint/format checks, then stage each
reviewed file. Run checks in the existing application container:

- `djlint <tracked HTML files> --check --lint`
- `prek run djlint-reformat-django --all-files`
- `prek run djlint-django --all-files`
- `pytest frontend_private/tests/test_template_lint_regressions.py`
- `bun run test:frontend`
- `bun run lint:frontend`
- `bun run build`

Rendered Django tests cover permissions, team badges, and private navigation.
DOM/controller tests cover native map toggles and modal visibility. Compile all
Django templates and verify every logical asset entry in the clean Vite
manifest. These changes add no database queries or map feature scans; native
labels remove redundant click handling.

Behavioral template contracts should inspect the relevant element's attributes,
classes, and rendered dimensions rather than exact HTML serialization. Void-tag
slash spelling is immaterial. Match charts to their actual container/canvas, and
keep dark-scheme values, Dark Reader lock placement, private-only `.dark`, and
stylesheet order assertions explicit when extracting styles.

Alpine application expressions belong in `frontend_common/bindings/*.ts`.
Templates use inert `data-speleodb-bind` and `data-speleodb-scope` markers; keep
transition classes, `x-cloak`, and named `x-ref` declarations in their original
locations. Initial preference values use inert data attributes. Do not replace
an expression with an `x-bind` string: executable attributes remain prohibited.
See [typed Alpine ownership](typescript-architecture.md#typed-alpine-ownership)
for controller registration and the real-vendor verification contract.

The ten private entity menus share `bindings/menu.ts` mechanics, with each
template's inert prefix and number of close links registered explicitly in
`bindings/private.ts`. Scope creation always returns fresh state. Entity menus
retain ordinary clicks and outside dismissal without ARIA, Escape or focus
handlers. Private user and revision menus select their original directive
modifiers individually; revision focus and cloned-menu policies remain distinct.
Sidebar, public navigation, welcome and preference bindings keep their own state
and behavior. Real-vendor tests cover every entity menu, outside dismissal,
transition settlement, independent clones and the intentional policy
differences. This consolidation adds no listeners or layout work beyond the
existing bindings.
