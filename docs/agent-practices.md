# Agent Documentation & Practices

Maintained implementation guidance for agents and contributors. The repository
[agent instructions](../AGENTS.md) and [coding rules](coding-rules.md) define
the shared workflow and constraints. This guide collects feature-specific
extension and review practices; the linked feature guides describe current
behavior.

## Coverage reports

The Python coverage configuration in `pyproject.toml` includes application code
and Django templates and excludes migrations and test modules. Run coverage in
the existing application container with the same isolated database and service
credentials as the normal backend suite:

```bash
docker exec -w /app speleodb-monorepo-django coverage run -m pytest
docker exec -w /app speleodb-monorepo-django coverage html
```

Open the generated `htmlcov/index.html` from the mounted checkout. Coverage
helps locate unexercised behavior; it does not replace regression tests for
meaningful failures. Reports are generated artifacts, not committed evidence.

## Background runtime verification

Feature reference:
[Background job runtime and ownership](background-jobs-operations.md#beat-runtime-and-ownership).

When runtime measurement is authorized, use an isolated migrated test database,
a unique test queue and the canonical Beat launcher for a real periodic task.
Observe at least 15 minutes of scheduling with the Linux process measurements in
the feature guide. Remove only probe-owned resources. Run within the existing
application-container verification boundary; do not start an extra stack or
change developer schedules.

Compare workers under the same architecture, dependencies, settings, prefork
concurrency and workload. Measure parent and execution child separately; use
combined PSS to apportion shared pages instead of summing RSS. Keep startup
preflight and container page cache separate from resident-process measurements.
Verify conversion geometry and relevant datum/UTM metadata as well as memory.
Compass section colors and generated metadata can vary, so whole-document
inequality alone does not establish numerical drift.

A few conversion samples do not establish throughput or cover network export,
email and storage work. Fixture size, production observability and workload
change the footprint. Keep measured results and limitations in external review
notes; verify the actual deployed service before claiming its memory goal is
met. Scale/performance benchmarks require explicit authorization.

## Dashboard metrics

Feature reference: [Dashboard metrics](dashboard.md).

Add summary queries to `UserDashboardStatsView._build_summary()` and connect
visible cards in `pages/dashboard.html` to `populateStatCards()` in
`frontend_common/controllers/dashboard.ts`. Extend the API and frontend suites
for the metric's permission scope, empty state, and rendered value.

## Form extensions

Feature reference: [Form extensions](frontend-forms.md).

When adding a form, first confirm the endpoint's audited schema and generated
operation. Reuse the applicable form primitive, add a typed controller context,
build the callback, and cover its DOM-to-HTTP behavior. Run `bun run typecheck`,
`bun run lint:frontend`, `bun run audit:api`, `bun run test:frontend`, and the
production build. The AST API audit prevents first-party raw transport calls
from returning under aliases or new endpoint strings.

## API exception handling

Feature reference: [Upload error handling](upload-error-handling.md).

Every `except` block in any API view that returns an `ErrorResponse` with
status >= 500 **must** follow this protocol:

1. **`logger.exception(...)`** — preserves the full traceback in console/Railway
   logs.
2. **`sentry_sdk.capture_exception(exc)`** — creates a Sentry event with
   traceback, tags, and request context.
3. **`transaction.set_rollback(True)`** — required **only** when ORM writes
   (`create`, `save`, `get_or_create`, etc.) happen inside the `try` block
   before the error. Tells Django's `ATOMIC_REQUESTS` to roll back the entire
   transaction.

### Savepoint rule for catching `IntegrityError`

Under PostgreSQL + `ATOMIC_REQUESTS`, a caught `IntegrityError` leaves the
transaction in an aborted state unless a savepoint was used.

**`get_or_create()` handles this automatically** — it creates its own savepoint
around the `create()` call. Do not add a redundant wrapper:

```python
# GOOD — get_or_create manages its own savepoint
try:
    obj, created = MyModel.objects.get_or_create(...)
except IntegrityError:
    pass

# BAD — redundant savepoint, unnecessary nesting
try:
    with transaction.atomic():
        obj, created = MyModel.objects.get_or_create(...)
except IntegrityError:
    pass
```

**A raw `create()` does NOT create a savepoint.** If you catch `IntegrityError`
around a plain `create()`, you MUST wrap it:

```python
# GOOD — savepoint protects the outer transaction
try:
    with transaction.atomic():
        MyModel.objects.create(...)
except IntegrityError:
    pass

# BAD — corrupts PostgreSQL transaction under ATOMIC_REQUESTS
try:
    MyModel.objects.create(...)
except IntegrityError:
    pass
```

## Tooling and package-manager changes

Feature references: [Bun tooling](bun-tooling.md) and
[dependency updates](dependency-updates.md).

A package-manager change preserves direct dependency specifications, exact
resolved package identities and integrity, dependency/peer edges, and optional
platform archives unless dependency changes are explicitly authorized. Keep a
resolver or lock-format change separate from a dependency refresh; do not use
general update commands to complete a preservation-only transition. Physical
hoisting differences do not authorize changing resolved versions. Verify native
loading on supported environments rather than inferring it from lock identity.

Review tooling-search matches semantically before changing them. DOM nodes, JSON
tree nodes, pytest identifiers, Celery worker names, product anode fields,
vendor sources, CDN URLs, source maps, and checksums are not obsolete runtime
commands. Parent-monorepo helper paths retain their actual names because the web
checkout does not own them. Explain legitimate remaining matches instead of
rewriting unrelated interfaces or claiming zero literal matches.

## Vite entry changes

Reference: [Vite entry changes](vite-assets.md).

### Adding entries to a running application

Register and build a new logical entry before a live shared template references
it. The registry is cached for the Django process lifetime even in DEBUG;
manifest mtime reload does not reload `entries.json`. Restart the Django process
after registry edits and verify it resolves the new entry. Confirm the manifest
entry and asset hash actually served by Django before reporting the new route
ready.

When extracting a static inline style, preserve every declaration and add the
replacement class even to a tag that previously had no other attributes.
Unlayered application CSS can override layered utilities, so verify computed
styles on the real route. Keep runtime inline sizing/visibility effective; avoid
`!important` on properties changed by map resizing or modal state.

When editing live templates and their CSS/controllers together, wait for a
successful watched or finite build before refreshing the page. Otherwise Django
can serve new controls with old handlers/styles. Smoke-test an integrated slice
on the authenticated route early, including primary actions and served hashes.
Clean-build for final browser evidence.

Controller discovery must retain the negative `!./controllers/*.test.ts` glob
alongside its positive TypeScript glob. Check a clean production graph excludes
test modules; Vitest globals must never reach a browser controller chunk.

Before removing a template fragment, inspect literal includes and inheritance as
well as computed names and their context providers. A text search alone cannot
prove a fragment unreachable. Keep the reviewed dynamic inheritance provider
contract and unresolved-include checks in
`frontend_common/test/template-snippet-ownership.test.ts` aligned with template
changes; do not weaken those checks merely to remove a fragment. The executable
attribute audit does not replace template reachability review.

## CSS candidate rewrites

Reference: [CSS candidate rewrites](tailwind-v4.md).

### Candidate rewrite boundary

Derive mechanical class-rewrite inputs from the entrypoints' explicit `@source`
sets. Restrict rewrites to class-bearing sources in those sets; backend strings,
fixtures, documentation, vendored files, and generated CSS are not blanket
rewrite targets. Review changed filenames and scan for retired candidates after
a rewrite to catch accidental changes outside compiler ownership.

For compiler or shared design-system changes, compare clean baseline and
candidate source inventories, selectors, at-rules, keyframes, breakpoints,
plugin output, and custom properties. Changed CSS serialization or nesting is
not itself a behavior change; preserve the affected rendering contracts. Do not
remove compiler-generated cross-browser fallbacks merely to shrink output or
improve a local timing sample.

Manually inspect real Django-rendered routes with representative permissions,
actual stylesheet order, and verified served asset hashes. Include affected
pseudo-elements, keyboard/focus behavior, accessibility, responsive boundaries,
and touch/hover states. For Git action styling, inspect both rendered anchors,
not a hand-built approximation. Report only the engines and states inspected;
the existing two-engine UI suite does not establish exhaustive cross-browser
visual parity. Automated browser coverage remains limited to the workflows in
`tests/browser/README.md`; these review dimensions do not authorize screenshot
comparisons, GPU capture, or performance benchmarks.

## TypeScript contracts

Reference: [TypeScript contracts](typescript-architecture.md).

### Adding and changing contracts

The workspace-root `ts-types/` directory holds contracts shared by frontend
areas and declarations for browser, worker, tooling and test environments. Its
name is a convention, not a Django or TypeScript discovery mechanism: imports
and the owning `tsconfig` determine which files participate in each check.
Keeping these compiler inputs outside `static/` avoids collecting or serving
them. Types used by only one module belong in that module; feature-local shared
types can live beside the feature in a descriptive `*.types.ts` file. Use
ordinary `.ts` modules for exported application types and `.d.ts` files for
declarations of existing globals and library extensions.

Keep types beside their domain under `ts-types/domain/`, and controller contexts
under `ts-types/controllers/`. Browser globals describe only calls made against
existing CDN/vendor runtimes. Do not install runtime libraries solely to obtain
types, merge production and test Window extensions, or replace a finite URL
contract with an arbitrary callable map. Unknown network/JSON values use their
owner's existing guards; erased assertions describe existing unchecked contracts
without introducing new defaults or exceptions. Type-only class fields use
`declare` to avoid changing constructed objects.

For a new module, add a `.ts` source in its existing owning directory, use its
explicit `.ts` extension in imports, and add a real behavior test. Register a
new route controller in `entries.json`, define its context under
`ts-types/controllers/`, and add an inert JSON declaration in the template.
Exercise actual initialization, load timing, failure and repeated wiring; helper
renderer tests alone do not cover the controller. The asset graph test must
prove that the source is reachable from an approved entry or worker and absent
from unrelated routes.

For an event, keep the owning domain's target, payload and dispatch order
explicit; Window and Document events are different contracts. For an endpoint,
correct the Django/OpenAPI contract, regenerate `@speleodb/api`, and consume its
operation and DTOs through the browser adapter. Keep Django URL declarations for
page navigation only. See [the API client guide](typescript-api-client.md). For
an external global, add only the used constructor/method signatures in
`ts-types/browser/` and keep test fakes in the corresponding test environment.
New runtime validation and product behavior changes require their own behavior
specification and tests.

## Map feature changes

Feature reference: [Map feature changes](map-viewer/design-requirements.md).

When changing these feature areas:

- run `docker exec -w /app speleodb-monorepo-django bun run lint:frontend`
- run `docker exec -w /app speleodb-monorepo-django bun run test:frontend`
- verify private/public parity for shared map behavior

See the [map testing playbook](map-viewer/testing-and-quality.md) for shared
validation guidance.

## Measurement changes

Feature reference: [Measurement changes](map-viewer/measurement.md).

Run all tests in the already-running application container. Use a minimal
MapLibre boundary harness rather than mocking the measurement modules.

Real authenticated Chromium/WebKit verification uses the existing Playwright
setup inside that container and the actual clean Vite build served by Django.
Use automated UI cases for complex interaction workflows and manual review for
visual properties. Check multiple pairs, canceled drafts, right-click, mouse
pan, touch tap/pinch/cancel, keyboard placement, dialogs, editor launch,
source/style changes, globe edges, label contrast/collisions, fullscreen, small
mobile and landscape layouts, 200% zoom, reduced motion, and repeated
activation/teardown. Confirm the served manifest hash and inspect runtime
errors. Record outcomes and remaining limits in external temporary verification
notes; JSDOM results alone are not visual or gesture evidence.

Future route length, snapping, editing, area measurement, persistence, or export
must be designed as explicit product extensions. Keep their data contracts
separate from this temporary point-to-point session.

## Map import changes

Feature reference: [Map import changes](map-viewer/import.md).

Run all tests inside the existing application container; full backend runs
retain the audited GitLab budget. Manual import verification should exercise
both intents, source download, keyboard navigation, narrow/mobile layouts,
fullscreen, and served production assets.

Keep new importer styles reachable from the logical style registry. Staged
uploads, import-session models, workers, and polling require a new product
requirement and measured need.

## Map permission changes

Feature reference:
[Map permission changes](map-viewer/permissions-and-access.md).

When touching permission code:

1. Route project/network checks through the central Config APIs; landmark
   actions use the backend-derived collection capabilities.
2. Verify no special-case feature bypasses write/delete rules.
3. Run:
   - `docker exec -w /app speleodb-monorepo-django bun run lint:frontend`
   - `docker exec -w /app speleodb-monorepo-django bun run test:frontend`
4. Confirm UI and action availability is consistent for:
   - `WEB_VIEWER`
   - `READ_ONLY`
   - `READ_AND_WRITE`
   - `ADMIN`

## Depth coloring changes

Feature reference:
[Depth coloring changes](map-viewer/depth-domain-reactivity.md).

- Keep domain APIs pure where possible (`map/depth.ts`).
- Keep map mutation concentrated in layer/legend modules.
- Prefer extending existing helpers over introducing parallel utilities.
- If event payload shape changes, update all listeners and tests together.

### Required validation

After depth-domain changes, run inside the existing application container:

- `docker exec -w /app speleodb-monorepo-django bun run lint:frontend`
- `docker exec -w /app speleodb-monorepo-django bun run test:frontend`
- `docker exec -w /app speleodb-monorepo-django bun run build`

Stop the local webserver and its watcher before the finite production build. For
browser verification, serve those assets through Django and confirm the manifest
in use. Manually verify:

1. depth mode project hide/show updates color scale immediately
2. all-hidden projects in depth mode shows `N/A`
3. shared automatic behavior remains aligned; private limits do not leak
   publicly
4. limit/unit edits update labels and the current hover without another mouse
   move
5. project/country toggles and delayed loading retain a configured scale

## Asynchronous viewer changes

Feature reference: [Asynchronous viewer changes](map-viewer/async-updates.md).

Run the complete JavaScript suite, lint, checked production build and browser
tests inside the existing application container. `make test` runs backend
pytest, frontend Vitest, and the browser wrapper through `test-py`,
`test-frontend`, and `test-browser`. Browser checks own UI/UX: real rendering,
control state, interaction during a gated response, visible error/retry
behavior, and the final displayed result. Use small deterministic surveys and
overlays; large preparation and worker-transfer inputs remain in the lower-layer
suites.

Default UI tests use small fixtures and do not establish scale or latency
guarantees. Unit scheduling, cancellation, and cooperative-yield tests verify
application behavior rather than real-browser throughput. A separate performance
benchmark requires explicit authorization and must remain opt-in.

Wait for actual renderer readiness when projecting pointer targets or asserting
visible map output. A controlled response gate exercises rapid input during
loading without manufacturing delays or replacing renderer methods. Investigate
individual browser executions over five seconds, preserve justified UI coverage,
and keep one worker with zero retries. See
[browser checks](../tests/browser/README.md) for the durable boundary, fixtures
and measurement procedure.

## OGC geometry extensions

Feature reference:
[OGC geometry extensions](map-viewer/ogc-url-and-geometry-contract.md).

Supporting polygons would be a product/API extension. Update `GEOMETRY_GROUPS`,
the `ogc_typed_id` converter, OpenAPI schemas/examples, migration-link
candidates, service assumptions, documentation, and positive/negative client
regression fixtures together. Verify actual discovery and rendering before
advertising the new group.

## Map providers

Feature reference: [Map providers](map-viewer/features.md).

Provider extensions belong in the shared `MAP_SOURCES` registry. Its order
controls both menu order and the first token-satisfied fallback. Update the
order-sensitive expectations in `map/sources.test.ts` and the documented source
list together. Keep provider logic shared across entrypoints and untrusted data
out of trusted static icon markup.

## Map settings

Feature reference: [Map settings](map-viewer/settings.md).

Category extensions belong in `DEFAULTS.DISPLAY` metadata/defaults and the
existing renderer/lifecycle gates. Reuse Settings rows and centralized state and
permission APIs. Document stable DOM hooks, escape user/API values, and cover
the new gate through creation, refresh, async completion, and style rebuilding.

Run tests only in the existing application container. Inspect the authenticated
browser at 320/390px, tablet, desktop, short landscape, fullscreen, 200% zoom,
and reduced motion. Stop the local webserver and its watcher before the clean
production build, then serve those assets through Django, refresh the browser,
and verify the served manifest before final screenshots. Check bounds, focus,
and network behavior as well as visuals, and record actual results in external
temporary verification notes.

## Survey section colors

Feature reference: [Survey section colors](map-viewer/shot-coloring.md).

Run frontend tests only in the existing application container. Expression
conversion behavior should also be verified through the map renderer rather than
inferred from mocked paint calls. Browser verification should cover narrow
screens, short landscape, keyboard focus, and 200% zoom after a clean production
asset build.

## Shared map packages

Feature reference: [Shared map packages](map-viewer/shared-packages.md).

Run checks inside the running application container from `/app`. Stop the local
webserver and its watcher before the finite production build:

```sh
bun run typecheck
bun run lint:frontend
bun run test:frontend
bun run build
```
