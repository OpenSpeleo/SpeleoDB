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
- `npm run test:js`
- `npm run lint:js`
- `npm run build`

Rendered Django tests cover permissions, team badges, and private navigation.
DOM/controller tests cover native map toggles and modal visibility. Compile all
Django templates and verify every logical asset entry in the clean Vite
manifest. These changes add no database queries or map feature scans; native
labels remove redundant click handling.
