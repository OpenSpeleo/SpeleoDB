# Shared map packages and MapLibre integration

The web and mobile viewers consume two SpeleoDB packages. `@speleodb/map-core`
owns portable geometry, depth, bounds, visibility and unit algorithms.
`@speleodb/map-viewer` owns MapLibre style expressions, layer specifications,
marker artwork, globe atmosphere, paint/update scheduling, camera-intent
ownership, globe-style normalization and visible-rectangle camera padding. App
code owns backend transport, permissions, persistence, scheduling budgets,
interaction policy, instance lifecycle and provider selection. These are
SpeleoDB libraries, not a generic map framework.

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

Web, mobile and map-viewer use the
[`DEKHTIARJonathan/maplibre-gl-js` hotpatch fork](https://github.com/DEKHTIARJonathan/maplibre-gl-js/tree/hotpatch),
based on MapLibre 6.14.0. Map-core remains renderer-independent. The fork owns
the engine source and distributable build, including the partial-pinch handoff
correction
([upstream issue #8809](https://github.com/maplibre/maplibre-gl-js/issues/8809)).
Ending a pinch with one finger still held can start zoom inertia; when that
animation naturally ends, upstream camera cleanup resets the held touch handler.
The next movement is then ignored until another touch starts. The fork prevents
end inertia while the touch-pan handler retains a contact and clears its
obsolete velocity samples. Normal `moveend` cleanup still runs, and full finger
release retains ordinary inertia.

The fork also synchronizes the requested camera's projection transition state
with the live camera during render
([upstream issue #8808](https://github.com/maplibre/maplibre-gl-js/issues/8808)).
A `transformCameraUpdate` callback, including React map wrappers, can keep a
requested camera whose globe/Mercator blend otherwise becomes stale while
zooming. Web currently uses the engine directly, but shares this correction so
the engine's behavior stays consistent across consumers. MapLibre 6.11.1 already
fixed movement-event delivery through the camera; 6.14.0 uses that upstream
cleanup without a local event correction.

The application declares `github:DEKHTIARJonathan/maplibre-gl-js#hotpatch`; its
frozen lock selects an exact fork revision containing the distributable build.
Vite bundles the installed engine normally; web and shared packages do not
rewrite engine files during installation or build. Both corrections live beside
MapLibre's own unit tests, while shared test helpers and the private/public
browser suites retain application-level gesture coverage. No per-frame
application callback or GeoJSON traversal is added. Engine upgrades, including a
return to upstream once it contains both fixes, must pass those mouse and touch
regressions.

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

Bounded GeoJSON tree transport is imported directly from
`@speleodb/map-core/geojson-transport`. The module worker and main-thread reader
share that implementation and its message types; web retains parse thresholds,
worker lifecycle, scheduling and sanitized errors. Its portable round-trip,
prototype-preservation and huge-coordinate-array tests live in map-core.

Endpoint snapping calls `findNearestGeographicCandidate` from map-core through
one web adapter that filters visible projects and keeps their original endpoint
arrays. Web retains project ownership, configured distance/radius and the two
public result shapes. Stable ties and zero-distance early exit belong to the
shared selection algorithm. Hover, click, drag and context-menu hit rectangles
use the existing map-viewer `hitQueryBounds`; radii and event dispatch stay web
policy. Shared types are imported from their package subpaths directly.

The `viewer_updates.ts` adapter creates the web-owned queue with a callback to
`DEFAULTS.VIEWER_WORK.BUDGET_MS`. The shared scheduler preserves a separate
two-frame and future-task paint boundary for every job, keyed coalescing,
cooperative yielding and teardown cancellation. Web does not set the mobile
WebView fallback deadline. Network work remains outside the queue.

The `map/navigation_intent.ts` adapter owns one shared navigation controller for
the current web viewer. All entity controllers compete for its latest intent;
user-originated `movestart` events and map replacement invalidate deferred
camera work. Teardown removes the gesture subscription. Visibility, permissions
and entity-specific camera destinations remain in the web controllers.

Provider style transforms call `normalizeGlobeStyle`; the shared helper strips
provider camera metadata while retaining source/layer identity and cache URLs.
`geometryCameraPadding` supplies the web padding cap and margin ratio to shared
`computeCameraPadding`. Web retains visual-viewport measurements, panel and
editor selectors, dateline handling and transient north-up `fitBounds` options.
The shared rectangle algorithm uses ordered greedy cuts, preserves the previous
region when an obstacle fully covers it, and returns the configured numeric
fallback for an empty visible intersection.

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

## Verification

The package suites test shared algorithms, scheduling and cancellation, camera
intent using actual MapLibre events, style identity and rectangle fitting as
well as expression/layer builders. Web suites retain singleton ownership,
configuration, app policy, permissions, persistence and both real composition
roots. Provider normalization tests cover source identity, retina sprites, glyph
paths and credential boundaries; raster protocol tests cover missing-data
hashes, abort propagation and cache metadata. Existing marker mutation tests
verify source/record identity using registered app-owned data.

The Playwright fixture observes `speleo:map-created` and actual rendered output
without replacing MapLibre methods, and intercepts provider data at the network
boundary. Small deterministic fixtures retain real rendering and native input.
Private and public UI/UX scenarios cover basemap switching, visible attribution,
tools, zoom restrictions, loading feedback and error recovery. Source identity,
worker behavior and processing belong in the suites run by `make test`. Live
provider verification additionally needs a valid Mapbox token and provider
network access; deterministic fixtures alone do not establish live imagery and
city-label availability.

Run checks inside the running application container from `/app`:

```sh
bun run typecheck
bun run lint:frontend
bun run test:frontend
bun run build
```

Standalone production builds consume exact npm releases of
[`@speleodb/map-core`](https://www.npmjs.com/package/@speleodb/map-core) and
[`@speleodb/map-viewer`](https://www.npmjs.com/package/@speleodb/map-viewer).
The application manifest and Bun lock pin their versions and archive integrity.
The matching `map-core` override keeps the viewer's compatible core dependency
on the same installed version. `bun run check:shared-packages` rejects local
paths, Git dependencies, version ranges and inconsistent core overrides before
standalone CI or Railway installs. Both npm installs and monorepo development
consume package TypeScript sources. Vite compiles that code as part of the
application build; no package installation script or checked-in `dist/` is
required. Type checking and ESLint use the same source exports, and the runtime
import audit follows their implementation.

The `speleodb-source` condition remains enabled for compatibility with older
source-enabled package revisions; npm releases export source by default.

The monorepo overlay links the same source and asset directories without
rewriting exports. Its installer owns validation of local source links. Web's
Vite and Vitest configuration consumes ordinary package exports without
requiring monorepo metadata, environment flags, or sibling repositories, so
standalone npm installs and native workspace links both work. Canonical
TypeScript, Vite and Vitest resolution preserve installed symlink paths so
shared sources resolve dependencies from the application's installation. Package
code stays independent of Django and application globals; browser scheduling
uses explicit cancellable ports and detects animation-frame availability. See
the monorepo TypeScript package documentation for packaging, local overlays and
publication sequencing.

The live renderer/provider smoke is opt-in. With a valid configured provider
token, run it through the Django browser wrapper so the ordinary isolated user
and view fixtures still own application data:

```sh
VIEWER_BROWSER_LIVE_PROVIDER=1 VIEWER_BROWSER_GREP='retained Mapbox imagery' \
  pytest tests/browser/test_django_browser.py -s -q
```

This smoke checks loaded imagery and composite sources, actual rendered vector
city-label features and visible provider attribution in Chromium and WebKit.
