# Tailwind CSS-Native Configuration Consolidation

> Superseded as the production architecture by
> `tasks/todos/tailwind-single-bundle-consolidation.md`. This record describes
> the intermediate configuration-only consolidation that still emitted two
> Tailwind assets.

## Goal

Replace the two legacy JavaScript Tailwind configurations with one shared,
CSS-native Tailwind 4 foundation while retaining the public/private build
boundaries and every existing application-owned computed style. Declare every
SpeleoDB-owned document as dark and prevent Dark Reader from reprocessing it.

## Checklist

- [x] Capture the clean pre-refactor Git state and minified/unminified CSS.
- [x] Move shared plugins and theme tokens into the shared design system.
- [x] Preserve public-only and private-only theme values in their entrypoints.
- [x] Remove both JavaScript configs and every production `@config` reference.
- [x] Add dark-scheme metadata and CSS declarations to every owned root document.
- [x] Strengthen compiler, source-isolation, token, plugin, and script contracts.
- [x] Add rendered tests for public, private, webview, and error document roots.
- [x] Verify shared and entrypoint-specific watcher dependency behavior.
- [x] Prove structural, computed-style, and pixel parity against the frozen baseline.
- [ ] Run repository, Node-version, Docker, and Railway build gates.
- [x] Update architecture, tooling, agent guidance, audit evidence, and lessons.

## Compatibility Ledger

| Area | Baseline evidence | Risk | Falsifying test | Conclusion / repair proof |
|---|---|---|---|---|
| Git and generated assets | Clean `dsf` at `c1977452…`; public/private baseline hashes frozen before edits | Stale ignored CSS or accidental branch/index changes | Git checkpoints and clean hashes | Branch/index preserved; three clean builds deterministic |
| Shared plugins and tokens | Pre-refactor generated CSS and both JS configs | Plugin duplication, layer movement, or changed declarations | Compiler contract and output inventory | One shared forms/typography registration; 15 contracts pass |
| Public entrypoint | `87f0682d…` minified, `62ea39df…` unminified | Typography, tracking, or animation drift | Public fixture, computed styles, and pixels | `6e4b5ec0…`; only added declaration is `color-scheme: dark` |
| Private entrypoint | `d2313d41…` minified, `4076eaf8…` unminified | Typography, breakpoint, size, border, outline, or shadow drift | Private fixture, computed styles, and pixels | `a026197f…`; only added declaration is `color-scheme: dark` |
| Source isolation | Existing mirrored compiler sentinel suite | Public/private candidate leakage | Temporary mirrored source compilation | Public-only and private-only CSS-native values remain isolated |
| Document themes | Private root already dark; other roots undeclared | Public GIS `.dark` activation or browser-extension recoloring | Rendered roots, computed `color-scheme`, extension run | Four rendered roots pass; public roots have no `.dark`; Dark Reader 4.9.125 injects 9 styles into the unlocked control and 0 into locked/SpeleoDB pages |
| Build integrations | Six stable Tailwind script names and output paths | Broken dev, pre-commit, CI, Docker, or Railway commands | Exact command matrix | Production/pre-commit and Node 22/24 gates pass; CSS-aware wrapper repairs imported-CSS watch invalidation |

## Review

The implementation is complete and all observed CSS differences are explained:
unminified output differs only by the three-line dark root rule, and removing
its 24-byte minified form yields exact byte identity. Chromium, Firefox, and
WebKit produced zero differing application pixels for public/private fixtures;
all computed roots were dark. Full results: 923 JavaScript tests on Node 22 and
24, 3,823 pytest tests with 156 skips, zero template errors, full `prek`, lint,
pre-commit, three deterministic clean builds, and watcher ownership checks.

The completion gate remains unchecked because the local Docker daemon is not
running, Railway's complete migrate/collectstatic command was not reproduced,
and the pre-existing exhaustive live route/role/permission matrix was not
repeated. These are verification limitations, not unexplained CSS differences.
