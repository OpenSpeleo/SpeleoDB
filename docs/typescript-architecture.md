# TypeScript architecture

## Intent and current scope

SpeleoDB uses strict TypeScript for first-party browser code, tests, and
tooling. Vite remains the only browser compiler, Bun runs tools, and Django
remains the only HTTP server. Every first-party runtime, test and tool source is
TypeScript. Compilation checks the complete source graph; runtime and browser
acceptance remain independent verification gates.

## Compilation boundaries

There are exactly three configuration files and three independent no-emit
projects:

| Configuration               | Environment and ownership                                                                                  |
| --------------------------- | ---------------------------------------------------------------------------------------------------------- |
| `tsconfig.json`             | Browser DOM and Vite import metadata; application runtime and shared strict compiler options               |
| `tsconfig.worker.json`      | WebWorker globals; GeoJSON worker and transport                                                            |
| `tsconfig.development.json` | DOM, Node, Bun and Vitest; all tests, browser instrumentation, tools and declarative Railway configuration |

Worker and development configurations extend the root browser configuration,
then explicitly replace its libraries, ambient packages, source includes,
exclusions and build-info path. There is no separate base or solution file and
no project references. The aggregate and watch commands pass all three paths to
the native compiler's build mode. Production and worker checks remain
independent of development globals; tests and tools deliberately share one
broader development environment. This reduces configuration overhead while
protecting code delivered to browsers and workers.

The root owns strict checking, unknown catch values, checked indexed access,
exact optional properties, isolated modules, erased-only syntax and bundler
resolution. Forced module detection keeps import-free test files from
contributing accidental ambient globals. Every project has a distinct ignored
build-info file under `.cache/typescript/`. Vite alone emits browser assets.
Tool loading uses Bun and root ESM package metadata; the bundled Vite/Vitest
configuration loader remains unchanged.

All three projects use `allowJs: false` and `noEmit: true`; there is no
mixed-source configuration. Unit tests and controller discovery use TypeScript
sources, with controller test files excluded from browser discovery. The source
audit rejects same-stem JavaScript/TypeScript ambiguity. First-party module
specifiers use their physical `.ts` or `.d.ts` extension, including dynamic
imports and test mocks. Physical worker URLs also use `.ts`. Vite-generated
assets, external vendors and dependency internals retain their real `.js` paths.

Browser source directories are `frontend_private/static/private/ts/`,
`frontend_public/static/ts/`, and `frontend_errors/static/ts/`. The directory
names identify the authored language; Vite does not compile beside those source
files. It emits hashed JavaScript under `speleodb/common/static/speleodb/vite/`.
The existing vendor subdirectories move with their owners, retaining their
original JavaScript filenames and contents. Django serves those approved vendor
files. Its standard `ignore_patterns` configuration excludes TypeScript inputs
from collection; the small finder guards separately block direct source lookup
during development.

## Checker and lint compatibility

The authoritative checker is TypeScript 7.0.2, installed as `@typescript/native`
via the `typescript` package alias. typescript-eslint 8.71.1 consumes the
TypeScript 6 compiler API provided by
`typescript: npm:@typescript/typescript6@6.0.2`. All checking scripts explicitly
select the native checker so executable-bin collision order cannot select the
compatibility implementation. Type-aware lint covers first-party TypeScript;
vendor distributions remain outside authored-source compilation.

Separate typed-lint canaries cover browser, worker and development environments.
Each inherits its real compiler options and ESLint rules but limits source
inputs to two temporary fixtures: a typed value and an unsafe JSON assignment.
This avoids rebuilding the application graph merely to check compiler API
compatibility. The ambient-isolation canaries still include each full
application project, and normal typecheck/lint commands check the complete
source tree. Unit-test timeouts and browser performance budgets remain
unchanged.

This follows Microsoft's documented
[side-by-side alias arrangement](https://devblogs.microsoft.com/typescript/announcing-typescript-7-0/#running-side-by-side-with-typescript-6-0):
TypeScript 7.0 does not expose a programmatic compiler API. The package named
`typescript` supplies that API for lint and source inspection, while every
application checking command explicitly runs TypeScript 7.0.2. The compatibility
package's API reports 6.0.3; it does not replace the authoritative checker.

Literal translation retains existing `var` hoisting, declared `async` functions,
unused bindings, and comments, so stylistic `no-var`, `prefer-const`, unused
binding, and `require-await` rules are not migration requirements. Unsafe-value
and explicit-`any` rules remain enabled. Five named files (shared
`security/html.ts`, map `config.ts`, map `utils.ts`, map `depth.ts`, and the
experiment-data controller) retain their tested `String(unknown)` coercion
contracts, including objects and throwing coercions; only `no-base-to-string` is
disabled for these owners. These exceptions do not authorize new fallbacks or
changed invalid-input behavior.

The station experiment module has two local documented lint exceptions: its
recursive API-error formatter preserves terminal `String` coercion, and its
existing async DOM submit listener returns a promise that the browser ignores.
Resource click listeners and sensor fleet-change listeners use the same local
exception when the original callback returns a promise. Resource callbacks also
retain their lexical receiver aliases, documented at each existing capture.
Characterization tests cover callable/primitive error messages and listener
promise settlement. These exceptions retain callable forms rather than adding
new wrappers or error policies.

Catch paths may forward an unknown rejection without wrapping it. The promise
rejection lint rule therefore permits `unknown` while still rejecting explicit
non-error literals; this preserves promise settlement and error identity.

The public shell composes `ParticleAnimation` and `Highlighter` from its own
`animation/` modules. Importing the classes starts no work: shell initialization
still initializes AOS, conditionally constructs each carousel, then constructs
particles and highlighters in document order. The classes own their existing
canvas, mouse, resize, and animation-frame behavior. Their instances remain
independent across repeated shell initialization, without a new teardown policy.
Type-only fields use `declare`, preserving instance property creation order.
Five local `unbound-method` annotations identify listener/RAF registrations
whose methods are already bound once in their constructors; lifecycle tests
assert callback identity and duplicate initialization. The edge-alpha
calculation uses explicit numeric coercion after `.toFixed(2)`, preserving the
original rounded string's arithmetic result. These annotations and the coercion
are part of the literal-translation contract, not a new animation lifecycle.

The feedback click listener remains declared `async`; its local lint annotation
preserves the existing event registration and internal error catch. Controller
tests cover network, JSON, response, and missing-context failures. Its HTML
error interpolation escapes the selected server message before entering the
HTML-accepting modal facade; malicious-input tests retain the literal text.

The development project deliberately does not load `vite/client`: Bun already
owns its import-meta ambient declarations, which conflict with the Vite client
declarations. Production independently retains `vite/client`, without Bun.

Browser vendors remain existing external runtimes. Added declaration packages
provide types only; they do not introduce corresponding browser dependencies.
The JSDOM preload bridge uses narrow tooling-owned declarations for the private
hooks it consumes, preserving its installed Undici selection and WebIDL proxy
registration. Those bridge declarations are not browser globals.

## Commands and verification

- `bun run typecheck` checks all three projects without emitting browser code.
- `bun run typecheck:<project>` checks an individual environment.
- `bun run typecheck:watch` performs incremental semantic checking.
- `bun run lint:frontend` checks first-party TypeScript.
- `bun run test:frontend` runs the TypeScript Vitest suite.
- `bun run test:frontend:watch` keeps that suite running.

Both production build commands check types and both ownership audits before Vite
emits assets. `build` performs those checks before deleting existing output;
`build:assets` applies the same checks without cleanup. The obsolete JavaScript
command aliases are removed. The development command supervises a Vite disk
watcher and semantic TypeScript watcher. Django remains the only HTTP server;
completed immutable generations trigger one full-page reload. See
[development publication](vite-assets.md#development-publication-and-reload).

Run installs and verification in the existing application container at `/app`.
Verify frozen reinstall, compiler identities, typed-lint rejection, full unit
discovery, the watcher and an isolated production build. Compare registry and
manifest entries, output graphs and clean CSS with the JavaScript baseline.
Annotations and declarations add no browser runtime work; output comparisons
protect that property.

## Source ownership and executable-template audits

`bun run audit:javascript` enforces zero first-party `.js`, `.mjs`, and `.cjs`
source and rejects simultaneous JavaScript/TypeScript files with the same stem.
Its only source-file exceptions are the fifteen exact existing vendor paths. New
code under a vendor directory does not inherit an exception. The ordinary
filesystem walk excludes dependency directories and explicitly owned generated
output, and works in the standalone application container without Git metadata.
CI can additionally pass `--tracked` to inspect Git's tracked filenames without
those exclusions, preventing committed source from hiding under an output or
dependency path. CI runs both modes.

`bun run audit:templates` rejects executable script bodies, native event
attributes, and executable Alpine attributes in authored templates. Inert JSON,
external script loading, comments, and inert data hooks are preserved. A
TypeScript compiler syntax-tree walk also examines runtime string literals and
template expressions that contain generated HTML, including interpolated
attribute values. This uses the compiler API compatibility package and never
loads application runtime modules. Test fixture examples and the exact vendor
files are excluded from generated-runtime inspection. Arbitrarily computed HTML
still requires the existing HTML-sink security review; static string inspection
cannot prove the behavior of arbitrary runtime string assembly.

Append `--inventory` only when a diagnostic JSON inventory is needed: its
successful reporting exit status is not an enforcement pass. Normal build and CI
commands omit that flag, and any finding fails their gate. CI also checks the
tracked-file inventory after checkout.

Typed audit tests exercise ownership exclusions, tracked output paths, ambiguous
stems, command exit behavior, quoted HTML attributes, inert scripts, and real
compiler parsing of generated markup. Their temporary repositories and files are
created outside the checkout and removed after each test. Auditing adds no
browser payload or runtime work.

The generated URL contract currently contains 79 routes. Its finite keys and
argument tuples are checked against Django's `url_config.json`, alongside
literal frontend uses and compiler rejection cases for unknown routes, arbitrary
strings, and incorrect arguments. This count comes from the current generated
contract rather than the initial migration inventory estimate of 80.

## Typed Alpine ownership

Templates carry inert `data-speleodb-bind` identifiers and `data-speleodb-scope`
markers. Private navigation owns private-shell, entity-menu and preference
bindings; the public shell owns mobile navigation, welcome and home bindings;
revision history owns desktop and generated mobile menus. Equivalent entity
menus share a fresh-state factory and receiver-based mechanics while each inert
identifier retains its explicit policy and independent scope. Private user and
revision menus retain their different modifiers, focus and ARIA behavior. The
original transitions, `x-ref` and `x-cloak` declarations stay in templates
because they contain no executable application expression. Preference initial
values are inert data attributes.

`frontend_common/runtime/alpine.ts` registers function-valued `Alpine.bind`
objects through the vendor's tree initialization interceptor. It initializes
available scope roots in parent-first order after Alpine's queued auto-start,
then uses Alpine's existing mutation observer for inserted revision clones.
There is no second `Alpine.start()` or application mutation observer. Repeated
controller registration does not rebind existing scopes; removed and reinserted
scopes still follow Alpine's cleanup and initialization lifecycle. A missing
vendor leaves an initialization listener without blocking other controllers.

This moves expression activation from vendor script evaluation to the owning
controller's binding registration. That startup adjustment allows compiled
behavior without executable template attributes while retaining route imports.
The real-vendor suite covers all entity menu families, stopped/prevented clicks,
outside/Escape differences, mobile measurements, preference serialization,
transitions, cloned menus, delayed vendor availability and repeated startup.

The typed bootstrap retains immediate tail-module initialization, sequential
controller discovery, failure isolation, retry after failure and overlapping
calls until success. Context JSON remains `unknown`, including primitive values;
the loaded controller owns its context contract. Returned cleanup functions
remain ignored. Common test setup and source-contract suites are TypeScript.

The obsolete ajax-error, cylinder and sensor template script snippets were
removed after source-contract tests proved there were no direct includes and no
unresolved dynamic include names. The test also records the finite dynamic
inheritance provider contract, so computed template names cannot silently make
those fragments reachable again. The permanent template audit now passes with no
executable first-party template expressions.

The watcher check and authenticated upload subprocess run directly with Bun as
TypeScript. The subprocess still reads its live-server URL and session cookie
from stdin, writes the same JSON result to stdout and inherits the GitLab audit
environment. JSDOM's native XHR performs the existing HTTP/multipart requests.
The development project owns Playwright and its instrumented Window alongside
unit tests, tools and the upload subprocess. Those evidence types never enter
production or worker ambient environments.

Literal numeric contracts retain JavaScript's native operand coercion. Date
subtraction uses erased operand assertions instead of introducing calls to a
replaceable global coercion function. Stored display preferences retain the
original property reads for both validation and assignment; restoring a checked
value does not cache an accessor result or replace its owning object. The
preference suite exercises this read ordering in addition to ordinary JSON
persistence, without adding runtime work.

Ambient isolation is checked with the native compiler against each project's
complete imported closure. Positive fixtures verify the intended globals;
negative fixtures reject Node, Bun, Vitest, browser, and worker globals where
they do not belong. Browser instrumentation and test globals are permitted in
development and excluded from the authoritative production and worker checks. An
empty source fixture alone would miss ambient globals introduced transitively by
dependencies, so these checks inherit the real source includes and declarations.

## Runtime ownership

Shared security primitives live in `frontend_common/security/`; the existing
form and map facades preserve their different fallback and receiver contracts.
Map `defaults.ts` owns the single `DEFAULTS` object, re-exported by `config.ts`.
Keeping constants independent of mutable Config breaks the Config/API/Utils
initialization cycle. Map transport owns response parsing and augmented errors;
endpoint forwarding and live CSRF policy remain behind API. Landmark transport
retains its distinct empty-response and error policies.

Form lifecycle helpers share raw CSRF reads, modal status and navigation while
owner callbacks retain serialization, validation, receiver and timing policies.
Landmark form model and presentation modules are shared by map and collection
UI, with direct function aliases retained in `LandmarkForms`. Station experiment
and sensor validation/presentation are separate from network and permission
orchestration. Import model/presentation modules accept live session inputs;
`DataImport` owns cancellation, generations and transport.

GIS list presentation no longer imports another controller. The GIS upload
feature owns its initializer; route controllers compose it. Format-specific
survey parsers preserve each format's accepted input, and shared result-modal
mechanics take explicit MIME, filename, syntax and post-highlight policies.
Public animation classes remain in the public shell's dependency graph.

Viewer roots share read-only lifecycle primitives. Public composition does not
register editing actions or import private tools; its graph and real startup are
tested independently. Shared Config/API and rendering facades still contain
domain methods, so the boundary is registration and runtime reachability, not a
claim that every mutation endpoint string is absent from public assets. The
test-only runtime import walker checks both public capability boundaries and the
Config/API dependency cycle through static imports, re-exports, nested dynamic
imports and module-relative worker URLs. It excludes erased type-only
declarations while retaining the empty runtime imports emitted for inline `type`
specifiers under `verbatimModuleSyntax`. Unclassified dynamic or worker paths
fail the boundary check; registry and glob expansion remain covered by the Vite
asset graph tests. Visibility selectors own the country-plus-project gates used
by rendering and snapping. Feature renderers and display scheduling sit beneath
the stable Layers facade; generation, revision and latest-intent checks remain
with their owners.

## Adding and changing contracts

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
add the specific request/response records and generated URL key/argument tuple,
then extend the URL contract test. For an external global, add only the used
constructor/method signatures in `ts-types/browser/` and keep test fakes in the
corresponding test environment. New runtime validation and product behavior
changes require their own behavior specification and tests.

## CI, publication and rollback

CI verifies frozen root installation, compiler identity and ambient isolation,
source/template audits, strict checking, lint, unit tests, watcher invalidation
and the guarded production build. The serial Django suite covers asset tags,
source exclusion and the real upload subprocess. Its separate browser wrapper
starts pytest's live server with a verified temporary login user and runs
controller/viewer parity plus the unchanged Chromium/WebKit workloads after
other CPU-heavy checks finish. Explicit database-only project and form fixtures
provide writable/read-only contexts; the inherited GitLab audit remains active.
Two test-only HTTP routes supply revision/tree presentation JSON because WebKit
does not intercept native synchronous XHR through Playwright routing. Production
controller URLs and synchronous behavior remain unchanged. The wrapper verifies
those routes before launching browsers and never prepares a Git repository. CI
retains the JSON browser report, attachments and failure screenshots.

Railpack remains Python-provider based, selects Bun through Mise, runs the
checked root build, then removes `node_modules`. Railway predeploy retains
migrations, background schedules and `collectstatic`; semantic checking never
moves to predeploy. These checks do not authorize executing Railway or
deploying.

Treat the application revision, entry registry, manifest and hashed asset set as
one release artifact. Record clean output hashes and compare actual Django
served URLs and bytes before browser evidence. Keep prior hashed assets during
the rollback window; restore a matching manifest with the application revision.
Django static finders exclude authored TypeScript and production emits no source
maps. Compilation and lint success alone do not establish browser, performance,
GitLab cleanup or served-asset acceptance.

The development project checks Vitest configuration alongside all other tests
and tools. Its intentional DOM/Node/Bun/Vitest environment accommodates the
upstream configuration types, including their JSDOM and DOM references, without
shadow declarations or changes to the bundled loader. Independent browser and
worker projects prevent those development globals from entering production
checks.
