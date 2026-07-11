# AGENTS.md

Guidance for AI/code agents working in the SpeleoDB repository.

This file is intentionally opinionated and feature-focused so agents can make
correct changes without re-discovering architecture every session.

## Core Principles

- **Simplicity First**: Make every change as simple as possible. Impact minimal
  code.
- **No Laziness**: Find root causes. No temporary fixes. Principal Engineer
  standards
- **Minimat Impact**: Changes should only touch what's necessary. Avoid
  introducing bugs or changing unrelated parts of the code.
- **Readability & Maintainability**: Preserve product behavior while improving
  maintainability.
- **Performance Conscious**: Be aware of the performance impact of your changes
  and try to minimize the impact on performance, whether it's N+1 SQL queries or
  heavy compute.
- **Refactor as necessary**: Prefer centralized logic over duplicated
  conditionals or per-call custom checks.
- **Tests are cheap**: Every behavior should be tested. Untested code is broken
  code.

## Task Management

1. **Plan First**: Write plan to `tasks/todos/` with checkable items
2. **Verify Plan**: Check in before starting implementation
3. **Track Progress**: Mark items complete as you go
4. **Explain Changes**: High-level summary at each step
5. **Document Results**: Add review section to tasks/todo.md"
6. **Capture Lessons**: Update `tasks/lessons/` after corrections
7. **Documentation is Key**: Document each feature and design inside `docs/`.
   What is the feature being implemented, the design space and intents and a
   rapid summary of the approach taken with key APIs & concepts.

## Workflow Orchestration

### 1. Plan Node Default

- Enter plan mode for ANY non-trivial task (3+ steps or architectural decisions)
- If something goes sideways, STOP and re-plan immediately - don't keep pushing
- Use plan mode for verification steps, not just building
- Write detailed specs upfront to reduce ambiguity

### 2. Subagent Strategy

- Use subagents liberally to keep main context window clean
- Offload research, exploration, and parallel analysis to subagents
- For complex problems, throw more compute at it via subagents
- One tack per subagent for focused execution

### 3. Self-Improvement Loop

- After ANY correction from the user: update `tasks/lessons/` with the pattern
- Write rules for yourself that prevent the same mistake
- Ruthlessly iterate on these lessons until mistake rate drops
- Review lessons at session start for relevant project

### 4. Verification Before Done

- Never mark a task complete without proving it works
- Diff behavior between main and your changes when relevant
- Ask yourself: "Would a staff engineer approve this?"
- Run tests, check logs, demonstrate correctness

### 5. Demand Elegance (Balanced)

- For non-trivial changes: pause and ask "is there a more elegant way?"
- If a fix feels hacky: "Knowing everything I know now, implement the elegant
  solution"
- Skip this for simple, obvious fixes - don't over-engineer
- Challenge your own work before presenting it

### 6. Autonomous Bug Fizing

- When given a bug report: just fix it. Don't ask for hand-holding
- Point at logs, errors, failing tests - then resolve them
- Zero context switching required from the user
- Go fix failing CI tests without being told how

## Repository Map

- `speleodb/`: Django backend code (APIs, models, permissions, tests).
- `frontend_private/`: authenticated/private UI assets and templates.
- `frontend_public/`: public UI assets and templates.
- `frontend_common/`: Vite registry, bootstrap, route controllers, and extracted
  template-owned styles.
- `frontend_private/static/private/js/map_viewer/`: core map viewer modules.
- `frontend_public/static/js/gis_view_main.js`: public viewer entrypoint.
- `tailwind_css/`: Tailwind source styles and Tailwind configs.
- `docs/`: agent-focused design and implementation docs.
- `tasks/lessons/`: agent-focused lesson docs - errors not to reproduce.
- `tasks/todos/`: agent-focused todo docs - working documents for the tasks
  being performed

## JavaScript Workspace Contract

The repository now uses a single Node workspace at the repo root.

- Canonical Node manifests are:
  - `package.json`
  - `package-lock.json`
- Do not re-introduce nested `package.json` files for frontend tooling.
- Vite 8 is the only first-party asset compiler. `frontend_common/entries.json`
  is the logical-entry registry consumed by `vite.config.mjs` and the Django
  manifest tags. Production emits hashed ESM, CSS, shared chunks, and
  `.vite/manifest.json` under `speleodb/common/static/speleodb/vite/`. Generated
  output is ignored.
- The only Tailwind entrypoint is `tailwind_css/style.css`. Vite compiles it as
  logical entry `style-app`; it imports the private entrypoint as the immutable
  configuration/component reference, then adds the public source set and
  namespaced `site-*` components. Do not build or ship the private reference
  independently.
- Tailwind source ownership is CSS-first. The imported private reference keeps
  `@import 'tailwindcss' source(none)` and both files declare explicit,
  stylesheet-relative `@source` directives. Do not add JavaScript Tailwind
  configs, `@config`, automatic detection, or CLI `-c` flags.
- Shared product tokens, browser defaults, and compiler-facing utilities live in
  `tailwind_css/shared/design-system.css`. Use durable semantic names such as
  `srgb-*`, `flow-*`, and `row-divide-*`; production CSS must not expose a
  migration-version prefix. Build-specific dark, hover, group-hover, and sidebar
  variants stay in the owning CSS entrypoint; feature selectors and project
  variables stay in their owning application stylesheet. Do not introduce
  application/runtime coupling to Tailwind's private `--tw-*` variables.
- Every SpeleoDB-owned document declares `color-scheme: dark` and includes the
  Dark Reader lock before stylesheet loading. Keep the private root's `.dark`
  class, but do not add it to public roots: the unified bundle contains the
  private class-controlled variants, which `.dark` would activate publicly.
- SpeleoDB-authored CSS/JS loads through `{% vite_styles %}`,
  `{% vite_preload %}`, and `{% vite_script %}`. Templates declare route
  controllers with inert JSON. Do not add executable inline application scripts,
  application event attributes, compatibility globals, or direct first-party
  `{% static %}` references. CDN/vendored libraries and Django's generated
  `url_reverse.js` remain external globals in their established order.
- `npm run dev` is a Vite disk-build watcher; Django remains the only server.
  There is no Vite dev server, proxy, HMR client, or HTML transformation.
  Tailwind's in-process candidate set can retain a removed template class, so
  stop the watcher and run `npm run build` before final browser evidence.
  Confirm the manifest hash actually served by Django.

### Root JS commands

- `npm run lint:js`
- `npm run test:js`
- `npm run build`
- `npm run build:assets`
- `npm run dev`
- `npm run test:assets-watch`

### Related system hooks

- Dev container/webserver bootstrap: `compose/start` (root npm commands).
- Railpack image build: `railpack.json` (Node 24, `npm ci && npm run build`).
- Railway predeploy: `railway.toml` (migrations and `collectstatic` only).
- CI jobs: `.github/workflows/ci.yml` (root npm install + test/lint paths).
- Pre-commit hooks: `.pre-commit-config.yaml` (root npm scripts).

## Map Viewer Design Guardrails

- Keep private/public map viewers behaviorally aligned where intended.
- The code between private & public map viewer should be as much as possible
  re-used, no re-implementation.
- **Colors are fully model-driven.** `Colors.getProjectColor()` and
  `Colors.getGPSTrackColor()` read the stored color from Config
  (`getProjectById` / `getGPSTrackById`). There is **no palette array in JS**.
  If Config hasn't loaded the entity yet, functions return `FALLBACK_COLOR`
  (`#94a3b8`) **without caching** so the next call retries.
- The 20-color palette lives in a single canonical location: `ColorPalette` in
  `speleodb/common/enums.py`. It is exposed to templates via the
  `{% get_project_color_palette %}` tag.
- **Two-level project visibility:** The map viewer project panel uses country
  grouping with a two-level visibility model. A project is visible on the map
  only when both its country gate AND individual toggle are ON.
  `State.effectiveProjectVisibility` tracks the actual on-map state;
  `getVisibleProjectIds()` reads from it, affecting stations, leads, cylinders,
  and depth domains.

Most map viewer behavior is implemented in shared private modules and loaded by
the `private-map` and `public-gis` Vite route controllers. Their lazy module
roots remain:

- private: `frontend_private/static/private/js/map_viewer/main.js`
- public: `frontend_public/static/js/gis_view_main.js`

When touching shared behavior, explicitly verify both entrypoints are still
valid.

## Testing Requirements

For frontend (public or private) changes, validate tests:

- `npm run test:js`

Backend/API changes should also run relevant `pytest` targets:

- `pytest`

New tests should respects coding existing structures

## Linter

Both frontend and backend include linting:

- Javascript: `npm run lint:js`
- Python: `ruff` & `mypy`

All python code must include type checking for every variable or function.

## Documentation Expectations for Agents

When changing feature behavior or architecture, update docs under `docs/` for
the impacted topic:

- feature intent
- engineering scope and ownership boundaries
- testing and verification strategy
- performance implications

Do not only document "what changed"; include "why this architecture exists".

## Performance and Regression Checklist

Before finishing map viewer work, check:

1. No duplicated permission matrix logic was added.
2. Depth mode toggles still avoid per-feature rescans.
3. Public and private map viewers still initialize shared modules correctly.
4. Lint and tests pass from root.
5. The clean Vite build emits a valid manifest and all registered entries.
6. No unescaped user/API data in `innerHTML`, `.html()`, or
   `insertAdjacentHTML`.

## Practical Do/Do-Not

### Do:

- Prefer shared utilities/modules over code duplication.
- Keep behavior parity for public/private map flows when intended.
- Add focused tests when changing anything of significance.
- Be performance conscious.
- Systematically document all features & architectural decisions.
- Escape all user/API data before inserting into HTML sinks (`Utils.safeHtml`,
  `Utils.escapeHtml`, or `textContent`).

### Do not:

- Duplicate code or logic
- Introduce "quick patches" that hinder long term maintainability.
- Add expensive computations.
- Reintroduce nested Node toolchains.
- Bypass centralized permission APIs.
- Use `Utils.raw()` on strings that contain unescaped user data.
- Put user-supplied strings into `innerHTML` / `.html()` without escaping.

### Coding rules

See `docs/coding-rules.md` for JavaScript constant centralization, XSS escaping
requirements, Python import ordering, and Django ORM rules. These are **hard
rules** — violations must be fixed before merging.
