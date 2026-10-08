# Vite Assets with a Django Backend

## Feature intent

Vite is SpeleoDB's one compiler, dependency graph, manifest, and disk watcher
for application CSS and TypeScript, emitting browser JavaScript. Django still
owns routing, templates, authentication, static URL generation, and every HTTP
response. This boundary removes duplicated Tailwind/esbuild orchestration
without turning the Django application into a Vite-served SPA.

## Registry and output

`frontend_common/entries.json` names every route-owned entry. Both
`vite.config.ts` and Django resolve that registry; a name cannot silently mean
different source files on each side. Production output is content-hashed and
minified under `speleodb/common/static/speleodb/vite/`, with source maps off.
Development output includes source maps and publishes complete immutable
generations under `assets/dev/<session>/<generation>/`. Django serves a
completed generation, and the development client reloads after a newer one is
published.

One graph does not mean one payload. Tailwind is shared, shell/route styles stay
isolated where cascade ownership matters, route controllers are lazy, and common
imports become shared chunks. The browser receives only the bootstrap, declared
controller branches, applicable styles, and established vendors for the route.

## Template integration

`speleodb.common.templatetags.vite_assets` provides three typed tags:

- `vite_styles` renders named CSS entries in caller order;
- `vite_preload` recursively deduplicates static imports and explicitly named
  controller branches;
- `vite_script` renders the module bootstrap.

Every URL passes through Django static storage. DEBUG reloads the manifest by
mtime and may use registry-derived stable paths before the first watcher build.
Production caches the manifest and raises `ImproperlyConfigured` for missing,
malformed, unsafe, duplicate, unknown, or wrong-type entries.

Templates provide controller context only as inert `application/json` or safe
`data-*` attributes. `frontend_common/app.ts` parses context and initializes
controllers sequentially in document order. Controllers import application
modules explicitly; they do not publish globals merely to support old script
loading. Generated map actions use delegated inert `data-map-action` metadata,
and user/API values still pass through the existing escaping boundary.

The bootstrap remains at the end of each owned document and applies critical
parser-time state before starting lazy imports. Public particle canvases are the
one measured-layout case: their container dimensions are snapshotted by the
bootstrap and consumed on the controller's first sizing pass, preserving the old
tail script's initialization phase. Later viewport resizes always use live
dimensions.

## Ownership boundaries

Vite owns all SpeleoDB-authored CSS/JS source. CDN and vendored libraries,
Mapbox, jQuery-family plugins, and Django-generated `url_reverse.js` remain
external globals in their existing relative order. Runtime-derived CSS custom
properties may remain in markup; static style blocks do not.

Dark metadata, the Dark Reader lock, private `.dark`, public roots without
`.dark`, and stylesheet cascade order are rendering contracts. Moving a style
into Vite must preserve its former template-block position.

### TypeScript source delivery boundary

TypeScript modules remain beside their original static-directory owners during
translation, but are compiler inputs rather than downloadable static assets.
`CompiledStaticFilesConfig` adds `*.ts` to Django's standard
[`ignore_patterns`](https://docs.djangoproject.com/en/6.0/ref/contrib/staticfiles/#customizing-the-ignored-pattern-list),
retaining its default exclusions. Django owns collection traversal and matching;
there is no custom collection filter. This excludes `.ts` and `.d.ts` files
without changing deployment commands.

The two finder subclasses in `speleodb.common.staticfiles` only reject direct
`.ts` lookups. This separately protects development static responses: collection
ignore patterns do not apply to `findstatic` or direct HTTP requests. Their
listing behavior is inherited unchanged from Django.

Vite-emitted JavaScript, workers, CSS, and existing vendor distributions retain
Django's normal discovery order, storage handling, prefixes, and ignore
patterns. Direct lookup adds one suffix check without reading asset contents or
changing Vite's input graph. Focused static-source tests exercise both finder
types, both lookup modes, actual static-view 404 responses, and collection with
both stock Django finders and the lookup guards into an isolated local
directory. Collection tests do not upload to S3 or certify a deployed CDN.
Deployment must use the resulting collected artifact; these finders do not
remove files previously published outside Django's collection workflow.

The root pytest `live_server` fixture collects assets once per session into a
temporary local `STATIC_ROOT`, preserving the configured media storage. It wraps
pytest-django's existing server fixture without replacing its lifecycle or HTTP
handler. Settings are overridden only while collecting and during each
live-server test, so other tests retain their original storage configuration.
This is necessary because pytest-django recognizes only the literal
`django.contrib.staticfiles` entry when choosing finder-backed serving; an
explicit `AppConfig` uses its normal collected-file handler instead. Browser and
upload integration tests therefore exercise the standard collected artifact. A
real HTTP contract compares the served compiled script with its build output,
checks vendor delivery, and verifies raw TypeScript returns 404.

## Verification and performance

Contract tests reject direct first-party static references, executable inline
application scripts, event attributes, unknown registry sources, parallel
compiler commands, and Vite client/server integration. Unit tests cover manifest
parsing/failures, recursive preloads, DEBUG fallback, bootstrap context parsing,
duplicate initialization, runtime map context, and delegated map actions.

Page stylesheet-count and cascade-order assertions identify stable entry
filenames, not their parent directories. Run these contracts with both
production and development manifests: development URLs include a session and
generation between `assets/` and the filename.

The isolated watcher test proves graph invalidation without touching a running
Django or developer process. Final browser evidence always starts from a clean
production build because Tailwind's in-process scanner can retain a deleted
template candidate. Release verification compares manifest-served hashes, route
request graphs, computed styles, behavior, accessibility, pixels, and
transfer/parse/init/style-recalculation performance against the preserved
baseline.

## Adding entries to a running application

Register and build a new logical entry before a live shared template references
it. The registry is cached for the Django process lifetime even in DEBUG;
manifest mtime reload does not reload `entries.json`. Trigger development Python
autoreload after registry edits and verify the running process resolves the new
entry. JSON edits alone need not trigger that reload. Confirm the manifest entry
and asset hash actually served by Django before reporting the new route ready.

When extracting a static inline style, preserve every declaration and add the
replacement class even to a tag that previously had no other attributes.
Unlayered application CSS can override layered utilities, so verify computed
styles on the real route. Keep runtime inline sizing/visibility effective; avoid
`!important` on properties changed by map resizing or modal state.

When editing live templates and their CSS/controllers together, verify the root
disk watcher is running or build the companion assets before exposing the
markup. Otherwise Django can serve new controls with old handlers/styles.
Smoke-test an integrated slice on the authenticated route early, including
primary actions and served hashes. Stop the watcher and clean-build for final
browser evidence.

The disk watcher shares the Django container console. Keep stdout/stderr
attached and `clearScreen: false` so rebuilds cannot erase application logs.
Controller discovery must retain the negative `!./controllers/*.test.ts` glob
alongside its positive TypeScript glob. Check a clean production graph excludes
test modules; Vitest globals must never reach a browser controller chunk.

## Development publication and reload

`scripts/dev.ts` supervises Vite's disk watcher and the three-project semantic
watcher. Compose adds Django to that same supervisor through `--django`.
Required-child failure stops the other processes and returns failure; SIGINT and
SIGTERM reach child process groups, with a bounded shutdown grace period. Logs
remain attached and semantic errors stay visible. Production builds still
require successful type checking and both ownership audits before emission.

The Vite development plugin compiles into a stable staging tree under
`.vite/pending/`. Vite caches unchanged worker bundles between watch builds;
copying the complete relative output graph into
`assets/dev/<session>/<generation>/` keeps those workers in the same published
generation as the entries, shared chunks and CSS. Relative imports and worker
URLs remain unchanged. The plugin validates registered entries, import edges and
every referenced file before atomically renaming the pending manifest to the
canonical manifest. A failed build never replaces that completion marker. Prior
generations remain available for old pages and their later lazy imports; stop
watchers and run the normal clean build to reclaim them.

Django's asset tags share a manifest snapshot for the whole template render,
including inherited and included templates. The app script carries its
generation and the DEBUG-only `__assets__/generation/` endpoint URL. The
endpoint is GET-only and sends no-store cache headers. A development-only module
polls the completed generation, comparing the first response with the generation
rendered into the page. It records an attempted target in session storage before
reloading once. Stale HTML cannot repeatedly reload for that same target;
unavailable storage, malformed responses and network failures do not navigate.
Template changes trigger a Vite rebuild even when no Tailwind class changes.

Production registers no reload endpoint, emits no development client, and adds
no reload attributes to its app script. Tests cover publication failure and
recovery, retained worker/assets, render-time races, stale-page loops, failed
storage/network responses, and real subprocess signal/failure cleanup. The
watcher verifier exercises actual Vite builds in an isolated temporary tree.

## Verification boundaries

The original Vite migration demonstrated deterministic builds, watcher
invalidation, focused manifest/controller tests, a public-route cross-engine
comparison, and production-shaped local static-file MIME/CORS behavior. Those
results did not certify the complete authenticated role/map/interaction matrix,
production S3/CloudFront delivery, deployed lifecycle, or all runtime
performance budgets. Local static-file checks are not proof of a production CDN
deployment.

For current changes, run the repository's focused checks inside the existing
application container and report the routes, engines, data states, and delivery
environment actually exercised. The checked-in browser suite covers controller
and template parity alongside viewer responsiveness; it does not replace a full
baseline/candidate asset migration comparison. Verify runtime performance as
well as compressed size before making a performance-parity claim. Build hashes
and historical test counts apply only to the exact revision that produced them.
