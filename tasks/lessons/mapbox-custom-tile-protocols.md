# Raster Tile Response Checks

Do not assume a main-thread `fetch` wrapper proves Mapbox raster tiles are
checked. Tile requests may happen through Mapbox workers or image-loading paths.
Do not model known missing tile image hashes as a per-provider opt-in unless the
product explicitly asks for that; SpeleoDB's missing tile hash list is global
and applies to every configured raster tile source.

Do not point a Mapbox raster source at a custom scheme unless the exact runtime
loaded by the templates exposes and accepts that protocol API. The Mapbox CDN
builds inspected for this task (`v3.12.0` and `v3.24.0`) did not expose
`addProtocol`, so a `speleo-checked-tile://...` template made ESRI Satellite
stop rendering. In that runtime, keep the raw provider URL.

If a future runtime exposes a documented custom protocol API, install the
protocol before constructing the map and make the source tile template use it
only after successful installation. The protocol handler must decode the real
provider URL, fetch that normal URL, inspect the image bytes, and report an
error for known bad tiles before Mapbox receives the image. Keep any `fetch`
wrapper as a fallback only; it is not proof that Mapbox raster tiles are
checked.

Tests for checked raster sources must assert:

- the generated tile template falls back to the raw provider URL when checked
  protocol support is unavailable;
- the template still contains literal `{z}/{y}/{x}`;
- any checked protocol template is used only after protocol installation;
- the protocol handler fetches the decoded raw provider URL;
- JavaScript returns an error for known missing-data hashes before passing data
  to Mapbox.
