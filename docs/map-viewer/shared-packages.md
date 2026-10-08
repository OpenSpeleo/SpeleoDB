# Shared map packages and MapLibre integration

The web and mobile viewers consume two SpeleoDB packages. `@speleodb/map-core`
owns portable geometry, depth, bounds, visibility and unit algorithms.
`@speleodb/map-viewer` owns MapLibre style expressions, layer specifications and
identical marker artwork and the globe atmosphere renderer. App code owns
backend transport, permissions, persistence, scheduling, user interaction and
provider selection. These are SpeleoDB libraries, not a generic map framework.

The web startup camera is application-owned: a wide globe centred on France
(`DEFAULTS.MAP.CENTER`, zoom `0`). Provider camera metadata is discarded. The
camera is applied once after the first style installs the globe projection,
avoiding Mercator viewport constraints during asynchronous startup. Existing URL
destinations and loaded-project bounds then take precedence as before; later
style loads do not reset navigation. This adds no data scans or requests. Unit
and real-renderer browser tests cover foreign provider cameras, tall viewports,
and preservation of subsequent navigation.

## Globe presentation

Both web composition roots attach `attachGlobeAtmosphere` before loading their
first style. The shared package renders a dark space background, deterministic
stars and a soft white atmospheric rim in one MapLibre custom layer. It uses
public custom-layer projection matrices rather than a screen-centred CSS circle,
so zoom, bearing, pitch, camera padding and resize follow the actual Earth.
Projection transition opacity removes the decoration in Mercator views. Native
atmosphere blending is disabled to avoid painting its hardcoded blue rim over
the shared white appearance.

The attachment owns its `style.load` and `remove` listeners and GPU resources;
replacing a style recreates the layer without resetting the camera. Provider
basemap visibility capture excludes this application layer, including tokenless
styles: a transparent basemap anchor keeps replacement rasters underneath it.
Survey sources, labels, provider attribution and overlay ordering retain their
existing owners. Map-height resize handlers and delayed resize work are released
when the map is removed.

This rendering costs one viewport-sized draw per map frame and no additional
network requests, feature traversal, texture downloads or animation loop.
`globe-appearance.spec.ts` checks actual screenshot pixels for dark space, stars
and the white halo in both private and public viewers, then exercises camera
padding, rotation, pitch, resize, style replacement and Mercator/globe changes.
The existing camera and basemap suites retain provider metadata and source
identity coverage. Build manually inside the application container before
running browser checks; refresh manually after a successful build.

## Web renderer and providers

Both the authenticated viewer and public GIS viewer construct the same imported
MapLibre GL JS engine through `map/renderer.ts`. The boundary exposes narrow,
structural capabilities to existing controllers and test doubles; production
never installs a renderer global. Vite bundles its CSS and explicitly emits
`maplibre-gl-worker.mjs?worker&url` with its dependencies; `setWorkerUrl`
prevents unresolved sibling worker URLs after engine code is placed in hashed
chunks. Geometry details and project forms link to the viewer and have no
separate map engine.

MapLibre changes the engine while preserving web providers. The default remains
Mapbox Satellite Streets v12 when a token is present, with its real vector city
and place labels. `normalizeMapboxRequest` maps the classic style, TileJSON,
sprite (including retina suffixes) and glyph URLs to the documented Mapbox HTTPS
APIs using MapLibre's `transformRequest`. Requests to other hosts and protocols
are unchanged, so provider credentials cannot leak to application downloads or
ESRI. Do not replace these labels with raster labels or silently drop layers.
`MAPBOX_API_TOKEN` remains a provider credential. The provider's unmodified
88×23 logo is retained as a control whenever the Mapbox base style is loaded; it
remains present on ESRI switches because that style still supplies overlay
glyphs. Native source attribution retains the TileJSON credits. Its public
control lifecycle is wrapped to remove only Mapbox's “Improve this map” feedback
link, including when source credits refresh. A DOM observer is scoped to that
control and disconnected on removal; copyright credits and the native compact
toggle are preserved without extra requests or changes to provider metadata. The
logo artwork comes from the
[Mapbox GL JS 3.12.0 stylesheet](https://api.mapbox.com/mapbox-gl-js/v3.12.0/mapbox-gl.css)
and follows Mapbox's
[attribution guidance](https://docs.mapbox.com/help/dive-deeper/attribution/).

The ESRI Satellite, World Hillshade and dark hillshade choices keep their
existing identifiers, attribution and zoom limits. `speleo_map_source` values
continue to work. Ordinary source switching replaces only the app raster layer
and restores the captured native basemap visibility; it does not reset the map
style, serialize survey GeoJSON, rebuild sources or refetch data. The shared
missing-image hash list is enforced through a scoped, abortable MapLibre tile
protocol. Missing-image matches carry HTTP status 404 so MapLibre can try
parent/child tiles, as it does for a provider 404. Other HTTP failures retain
their actual status; abort rejection and cache metadata pass through unchanged.
Global `fetch` is never patched.

The style transform converts the provider globe projection before MapLibre
validates the style, preserving source and vector-layer definitions. Existing
measurement and drawing tools continue using public surface/project/unproject
methods and their horizon guards. DOM markers use MapLibre's
`opacityWhenCovered`; custom marker images use its Promise-returning `loadImage`
API.

## Shared logic and application policy

Web layer adapters use shared overview stroke construction, shot/depth color
expressions, station/landmark specifications and GIS vector specifications. They
supply existing source and layer IDs, colors, zoom thresholds, width and size
policy. Their data lifecycle remains web-owned. The web depth ramp remains
linear with its existing shallow/mid/deep colors, missing-value fallback and
zero-domain fallback; the shared normalized expression also keeps interpolation
stops distinct for subnormal positive domains. Mobile supplies its own ramp and
transfer function. Neither package branches on an app name.

Marker images are package assets. The shared runtime-context boundary resolves
the complete icon catalog once for both map sprites and DOM menus, dialogs and
panels, including the legacy `bone` and `cylinderOrange` keys. Nonempty context
overrides remain possible; omitted or empty values use the bundled assets, so
consumers never emit an `undefined` image URL. Django no longer needs to inject
seven copies of asset paths. This normalization adds no network requests or
per-feature processing. Unit tests cover defaults and overrides; browser tests
exercise the actual menu and dialog image requests. The public viewer does not
initialize private marker, measurement or editing workflows. Public zoom
restrictions and preference isolation remain enforced by the public root.

Dialog initialization belongs to the dialog instance: deferred `Modal.open`
callbacks run only while that same element remains mounted. Closing or replacing
a dialog cannot initialize a later instance with stale form data. Cylinder
close/backdrop listeners bind when the dialog opens, because the route can load
after `DOMContentLoaded`; loading, empty-fleet and error states remain
dismissible. Stable listener identities avoid duplicate handlers on reopening.
Unit tests cover these lifecycles, and browser icon checks also close the real
dialogs and reject uncaught page errors.

Mutable web marker data is held in a WeakMap keyed by the actual GeoJSON source.
`addOwnedSource` registers the input and mutation handlers retrieve the owned
collection before calling `setData`. No code reads the undocumented engine
`source._data`. Source replacement naturally invalidates ownership; removed
sources and their data can be garbage collected. Survey sources keep their
existing preparation caches and are not rebuilt by display toggles.

## Shared package CI gate

Before any app checks or dependency installation, `Shared Package CI` runs
`bun scripts/check-shared-package-ci.ts`. It verifies the full SHA pins for
`@speleodb/map-core` and `@speleodb/map-viewer` against their public OpenSpeleo
repositories and checks each repository's `.github/workflows/ci.yml` (`Verify`)
using the GitHub Actions API. Only a `push` run on that exact SHA counts; PR
merge runs and unrelated workflows cannot satisfy the gate.

Both commits must exist. A missing commit, API error, or completed run with any
conclusion other than `success` fails immediately. The newest workflow run is
selected by run ID, including its current rerun attempt. Queued/in-progress runs
and an absent run are polled every 30 seconds, with one shared 30-minute
deadline for both packages, including API time. Each request has at most 30
seconds to finish. Both packages are rechecked every round, so a rerun of a
previously green package is observed while the other is pending. No verification
result is cached between app runs. The job timeout is 32 minutes to allow
checkout/Bun setup; the verification script itself stops at 30 minutes.

All downstream CI jobs depend directly or transitively on this gate and are
skipped when it fails. The job uses the read-only `GITHUB_TOKEN` supplied by
Actions, including fork/Dependabot runs; no extra secret is required for these
public repositories. API/authentication/rate-limit errors fail closed. For local
verification, provide `GITHUB_TOKEN` with public-repository Actions read access;
unauthenticated polling can exhaust GitHub's lower rate limit before 30 minutes.

The small script uses only Bun built-ins and is kept in each standalone app:
loading a shared dependency to decide whether that dependency is safe to install
would make this bootstrap check circular. Keep both copies and their policy
aligned. Vitest exercises the actual checker with simulated GitHub responses and
a virtual clock, covering failure propagation, exact-SHA selection, reruns,
pagination and the shared deadline. Workflow contract tests verify downstream
dependencies. There is no application runtime or browser impact.

## Verification

The package suites test shared algorithms and expression/layer builders. Web
suites retain app policy, permission, persistence, scheduling and both real
composition roots. Provider normalization tests cover source identity, retina
sprites, glyph paths and credential boundaries; raster protocol tests cover
missing-data hashes, abort propagation and cache metadata. Existing marker
mutation tests verify source/record identity using registered app-owned data.

The Playwright fixture observes `speleo:map-created` and instruments the actual
imported MapLibre instance, intercepting provider data at the network boundary.
It retains real source updates, rendered features and engine workers. Private
and public scenarios cover basemap switching, source identity, tools, zoom
restrictions and responsiveness. Live provider verification additionally needs a
valid Mapbox token and provider network access; deterministic fixtures alone do
not establish live imagery and city-label availability.

Run checks inside the running application container from `/app`:

```sh
bun run typecheck
bun run lint:frontend
bun run test:frontend
bun run build
```

Standalone production builds consume immutable full-SHA revisions from
[SpeleoDB-TS-MapCore](https://github.com/OpenSpeleo/SpeleoDB-TS-MapCore) and
[SpeleoDB-TS-MapViewer](https://github.com/OpenSpeleo/SpeleoDB-TS-MapViewer).
The application manifest and Bun lock pin the exact revisions. The matching
`map-core` override ensures the viewer peer resolves to that same revision.
`bun run check:shared-packages` rejects local paths, floating Git branches and
inconsistent core overrides before standalone CI or Railway installs. Both Git
installs and monorepo development consume package TypeScript sources. Vite
compiles that code as part of the application build; no package installation
script or checked-in `dist/` is required. Type checking and ESLint use the same
source exports, and the runtime import audit follows their actual
implementation.

The `speleodb-source` condition remains enabled in every environment for
compatibility with the existing immutable Git pins, which already include
sources but still default to compiled exports. New package revisions export
source by default. Advance the application pins and locks only after those
revisions are published; the compatibility condition prevents that release
sequence from blocking source builds now.

The monorepo overlay links the same source and asset directories without
rewriting exports. `SPELEODB_LOCAL_PACKAGES=1` verifies that both packages came
from this overlay and rejects missing local packages. Canonical TypeScript, Vite
and Vitest resolution preserve installed symlink paths so shared sources resolve
dependencies from the application's installation. Package code stays independent
of Django and browser globals. See the monorepo TypeScript package documentation
for packaging, local overlays and publication sequencing.

The live renderer/provider smoke is opt-in. With a valid configured provider
token, run it through the Django browser wrapper so the ordinary isolated user
and view fixtures still own application data:

```sh
VIEWER_BROWSER_LIVE_PROVIDER=1 VIEWER_BROWSER_GREP='retained Mapbox imagery' \
  pytest tests/browser/test_django_browser.py -s -q
```

This smoke checks loaded imagery and composite sources, actual rendered vector
city-label features and visible provider attribution in Chromium and WebKit.
