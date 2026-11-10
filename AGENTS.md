# AGENTS.md

Guidance for AI/code agents working in the SpeleoDB repository.

This file is intentionally opinionated and feature-focused so agents can make
correct changes without re-discovering architecture every session.

Read the current root `AGENTS.md` at the start of every session and follow its
instructions. Do not rely on memory from previous sessions; conventions and
workflow requirements may have changed.

## Git commits run on the host only

When the user asks to commit, you are ONLY allowed to execute
`git commit -m '...'`, using the existing staging area. Do not inspect status or
diffs, run tests or checks, modify files, stage or unstage anything, or perform
any other operation. An explicit additional instruction from the user authorizes
only that additional action.

**NEVER execute `git commit` inside Docker or a devcontainer.** Run every
authorized commit directly on the host from the owning repository checkout. This
includes commits invoked indirectly by scripts, tools, skills, or subagents; do
not use `docker exec`, `docker compose exec`, or any other container execution
path to create a commit.

The requirement to run tests and application checks inside the running
devcontainer does not apply to Git commits. Commit authorization is still
required; this rule only specifies where an authorized commit must run.

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
- **Tests protect behavior**: Prioritize consequential failures and likely
  regressions. Test count and assertions about obvious implementation details
  are not quality goals.

## Mandatory owner directives

These constraints apply to implementation, refactoring, tests, reviews and
subagents. A plan, skill or existing pattern does not authorize ignoring them.
Apply corrections throughout the affected callers, fixtures and documentation;
do not fix one occurrence and leave the same rejected design elsewhere.

Do not install packages, browser binaries or system libraries without an
explicit user request to install them. Test authorization does not authorize
environment installation. Report missing prerequisites instead.

### Keep the design proportional to the actual application

- This is a low-traffic application with one administrator. Do not build
  coordination infrastructure for hypothetical concurrent administrators.
- Do not introduce project-operation middleware, request-wide ownership,
  advisory/filesystem checkout locks, generation counters, dispatch leases,
  checkpoint/resume engines or automatic recovery without an explicit new
  requirement. Preserve unrelated, established export and scheduler behavior.
- Project history, checkout, purge and conversion behavior belongs on `Project`.
  Do not extract it into separate files or services. Prefer a readable model
  method over forwarding wrappers and helper layers.
- Do not add a model, database field, migration, queue, service or recurring
  schedule merely to support an implementation abstraction. Tie persistent state
  to an actual requested product requirement.
- Use ordinary exceptions when callers do not need a distinct exception type.
  Report failures with the original traceback (`logger.exception` inside the
  handler) and preserve exception chaining. Do not build regex-based exception
  parsers, diagnostic taxonomies or retryability classifiers. Do not accumulate
  coded per-commit diagnostics, `explain()` helpers or arbitrary diagnostic
  limits. Keep required counts and log the original failure traceback.
- Handle expected omissions, such as missing sources, empty surveys and missing
  anchors, explicitly. Unexpected conversion failures must fail the task even
  when other revisions succeeded; never swallow them and report success.
- Do not introduce convenience aliases, renamed imports or rebound APIs just to
  shorten or hide the original name. Prefer the original name or a
  module-qualified reference. Do not retain superseded entrypoints as aliases.

### Resource ownership must be concrete

- Inspect the actual resource type and ownership before changing `.close()`.
  Variable names alone do not identify a repository, HTTP response or file. UI
  dialog/editor/menu `close()` calls are application behavior, not resource
  disposal.
- Prefer a library's existing native `with` protocol when the resource belongs
  to one lexical scope. Verify that the installed class actually supports it; do
  not assume that a file-like response is a context manager.
- Never add manual `.close()` calls or cleanup-only `try/finally` blocks for
  resources owned within one lexical scope, including tests. Use the native
  `with` protocol when supported; otherwise use `contextlib.closing(resource)`
  when closure is required. Django `FileResponse`/`StreamingHttpResponse`
  objects consumed entirely in a test use `contextlib.closing(response)`; their
  streaming type does not justify a manual `finally: response.close()` block.
- Retain explicit closure only when ownership actually spans methods or a shared
  fixture, or a required shutdown sequence cannot be expressed by a local
  context. Explain that concrete lifetime requirement beside the closure. Remove
  redundant cleanup instead of wrapping it in another abstraction.
- Do not add GitRepo `.close()` calls, `closing(repo)` wrappers, active-handle
  caches or custom checkout lifetime protocols as an unsolicited cleanup
  feature. A repository directory is not an open file.
- Do not use `enterContext`, `ExitStack`, manual `__enter__`/`__exit__`, or
  equivalent hidden context registration for ordinary resources. Prefer local
  `with` blocks and simple fixtures with clear ownership. Do not rename a
  rejected wrapper and keep the same design.
- Do not create custom context/disposal protocols to eliminate the spelling
  `.close()`. Keep necessary ownership, scope and shutdown ordering visible.

### Preserve API scope and real execution status

- Internal refactors must not change unrelated API permissions, status codes,
  error shapes or OpenAPI response schemas. Do not add HTTP 409 responses for
  the rejected project coordination design or incidentally alter existing 403
  behavior. Review generated schema changes; avoid global error-schema churn.
- Keep task publishers, worker signatures, CLI callers and tests aligned. Do not
  conceal mismatches with unused compatibility arguments or wrappers. Preserve
  original exceptions through Celery serialization and task results. Use the
  shared `TaskResultStatus` enum for Celery/TaskResult state values; do not
  scatter status string literals through code, tests or templates. dss
- Reuse existing admin/forms/assets and background execution infrastructure.
  Failed project operations are rerun explicitly; do not restore automatic
  generation retry/recovery or change the separate export-job lifecycle. Keep
  model URLs, export permissions and the worker's lightweight admin setup. Use
  `docs/admin-operations.md` for the current operation semantics.

### Honor stop requests and migration ordering

- A stop request overrides the verification workflow below. Stop the owned
  running commands and delegated work in scope, including their child processes.
  Do not merely stop launching new commands or leave checks running in the
  background. Do not interrupt unrelated developer processes.
- Do not restart stopped tests, hooks, builds or checks until the user requests
  them again. Authorization to edit or review files is not authorization to
  resume execution. Report unverified changes honestly.
- When asked to run `prek`, fix its actual failures and rerun the requested
  hooks. Include new untracked files without staging them. Do not weaken checks,
  add blanket ignores, or claim that a passed hook means unrun tests passed.
- When asked to revert an applied migration, inspect the reversal plan and
  reverse the intended database migration **before** deleting its file or
  dependent code. Verify the database state and migration record. Deleting a
  Python migration file alone does not revert a database change.
- Implementation, local checks, Git publication and production execution are
  separate actions. Preserve staged/unstaged work; do not commit or deploy
  without the explicit authorization required by the root instructions.

## Legacy and backward compatibility

**Do not assume legacy support or backward compatibility is required.** Add or
retain legacy entrypoints, compatibility wrappers, aliases, or fallback paths
only when the user explicitly requests compatibility. Hypothetical external
consumers are not a reason to preserve a superseded interface.

When replacing an interface, migrate its in-scope callers, tests, and
documentation to the supported interface and remove the superseded code.

## Temporary agent files

Keep agent plans, task lists, TODO tracking, progress notes, review notes, and
scratch lessons outside the repository tree, including all submodules. Use a
unique task directory under `/tmp/` (for example, create one with
`mktemp -d /tmp/sdb-website-task.XXXXXX`) or another OS temporary directory
whose resolved path is outside every checkout.

Never create or update these working files inside the checkout, even in ignored
directories such as `tasks/`, `todos/`, or `plans/`. Never stage or commit them.
Existing tracked task and lesson files are historical references; do not append
new work to them. Keep durable product and architecture documentation in
`docs/`, without embedding task checklists or linking to temporary files. Before
an authorized commit, inspect the staged filenames and exclude all agent working
files.

## Task Management

1. **Plan First**: Write `plan.md` in the external temporary task directory with
   checkable items
2. **Verify Plan**: State the intended approach before implementation; do not
   request confirmation for work the user has already authorized
3. **Track Progress**: Mark items complete as you go
4. **Explain Changes**: High-level summary at each step
5. **Document Results**: Add a review section to that temporary `plan.md`
6. **Capture Lessons**: Update `lessons.md` in the external temporary task
   directory after corrections
7. **Documentation is Key**: Document each feature and design inside `docs/`.
   What is the feature being implemented, the design space and intents and a
   rapid summary of the approach taken with key APIs & concepts.

## Workflow Orchestration

### 1. Plan by Default

- Use a short plan for genuinely multistep work or architectural decisions;
  routine fixes do not need a separate planning or approval ceremony
- If something goes sideways, STOP and re-plan immediately - don't keep pushing
- Include the authorized verification steps in the plan
- Keep plans proportional to the task; do not turn a small fix into a design
  project or introduce machinery merely to satisfy a plan

### 2. Subagent Strategy

- Use subagents for independent, clearly scoped work when delegation helps
- Give each subagent one task and explicit file ownership
- Propagate user constraints, stop requests and verification limits to every
  subagent; review the combined result for missing imports and stale callers
- Do not multiply parallel rewrites or abstractions just because agents are
  available

### 3. Self-Improvement Loop

- After ANY correction from the user: record the pattern in `lessons.md` in the
  external temporary task directory
- Write rules for yourself that prevent the same mistake
- Ruthlessly iterate on these lessons until mistake rate drops
- Review lessons at session start for relevant project

### 4. Verification Before Done

- Never mark a task complete without proving it works
- Diff behavior between main and your changes when relevant
- Ask yourself: "Would a staff engineer approve this?"
- Run appropriate tests and checks when authorized; obey stop requests and
  explicitly identify anything left unverified

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
- `ts-types/`: shared domain/controller contracts and browser, worker, tooling
  and test declarations.
- `frontend_common/`: Vite registry, bootstrap, route controllers, and extracted
  template-owned styles.
- `frontend_private/static/private/ts/map_viewer/`: core map viewer modules.
- `frontend_public/static/ts/gis_view_main.ts`: public viewer entrypoint.
- `tailwind_css/`: Tailwind source styles and Tailwind configs.
- `docs/`: agent-focused design and implementation docs.
- `tasks/lessons/` and `tasks/todos/`: historical references only; all new agent
  working files belong in the external temporary task directory.

## Frontend TypeScript Workspace Contract

The web application uses one Bun-managed workspace at its root. Authored
browser, test and tooling sources are TypeScript, checked in three no-emit
projects with `allowJs: false`. Exact vendor files and generated JavaScript are
excluded by the ownership audit; new application code cannot hide in vendors.
Both production build commands run type checks and source/template audits before
emission, and `build` checks before cleaning previous output. Alpine behavior
lives in typed function-valued bindings with inert template identifiers.

- Canonical JavaScript manifests are:
  - `package.json`
  - `bun.lock` (text JSONC)
- `.bun-version` is the canonical exact Bun version for local containers, CI,
  and Railpack. The root `packageManager` mirrors it as `bun@<version>`, and
  `engines.bun` mirrors the exact version. Use
  `test -s bun.lock && bun install --frozen-lockfile` for reproducible installs;
  the guard rejects a missing or empty lock before resolution.
- Bun is the JavaScript runtime for Vite, Vitest, Playwright, and tool
  subprocesses. Keep `[run] bun = true` in `bunfig.toml` so package scripts and
  their executable children use the declared Bun runtime. Retain Vitest and its
  existing test configuration; `bun test` is a different runner.
- `trustedDependencies` explicitly approves `esbuild` and `fsevents` install
  scripts. Review this list whenever the dependency graph changes.
- Run web installs and checks from `/app` inside the application container. This
  standalone mount prevents Bun from discovering the enclosing monorepo
  workspace and changing its dependency graph or lockfile.
- For monorepo relocking, run `bun run lock` (or `--upgrade`) from this
  checkout. The shared monorepo utility resolves a temporary standalone copy
  with the pinned Bun version and copies back only `bun.lock` after success,
  without installing dependencies. See `docs/dependency-updates.md` for its
  scope.
- Do not re-introduce nested `package.json` files for frontend tooling.
- Vite 8 is the only first-party asset compiler. `frontend_common/entries.json`
  is the logical-entry registry consumed by `vite.config.ts` and the Django
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
- Local `compose/start` completes `bun run build:assets` before serving
  templates, then supervises Django and `bun run dev` together for automatic
  asset rebuilds on save. Do not start a second watcher. Use
  `docker exec -w /app speleodb-monorepo-django bun run dev` only when Django
  was started independently without the local launcher. Type checks and
  source/template audits run once before the Vite build watcher starts;
  subsequent rebuilds compile only. Wait for a successful build, then refresh
  the browser manually. Retain old hashed assets while watching so open pages
  can finish deferred imports. Restart the watcher after registry or Vite
  configuration edits. `build` and `start` remain finite production builds. Stop
  the local webserver and its watcher before production builds or final browser
  checks, then run `docker exec -w /app speleodb-monorepo-django bun run build`
  and confirm the manifest hash actually served by Django. Django remains the
  only server; do not add reload clients, generation polling, a Vite development
  server, proxy, HMR, or HTML transformation.

### Root frontend commands

- `bun run lock [--upgrade]` (monorepo-only standalone lockfile resolution)
- `bun run typecheck` (all three TypeScript environments)
- `bun run lint:frontend`
- `bun run test:frontend`
- `bun run audit:javascript`
- `bun run audit:templates`
- `bun run build`
- `bun run build:assets`
- `bun run dev`
- `bun run start`

### Related system hooks

- Dev container/webserver bootstrap: `compose/start` installs dependencies,
  completes an initial checked asset build, and starts Django with the asset
  watcher. Both process groups and their children stop together. Local Compose
  mounts the checkout's launcher at `/start`; restart the container after
  launcher edits, and recreate it when the Compose mount changes. Startup and
  watched builds retain older hashed assets. Run finite production builds with
  the local webserver and its watcher stopped.
- Railpack image build: `railpack.json` (Bun from `.bun-version` via Mise,
  guarded frozen install followed by `bun run build`).
- Railway service configuration: `.railway/railway.ts` is the sole authority;
  predeploy runs migrations, `install_background_schedules`, and
  `collectstatic`. Do not reintroduce legacy `railway.toml` or `railway.json`
  files.
- CI jobs: `.github/workflows/ci.yml` (root Bun install + test/lint paths).
- Pre-commit hooks: `.pre-commit-config.yaml` (root Bun scripts).
- Dependabot: `.github/dependabot.yml` uses the `bun` ecosystem for the root
  manifest and lockfile; preserve the existing scheduling and grouping policy.

## Railway configuration apply and session handoff

`.railway/railway.ts` is the source of truth for Railway service settings. Keep
all managed service definitions in this single file, including Gogs and the Git
backup job whose application source belongs to a separate repository. Do not add
another `railway.ts` or separate IaC SDK to that repository. Railway does
**not** read this file during ordinary application deployments. Committing,
pushing, building, restarting, or redeploying application code does not apply
changes to this configuration.

All eight active production services, including Redis and both backup cron jobs,
belong in this file. Use `docs/railway-production.md` for the ownership
inventory and Redis replacement procedure. A no-change adoption must compare
against raw live configuration, not just the CLI's imported graph. Redis is a
plain image service; keep it free of template-origin metadata so its builder and
volume mount import correctly. The final plan must have no effective drift.

PostgreSQL PITR requires the image's own startup; never add a custom start
command to tune its memory. Preserve its `WAL_ARCHIVE_*` references and archive
bucket in the same file. Memory tuning persists in
`PGDATA/postgresql.auto.conf`; verify or restore it when replacing the volume.
Follow `docs/railway-production.md` and verify a completed base backup plus
healthy WAL archiving before reporting PITR ready.

- Run `railway config plan` against the intended project and environment when
  changing this file or a helper that affects its evaluated configuration, or
  when repairing live settings that have drifted from it. Review the exact
  service/settings changes and preserve the existing named partial's ownership.
- Changes to configured startup/build/pre-deploy commands, service sources,
  variables/references, replicas, resource limits, or other managed settings
  require `railway config apply` to become live. Application code or startup
  script content changes with unchanged configured settings require the normal
  application deployment, not an additional configuration apply. A plan with no
  effective changes does not require an apply solely because the file was
  edited.
- Apply within the user's authorized scope. Keep unrelated services, settings,
  variables, and staged Railway changes intact. Do not substitute independently
  hardcoded dashboard/MCP values for the source configuration. If a targeted
  repair uses MCP, derive values from the evaluated file and verify their scope.
- After applying configuration, read back the affected settings and verify the
  resulting deployments and runtime logs. A cached redeploy may retain an old
  image's launch command; use a fresh source build when needed. A deployment's
  initial `SUCCESS` status alone is insufficient if its runtime is crashing.
- After an authorized Redis replacement, restore consumer references from this
  file and redeploy web, worker, and Beat. Verify their deployed connection URLs
  and Redis connectivity; preserving the private hostname alone does not refresh
  running processes or repair references rewritten during service deletion.

**Mandatory final-response notice:** If required configuration changes remain
unapplied, or their live application has not been verified, end the session's
final response with a separate, prominent paragraph beginning: **ACTION REQUIRED
— RAILWAY CONFIGURATION NOT CONFIRMED LIVE.** Name the target
project/environment, affected services/settings, and whether the apply is
pending, failed, or awaiting verification. Provide the exact remaining
plan/apply/deploy or verification steps, including the working directory and
target environment; explain any missing authorization or blocker. Explicitly
state that a Git push alone will not finish the configuration change. Do not
bury this notice in a test list, progress update, or linked document, or
describe the rollout as complete. If application and runtime verification are
complete, report that result instead of presenting an unnecessary pending-action
warning.

## Dependency Update Workflow

- Treat the open Dependabot PRs targeting `dev` as the authoritative branch set.
  Fetch and merge every open `dependabot/*` head before consolidating the
  manifests and lockfiles.
- Use `bun outdated` to inspect available releases and `bun run update` for
  updates within declared ranges. For an authorized major-version refresh, use
  `bun update --latest '*' --lockfile-only --ignore-scripts` in an isolated
  external directory; review peer compatibility explicitly. Resolve `bun.lock`
  independently of the installed tree, then verify workspace/manifest agreement,
  portable package identities, dependency edges, and registry integrity. Bundled
  packages inherit their parent archive's integrity; do not fabricate separate
  checksums. See `docs/dependency-updates.md` for the lockfile workflow.
- Apply compatible Python direct updates, run `uv lock --upgrade`, and use
  `uv tree --outdated --depth 1` to prove that every remaining old direct
  dependency has an explicit incompatibility.
- Run Cargo or other update and lockfile workflows only when their manifests are
  present. Do not introduce a new package manager to satisfy this checklist.
- Run `prek update`, review every hook revision change, and keep duplicated tool
  hooks such as ruff and djLint aligned with their project pins.
- Validate a clean install, production asset build, all JavaScript and Python
  tests, and `prek run -a` before creating the single dependency-update commit.

### Current Dependency Blockers

- Can't update Django to 6.1.x until `django-celery-beat` supports Django 6.1;
  version 2.9.0 requires Django `<6.1`.
- Can't update orjson to 3.12.x until `compass-lib` relaxes its `orjson<3.12`
  constraint and supported non-x86 architectures have a binary-wheel path;
  version 0.0.7 requires `orjson>=3.11.8,<3.12`, while orjson 3.12 removes
  ppc64le and s390x wheels and the standalone image is intentionally Rust-free.
- Can't update pyproj to 3.8.x until `compass-lib` relaxes its `pyproj<3.8`
  constraint; version 0.0.7 requires `pyproj>=3.7.2,<3.8`.

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

- private: `frontend_private/static/private/ts/map_viewer/main.ts`
- public: `frontend_public/static/ts/gis_view_main.ts`

When touching shared behavior, explicitly verify both entrypoints are still
valid.

## Testing Requirements

### Test-driven development

For bug fixes and behavior changes, follow test-driven development:

1. Before changing production behavior, add a focused behavioral test that
   reproduces the defect or expresses the required behavior. Run it and confirm
   that it fails for the intended reason. Environment and fixture setup failures
   do not establish reproduction.
2. Implement the smallest root-cause correction. Keep the regression's expected
   behavior intact.
3. Rerun the regression, relevant boundary and state-preservation cases, and
   required broader checks. Refactor only while this coverage remains passing.

Tests must exercise consequential application behavior using the repository's
established test boundaries. Record the observed failure and passing
verification outside the checkout. Preserve the rules for real clocks, minimal
mocking, and container execution. Missing prerequisites and stop requests must
be reported; unrun checks cannot establish completion. Do not claim broader
guarantees than the verified scenarios support.

The owner's stop/resume directives take precedence over every test/check
requirement in this file. When tests are authorized, run **every test inside the
already-running application container**. Do not run tests on the host or start
another stack for verification. The current local container is
`speleodb-monorepo-django`, with the repository mounted at `/app`.

For frontend (public or private) changes, validate tests:

- `docker exec -w /app speleodb-monorepo-django bun run test:frontend`

Backend/API changes should also run relevant `pytest` targets:

- Full suite: `docker exec -w /app speleodb-monorepo-django make test-py`
- Focused suite: `docker exec -w /app speleodb-monorepo-django pytest <targets>`

### Targeted backend coverage

Apply pytest markers directly to test functions or classes with decorators such
as `@pytest.mark.django_db`. Do not introduce `pytestmark` assignments or
aliases for marker expressions, including lists of markers. Mark database use
only where needed and preserve required options such as `transaction=True`.

Every new or retained test must protect an identifiable application failure. Do
not create tests that merely restate factory defaults, compare factory
timestamps with `before`/`after` calls to `timezone.now()`, verify framework
mechanics, or echo values just assigned by a mock. Do not replace a deleted
low-value test with another test of the same implementation detail. Keep
regression coverage for permissions, real persistence and storage, Git history,
failed replacement preservation, task outcomes and exception serialization.

- The complete backend suite uses PostgreSQL, as explicitly authorized by the
  user, because retained integration contracts use advisory locks, immediate
  constraints, and independent worker connections. Honor the test environment's
  `DATABASE_URL` and explicit `TEST_DATABASE_URL` override; never silently
  inherit the development connection or change the selected database engine.
  Pytest owns an isolated `test_` database created from `template0`; do not run
  tests against the development database. This does not authorize new
  race-condition tests.
- `make test-py` is the complete default backend suite; `make test` also runs
  frontend tests. Tests against `OpenAPI.yaml` are limited to the
  `export_api_schema --check` SHA-256 comparison with a fresh temporary export.
  Endpoint tests assert application behavior independently of the schema. Every
  backend test runs by default, including existing worker and storage
  integration. Missing services, dependencies, privileges, or fixtures must fail
  clearly; never add environment opt-ins, `skipif`, `importorskip`, or runtime
  skips. Explicit `--light`/`--offline`, `-m`, or `--ignore` exclusions are
  reported as deselection and do not replace complete validation. Invalid
  parameter combinations belong outside the collected matrix. Browser tests
  remain a separately invoked UI/UX layer.
- Backend behavior belongs in pytest, frontend logic in Vitest, and browser
  tests exclusively in UI/UX verification. Do not move backend assertions into
  browser tests to reduce pytest time.
- Choose the narrowest useful layer. Keep real database checks for constraints,
  query behavior, transactions, and permissions, plus a small set of real
  storage/repository/worker integrations. Use local bare repositories for
  Git-only behavior; pure parsing and validation should not request a database.
- Keep authorization matrices where grant source and access level change
  behavior. Test unrelated validation, serialization, and file handling with a
  representative authorized user instead of multiplying them by that matrix.
- Before deleting or consolidating tests, inspect production behavior and name
  the concrete failure covered by a retained test. Similar names alone do not
  prove redundancy. Remove framework, factory-echo, source-formatting, and
  private-implementation assertions that provide no useful application contract.
- Build the smallest object graph that exposes the regression. Use deterministic
  boundary cases; do not repeat randomized inputs or large fixtures without a
  failure they distinguish. A query-count regression must assert that the
  requested records are actually visible and returned.
- Review actual transaction boundaries, existing lock ownership, permissions,
  duplicate delivery and idempotency. This does not authorize speculative
  coordination infrastructure for single-admin project operations. Do not add
  race-condition tests unless explicitly requested: no threaded writers,
  competing schedulers, forced interleavings or lock-contention harnesses as
  routine regression coverage. Use small sequential tests for observable state
  transitions and existing safeguards. Removing a test does not by itself
  authorize removing a production safeguard.
- Test fixtures, generated payloads, and uploads/downloads must stay at or below
  100,000 bytes. Keep compressed fixtures small after extraction too. Preserve
  behavioral tests by using small representative inputs and lowering test-local
  size/chunk thresholds; never run capacity or load tests as backend pytest.
  Keep the existing GIS Station photo, video, and PDF examples unchanged. If a
  format cannot be safely reduced (for example TML), ask for a smaller valid
  artifact instead of keeping an oversized fixture or silently dropping
  coverage.
- Let pytest-django/Django own database rollback and transactional flushes.
  Declare database use explicitly on tests or fixtures that need it. Never add
  autouse database access or whole-database deletion to support pure tests, and
  do not widen mutable fixture scope to trade away isolation.
- Compare timing with the same command, workers, database creation/reuse, and
  service conditions. Report setup/call/teardown separately, attribute shared
  fixture costs separately, and distinguish summed durations from suite wall
  time. Investigate slow tests; do not delete important coverage just to meet a
  timing threshold or hide costs behind skips, retries, or more workers.

### Browser tests cover complex UI/UX workflows only

This boundary applies to **all browser engines**, including Chromium and WebKit,
and to new tests as well as changes to existing tests:

- Browser tests protect complex workflows requiring a real browser: native
  gesture handoff, drawing/history/discard, interacting visibility scopes,
  asynchronous loading/cancellation/recovery, focus/fullscreen interaction, and
  native editing with retained state after errors. Keep the real compiled
  templates, controllers, vendor libraries and renderer.
- Do not add browser checks for icon artwork, asset availability, colors, fonts,
  attribution, camera configuration, static read-only markup, basic validation,
  or simple menu/dialog open/close and button feedback. Do not add pixel
  sampling, screenshot comparisons or GPU-frame capture to cover those
  properties. Existing Vitest/pytest contracts own their application behavior;
  screenshots are failure diagnostics only.
- Backend validation, permissions enforcement, persistence, serialization, API
  contracts and data processing belong in **pytest**. Frontend application
  logic, request payloads/counts, caching, scheduling, workers and renderer
  configuration belong in the existing **Vitest** suite. Both are covered by
  **`make test`**.
- Prioritize consequential, likely-to-break interactions and known regressions.
  Use representative cases for shared components; avoid Cartesian input matrices
  and repeated basic open/close/reset checks already covered below browsers.
  Exhaustive browser variants require a distinct failure mode, not merely
  another value or template using the same interaction.
- Before adding a browser test, identify its browser-specific regression and
  inspect lower-layer coverage. Before removing an application-logic assertion,
  verify its pytest/Vitest replacement or add the missing test. Do not retain
  duplicate logic coverage in browsers to avoid this verification.
- Use small deterministic fixtures and real HTTP fixtures where possible.
  Control responses/loading gates only when necessary to produce a specific
  external failure or ordering case. Keep real application functions and
  renderer methods. Large processing inputs, worker/internal counters, repeated
  timing samples, and source-configuration assertions belong outside default UI
  CI.
- Minimal database/authentication fixtures may render real application pages.
  Seed editing independently. Do not use browser write/readback/reload chains to
  prove backend persistence; intercept mutations and assert visible completion.
  Reload/navigation remains valid when it is itself the UI behavior under test.
- Investigate executions over five seconds; five seconds is not a ceiling. Keep
  justified rendering and interaction costs, and do not weaken coverage to meet
  a number. Reduce unnecessary work before adding compute. Retain one worker,
  zero retries and both engines unless the user explicitly authorizes a change.
- Adding a scale/performance benchmark requires explicit user authorization.
  Keep an authorized opt-in benchmark separate from default UI/UX CI; do not
  silently reintroduce stress fixtures. Unit yielding tests do not establish
  real-browser scale/latency guarantees.

Keep `tests/browser/README.md` aligned with this contract. Record timing reports
outside the repository, not in these durable instructions.

### Controlled test boundaries

**Never fabricate retry failures or retry behavior, anywhere in Python or
TypeScript tests or fixtures.** Retry only after an actual call fails. Do not
raise synthetic exceptions, return canned failure statuses, script failures
followed by success, mock retry results, or replace clocks/sleeps to manufacture
a retry scenario. Exercise the real operation against a real failure condition
when retry coverage is necessary. Remove tests that only prove invented retry
behavior; do not preserve them by replacing fake timers with long real waits.

Do not deliberately hold locks, pause services or manufacture outages solely to
force a backoff sequence or exhaust its waiting budget. Using real sockets,
database locks or real sleeps does not make that artificial scenario acceptable.
Do not replace removed scenarios with shorter waits, patched delays or new
backoff configuration. Preserve production recovery behavior.

**No mocking, patching, stubbing or spying unless absolutely necessary.** This
applies throughout backend, frontend, browser tests and shared fixtures.

- Use real constructors, application functions, state/configuration objects,
  supported configuration, small real inputs, local repositories and actual HTTP
  fixtures. Reuse existing real composition coverage instead of creating suites
  that replace entire application modules and assert mock call counts.
- A necessary substitute must be limited to the precise external/native
  boundary: for example, a specific upstream failure that cannot be induced
  reliably, or a browser/GPU capability unavailable in the test environment.
  Explain the concrete necessity beside it. Convenience, speed and avoiding
  fixture setup are not sufficient reasons.
- Test the behavior claimed by the test with the real implementation. Assert
  observable results, not values manufactured by the substitute. Keep real
  native input, decoding and available renderer/library behavior.
- Do not mute console output, fix randomness, override document state or mock
  working vendor libraries merely to make tests convenient. Observe actual calls
  without replacing behavior only when that observation is necessary.
- Inspect the substitutions behind `restoreAllMocks`, `restore_all`, patch
  teardown and similar cleanup. Remove unnecessary substitutions and then
  redundant cleanup. Do not replace bulk restoration with renamed/manual
  restoration to hide the same mocking. Restore any genuinely required
  substitution so it cannot leak into other tests.

**Use real time and real waiting everywhere.** Do not patch clocks or sleeping,
freeze `timezone.now()`/`Date.now()`, replace `monotonic`/`performance.now`,
install fake timers, manually advance timers, flush captured animation-frame
callbacks, or replace sleeps with no-ops or delay-recording functions. This
includes shared GitLab provisioning and retry fixtures. Let actual retries,
timeouts, polling, feedback and animation frames run. Existing supported
arguments may use small positive test delays; do not add production timing APIs
or patch constants solely to accelerate tests. Use real timestamps and persisted
past/future deadlines for state transitions; pass explicit dates to pure
calendar helpers instead of replacing the clock.

Keep real rollback, storage readback, repository restoration, and worker
lifecycle tests where a substitute would hide the failure. For retry policy,
exercise real bounded attempts and waits, and assert observable outcomes.
Concurrency concerns require implementation review, not new race-condition tests
without the user's explicit request. Keep substitutes function-scoped and
automatically restored, including environment changes. Do not fabricate success
responses in a test advertised as an integration test.

### Django GitLab repository contract

- Read `docs/ci-gitlab-testing.md` before modifying Git-related fixtures. A test
  invocation may create **at most nine GitLab projects cumulatively**, including
  repositories deleted during the run. Never increase the budget to accommodate
  a new test.
- Ordinary tests reuse the four run-scoped canonical identities: **ADMIN
  Project**, **Read and Write Project**, **Read only Project**, and **Webviewer
  Project**. A leads ADMIN; B leads the other three and A receives the named
  access level. Use `canonical_project()`, `canonical_user()`, and
  `project_matrix()` from `speleodb.testing.gitlab_pool`.
- Database rows are materialized within each test's transaction. Additional
  `ProjectFactory` rows are permitted when distinct identities/cardinality are
  required; they are database-only and must not provision GitLab. Pass projects
  explicitly into child factories when building without database access.
- Permission grants remain explicit for no-access, inactive, team-only, and
  permission-count cases. `canonical_project()` supplies metadata, not hidden
  access. Do not give a team test a direct grant that could mask a regression.
- Git consumers explicitly call `get_pool().prepare(project)`; the shared
  fixture isolates checkout directories and restores acquired leases. A heavy
  test marker does not provision GitLab. Tests never delete pooled repositories;
  session cleanup owns them. Preserve fresh local checkouts, baseline SHA
  restoration, all-refs history checks, and transaction rollback coverage. Use
  real local bare Git repositories for Git-only behavior.
- Only the fixed lifecycle allocations `manager-new`, `proxy-new`,
  `empty-archive`, `manager-empty`, and `write-check` may create additional
  repositories. Keep absent/empty/create/delete assertions in self-contained
  lifecycles; do not depend on test execution order or recreate a deleted slot.
- The normal full-suite budget is nine successful creations and ten creation
  POSTs: the extra POST is the intentional invalid-namespace HTTP 400. Retries
  remain bound to the same allocated namespace/path and existing retry policy.
  Never bypass the audit, disable its guard, or replace real SDK responses with
  mocks to satisfy the limit.
- The root pytest plugin audits creation before transport and propagates its
  ledger to subprocesses. Preserve inherited audit environment variables.
  Inspect `.artifacts/gitlab/<run-id>/summary.json` and `events.jsonl`; any
  violation or unresolved creation fails the run, even if application code
  caught the exception. Deletion does not refund a creation allocation.
- Keep pytest serial and CI preflight `check_gitlab --read-only`. Do not run
  group-wide cleanup concurrently with an active suite. Report actual audit
  counts and verified cleanup alongside test results.

## Linter

Both frontend and backend include linting:

- Javascript: `bun run lint:frontend`
- Python: `ruff` & `mypy`

All python code must include type checking for every variable or function.

## Documentation Expectations for Agents

When changing feature behavior or architecture, inspect `docs/` and read the
existing documentation for the impacted topic. Update it in the same change. If
no relevant document exists, create one and link it from `docs/README.md`.
Cover:

- feature intent
- engineering scope and ownership boundaries
- testing and verification strategy
- performance implications

Do not only document "what changed"; include "why this architecture exists".
Undocumented behavior or architecture changes are incomplete.

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
- Reintroduce nested JavaScript toolchains.
- Bypass centralized permission APIs.
- Use `Utils.raw()` on strings that contain unescaped user data.
- Put user-supplied strings into `innerHTML` / `.html()` without escaping.

### Coding rules

Before writing or editing Python or JavaScript in each session, read the current
`docs/coding-rules.md`. Do not rely on a remembered or paraphrased version. Its
JavaScript constant centralization, XSS escaping, Python import ordering, and
Django ORM requirements are **hard rules** — violations must be fixed before
merging.

### Preserve existing code comments

Never remove or modify existing code comments unless your code change makes them
factually incorrect. Keep comments above edited code and carry comments inside
refactored blocks with the code. Do not remove comments because they seem
redundant or rephrase them for style.

### Python exception syntax

The project targets Python 3.14 and uses PEP 758 bare commas when catching
multiple exception types. Only add parentheses when binding the exception with
`as`:

```python
except ValueError, TypeError:
    ...

except (ValueError, TypeError) as exc:
    ...
```

### Python imports

**Relative imports are prohibited unless an absolute import is technically
impossible.** Use absolute package paths throughout the repository, including
`config/settings/`. Shorter spelling, convenience, and existing style do not
justify an exception. Document the specific technical necessity beside any
unavoidable relative import.

All imports belong at module scope. Never place imports inside functions,
methods, `setUp`, tests, or other local scopes, even for a symbol used only
once. Ruff enforces this with PLC0415. The only permitted guarded imports are in
module-level `if TYPE_CHECKING:` blocks for type-only dependencies that must not
create runtime circular imports:

```python
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from speleodb.users.models import User
```
