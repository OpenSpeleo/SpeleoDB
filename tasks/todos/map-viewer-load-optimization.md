# Map Viewer Load Optimization

## Problem

A HAR capture (`map_viewer.har`) showed the private viewer spending ~42% of a
~10s load on pure preamble. The startup sequence chained blocking `await`s:

- The three independent startup APIs (`/projects/` 1456ms, `/surface-networks/`
  105ms, `/gps-tracks/` 139ms) ran one after another.
- `MapCore.init()` (Mapbox style/tiles) was blocked behind those awaits, only
  starting at ~2.1s despite needing none of that data.
- The all-projects GeoJSON metadata fetch (1602ms) only started inside the
  `map.on('load')` handler, at ~2.6s.
- The first project GeoJSON download did not begin until ~4.2s.
- Post-map phases (surface stations -> landmarks -> exploration leads ->
  cylinders -> GPS tracks) ran serially.

No N+1: `StationManager.loadStationsForProject` shares one cached fetch. The
problem was purely scheduling/parallelism, not logic.

## Plan

- [x] `main.js`: init map immediately; run `loadProjects`/`loadNetworks`/
      `loadGPSTracks` in parallel; prefetch GeoJSON metadata early
      (`configReady` / `metadataReady`).
- [x] `main.js` `loadMapData`: await `configReady`, consume in-flight
      `metadataReady`, overlap marker images with metadata, parallelize post-map
      layer phases with a single final `reorderLayers()`.
- [x] `gis_view_main.js`: prefetch `fetchPublicViewData()` concurrently with map
      init; consume inside the `map.on('load')` handler.
- [x] Add `preconnect`/`dns-prefetch` resource hints (api.mapbox.com,
      fonts.openmaptiles.org, services.arcgisonline.com) to both templates.
- [x] Extend `main.test.js` (map-init decoupling, parallel kickoff, metadata
      prefetch-once) and add a public prefetch test.
- [x] Update `docs/map-viewer/data-flow.md` + `architecture.md`.
- [x] Run JS tests, lint, and esbuild verification.

## Review

- No application logic changed. Same functions are called, same final rendered
  state, same final layer z-order. Only the timing/concurrency of requests
  changed.
- Private entrypoint: `MapCore.init()` runs first; `configReady` and
  `metadataReady` are kicked off immediately and consumed in `loadMapData`;
  marker images + metadata download concurrently; the six layer phases run as a
  single `Promise.all` followed by one authoritative `reorderLayers()`.
- Public entrypoint: the single GIS-View GeoJSON request is prefetched during
  init and consumed in the load handler (swap-to-null so a failed prefetch or a
  later reload re-fetches fresh, matching prior behavior).
- Invariants preserved: markers ready before layers; single final reorder; no
  refetch on non-destructive source change; no unhandled rejections (config and
  metadata loaders catch internally, public prefetch attaches a no-op `.catch()`
  with real handling on consume).
- Expected result: map style download ~2.1s -> ~0.4s; first project GeoJSON
  ~4.2s -> ~2.0s; post-map phases overlap instead of serializing.

## Verification

- `npm run test:js` (44 files, 906 tests passed)
- `npm run lint:js` (clean)
- esbuild bundle verification for both `main.js` and `gis_view_main.js` (built
  to a temp path; `dist/` is gitignored and produced at deploy time).

## Environment note

The local `node_modules` shipped Linux-platform native binaries for `rolldown`
(vitest) and `esbuild`. `npm install` restored the correct darwin-arm64 binding
for rolldown; the darwin esbuild binary was installed separately for local
bundle verification. No tracked files (`package.json` / `package-lock.json`)
were changed by this.
