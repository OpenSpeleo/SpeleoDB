# Vite Assets with a Django Backend

## Feature intent

Vite is SpeleoDB's one compiler, dependency graph, manifest, and disk watcher
for application CSS, JavaScript, and future intentionally introduced TypeScript.
Django still owns routing, templates, authentication, static URL generation, and
every HTTP response. This boundary removes duplicated Tailwind/esbuild
orchestration without turning the Django application into a Vite-served SPA.

## Registry and output

`frontend_common/entries.json` names every route-owned entry. Both
`vite.config.mjs` and Django resolve that registry; a name cannot silently mean
different source files on each side. Production output is content-hashed and
minified under `speleodb/common/static/speleodb/vite/`, with source maps off.
Development output uses stable names and source maps so Django can serve each
completed rebuild after refresh.

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
`data-*` attributes. `frontend_common/app.js` parses context and initializes
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

## Verification and performance

Contract tests reject direct first-party static references, executable inline
application scripts, event attributes, unknown registry sources, parallel
compiler commands, and Vite client/server integration. Unit tests cover manifest
parsing/failures, recursive preloads, DEBUG fallback, bootstrap context parsing,
duplicate initialization, runtime map context, and delegated map actions.

The isolated watcher test proves graph invalidation without touching a running
Django or developer process. Final browser evidence always starts from a clean
production build because Tailwind's in-process scanner can retain a deleted
template candidate. Release verification compares manifest-served hashes, route
request graphs, computed styles, behavior, accessibility, pixels, and
transfer/parse/init/style-recalculation performance against the preserved
baseline.
