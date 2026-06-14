# Lesson: the `MAP_SOURCES` registry order is a tested contract

## Context

`MAP_SOURCES` in
`frontend_private/static/private/js/map_viewer/config.js` is a frozen, ordered
registry. Its order is not cosmetic:

- It is the order rendered in the in-map Map Source selector.
- It drives the tokenless default. `MapSources.getFirstUsableSource()` /
  `getCurrentMapSourceId('')` return the **first** entry whose token
  requirement is satisfied. With no Mapbox token, the first non-token source
  wins.

## What went wrong

The registry was reordered (ESRI Satellite moved ahead of the hillshade
sources) without updating `sources.test.js`. Two tests then failed:

- the tokenless default expectation, and
- the `getAvailableMapSources('')` order array.

The generated `dist` bundles were also stale and contained none of the feature,
so a green-looking local app could still ship the wrong behavior.

## Rule

When you change the order or membership of `MAP_SOURCES`:

1. Update the order-sensitive expectations in
   `frontend_private/static/private/js/map_viewer/map/sources.test.js`
   (tokenless default id and the available-sources order array) in the same
   change.
2. Remember that the first token-satisfied entry becomes the tokenless default
   base map; confirm that is the intended default.
3. Update `docs/map-viewer/features.md` so the documented source list matches
   the in-menu order.
4. Rebuild the bundles (`npm run build:esbuild:private` and
   `:public`) and grep them to confirm the feature and order actually shipped —
   `dist/*.bundle.js` are gitignored and can silently go stale.
