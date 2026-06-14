# Map Source Selector

## Plan

- [x] Add a shared map source registry and source helper module.
- [x] Add shared in-map Map Source UI control.
- [x] Wire private and public viewers to initialize and reload from shared map source behavior.
- [x] Add focused JavaScript tests for registry, control, and public entrypoint wiring.
- [x] Update map viewer documentation.
- [x] Run JavaScript lint, tests, and esbuild verification.
- [x] Re-review for non-destructive source switching regressions.

## Review

- Added shared `MAP_SOURCES` registry and `MapSources` helper for source selection, persistence, token filtering, raster style generation, and the in-map control.
- Added `ESRI - Satellite` as a tokenless raster source using the ESRI World Imagery tile endpoint with provider `maxzoom: 18`.
- Added a reusable global missing-tile SHA-256 list for every configured raster source; `9eafd300d61393184a4abc1d458564cfd1cd9b6f9c4e9c74687045c0a0e5b858` is treated as a tile failure when matching raster tile requests pass through browser JavaScript that can inspect response bytes.
- Removed the Python checked-tile proxy and the root service-worker workaround. The Mapbox CDN builds currently loaded by SpeleoDB do not expose a documented custom tile protocol API, so ESRI raster sources keep their normal provider URLs to preserve rendering. `MapCore.init()` installs a main-thread `fetch` wrapper fallback before map construction.
- Wired private and public viewers to initialize from the selected source and ignore non-destructive ESRI source-change events.
- Corrected the UI to render as a true Mapbox GL control via `map.addControl(..., 'top-right')`, matching navigation/fullscreen controls.
- Corrected source switching so ESRI sources replace a single base raster layer below overlays instead of calling `map.setStyle()` and clearing survey layers.
- Set ESRI hillshade raster provider `maxzoom` to 16 after Mexico tile inspection showed zooms 1-16 are good and zoom 17 returns unavailable-data imagery; the map still zooms beyond 16 by overzooming source tiles.
- Hardened the compact radio popover with outside-click close, Escape close, radio-group semantics, and mobile overflow limits.
- Added focused JS coverage for source behavior, `MapCore`, and public source-change reloads.
- Strengthened tests so the source selector must use the Mapbox control API and render through `onAdd()`.
- Strengthened tests so ESRI source changes must not call `setStyle()`, must hide only Mapbox base layers, must preserve SpeleoDB overlays, must insert the raster layer before overlays, and must ignore `reloadRequired: false` in both entrypoints.
- Documented the trusted-static SVG `innerHTML` boundary and added a lesson for avoiding `setStyle()` when overlays must survive.
- Verification passed:
  - `npm run lint:js`
  - `npm run test:js` (44 files, 897 tests)
  - `npm run build:esbuild:private`
  - `npm run build:esbuild:public`
  - `git diff --check`
- Additional verification for the checked tile hash path:
  - focused JS tests cover the ESRI raw provider URL fallback, optional checked-protocol behavior only when such support is actually installed, and JavaScript rejecting the known missing image hash for multiple configured raster sources.

## Adversarial Re-Review (2026-06-14)

Findings and resolutions:

- **Source order changed and tests went stale.** The working tree `MAP_SOURCES`
  order was changed to `mapbox-satellite, esri-satellite, esri-world-hillshade,
  esri-world-hillshade-dark`. This is the intended order (kept on request). Two
  `sources.test.js` expectations still asserted the old order and failed:
  tokenless default and the available-sources order array. Updated both to the
  kept order. **Consequence:** the tokenless default base map is now
  `ESRI - Satellite` (was `ESRI - World Hillshade`). Reordered the
  `features.md` source list to match the in-menu order.
- **Stale generated bundles.** Both `dist` bundles contained none of the Map
  Source feature (no `arcgisonline` / `speleo-base-raster` / `Map Source`
  strings) despite recent mtimes. Rebuilt both; verified each now contains the
  feature with `esri-satellite` preceding the hillshade ids. Bundles are
  gitignored, so this is a local-artifact refresh, not a committed artifact.
- **Icon SVG fill.** `MAP_SOURCE_ICON_SVG` hardcoded `fill="#000000"`, which
  made the `.map-source-button { color }` CSS inert. Switched to
  `currentColor` so the icon follows the control's text color. Still trusted
  static markup; no user/API data in that `innerHTML` path.

Verified correct, no change needed:

- Control installs via `map.addControl(control, 'top-right')` with a dedup
  guard and `onRemove` listener cleanup.
- ESRI switches never call `map.setStyle()`; they replace a single
  `speleo-base-raster-layer` inserted before the first SpeleoDB overlay.
- `OVERLAY_LAYER_PREFIXES` covers every real overlay layer id in `layers.js`,
  so `hideBaseStyleLayers()` hides only Mapbox base layers and never overlays
  or the raster; original visibility is stored and restored.
- `reorderLayers()` moves overlays to the top (no `beforeId`), so overlays can
  never fall below the ESRI raster.
- Switching back to Mapbox removes the raster source/layer and restores hidden
  base layers; camera is preserved (no `setStyle`/`flyTo`).
- Both entrypoints share the implementation and early-return on
  `reloadRequired: false`; no duplicated provider logic.
- Token present keeps Mapbox default; tokenless filters the token-required
  source out; `localStorage` reads/writes are guarded.
- The Python tile proxy and root service-worker workaround are absent; no
  `map_tile` / `serviceWorker` references remain outside `dist`.

Residual risks (honest limitations):

- Pre-render hash rejection is best-effort only. Mapbox-internal raster loads
  bypass `window.fetch` and the loaded Mapbox CDN builds expose no documented
  `addProtocol`, so known missing-data tiles can still render. Documented in
  `architecture.md` / `features.md`.
- The destructive `clearRenderedMapState()` + reload path in both entrypoints
  is currently unreachable (events always carry `reloadRequired: false`); kept
  as defensive future-proofing.
- The global `.mapboxgl-ctrl-attrib` override restyles Mapbox attribution too
  (intentional, for high-contrast bordered attribution).
- `config.js` was left as `MM`: the git index still holds the old source order
  while the working tree holds the kept order. Staging was intentionally not
  touched; re-stage `config.js` to align the index.

Re-verification:

- `npm run lint:js` — pass.
- `npm run test:js` — 44 files, 902 tests, all pass.
- `npm run build:esbuild:private` / `:public` — both built; feature present in
  kept order.
- `git diff --check` — clean.
