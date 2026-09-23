# Private map display settings

## Intent and ownership

The private Survey Viewer separates authoring from display preferences. Its
toolbar contains four equal-width buttons: **Create Geometry**, **Import
GPX/KML**, **Managers**, and **Settings**. Import GPX/KML uses green, Managers
blue, and Settings purple, with matching hover/open states. The selected color
mode uses an indigo fill and white text so its state is immediately visible. All
manager rows share full-width hit areas and highlights; obsolete ID-specific
toolbar widths must not override their menu styling. Managers gives direct
access to Survey Stations, Surface Stations, and Landmarks; entity management is
separate from display preferences. Settings contains compact color controls and
marker visibility. Per-project and per-record panels remain on the map and own
record selection. Hiding a marker category never rewrites those selections.

Controls reflect changes immediately; map work follows a paint opportunity.
Close, Escape, and backdrop dismissal keep changes. Desktop uses a centered,
constrained dialog; phones use the viewport with a scrolling body and persistent
header/footer. Station types expand inline. A danger-styled Reset button sits
left of Close. Managers remain available even when their marker category is off.
The backdrop uses a dark scrim without blur: filtering the live WebGL canvas can
delay control frames even when application work yields before painting.

The public viewer retains its existing color/source controls. Shared rendering
supports both viewers, but public initialization does not load private display
preferences. The existing map-canvas source picker and its persistence remain
shared as before; map source is outside Settings.

## Preference model and lifecycle

`State.displayPreferences` is the backing object for `colorMode`, `categories`,
and `stationTypes`. Existing `Layers.colorMode` and `State.landmarksVisible`
accessors reference it. Defaults and presentation metadata live in
`DEFAULTS.DISPLAY`. Station types align with backend `SubSurfaceStationType`:
Sensor, Biology, Bones, Artifact, and Geology. Missing/null feature types retain
Sensor rendering; experiments remain station-detail records, not map markers.

`DisplayPreferences.init({persist: true})` restores validated, versioned browser
preferences before private layers load. Public initialization uses
`persist: false`, establishing defaults without reading private storage.
Map-data resets preserve preferences. Malformed fields use defaults; unavailable
storage leaves controls usable for the visit. Retired preference fields from the
earlier linework/overlay controls are ignored, so removed controls cannot leave
content hidden.

Display, project, network, and country preferences update in memory before any
storage write. `schedulePreferenceWrite()` coalesces each storage key until a
frame and a subsequent task; it serializes the newest value at write time.
Pending writes flush on `pagehide` and owner teardown. Country visibility and
accordion state hydrate once per panel initialization, so a delayed storage
write cannot change the country gate used by a concurrent project toggle or
newly loaded source. Display persistence is registered only on the private
route.

The private color selector offers **By Survey**, **By Depth**, and **By Shot**.
By Shot uses exported Ariane shot colors and generated Compass section colors,
with each feature falling back to its survey color when its color is absent or
invalid. This mode stays available for legacy or mixed data and persists like
the other modes. See [shot coloring](shot-coloring.md) for the rendering
contract. Depth controls and the depth legend appear only in By Depth.

All six marker categories and all five station types default on; color defaults
to By Survey. **Cave entrances** is the first visibility row and controls the
yellow stars from Point features in project GeoJSONs. Existing version-1 saved
preferences without this category keep entrances visible; other saved choices
are preserved. The preference remains local to the private viewer. Individual
GPS, GIS layer, and GIS geometry selections keep their existing session-off
defaults. Reset restores marker/type visibility and color defaults, preserving
map source, project, country, network, and item selections, cached data, and
camera position.

## Visibility composition

| Content                              | Required conditions                            |
| ------------------------------------ | ---------------------------------------------- |
| Survey lines and section labels      | Country + project                              |
| Cave entrance stars                  | Country + project + cave-entrances setting     |
| Survey stations and labels           | Country + project + stations setting + subtype |
| Surface stations and labels          | Network + surface-stations setting             |
| Exploration leads / safety cylinders | Existing project filter + category setting     |
| Landmarks and labels                 | Landmark setting                               |
| GPS tracks / GIS layers              | Item selection                                 |
| Saved GIS geometries                 | Item selection + editing suppression           |

Linework remains controlled by project selection. Existing zoom thresholds and
permissions still apply. Station parent off/on preserves subtype choices; it is
not a select-all checkbox. Hiding entrances leaves linework and section labels
visible, and showing them never reveals a project hidden by its individual or
country selection. The entrance gate is applied to the existing project point
layer, preserving its star appearance and zoom threshold without changing the
GeoJSON schema.

`Layers.setCategoryVisibility()`, `setStationTypeVisibility()`, and
`setColorMode()` apply the shared model. Settings and persistence subscribe to
`speleo:display-preferences-changed`. Color changes also emit
`speleo:color-mode-changed`. `applyDisplayPreferences()` reapplies current
values.

Creation, refresh, async completion, and style reconstruction must compose every
gate. Type switches filter the shared station-label layer as well as symbols.
Pending marker loads cannot bypass a category hidden while they were loading.

`Layers.applyProjectLayerVisibility()` composes the entrance category with the
effective project gate on creation and every project/country visibility change.
This keeps async loads, source refreshes, and reconstructed layers consistent.
Basemap changes preserve the existing overlay layout visibility. Entrance
switches do not recompute depth domains or change station settings.

## Navigation, managers, and fullscreen

Ordinary toggles retain global gates and never move the camera. Explicit Go to /
Show on map reveals the required category, subtype, and owning project/network
before navigating, waiting for queued display work to apply. One navigation
intent spans the project, GPS, GIS, station, and landmark controls. A newer
destination, hiding the target, a user camera gesture, or map teardown cancels
an older pending camera move. `ProjectPanel.revealProject()` owns country
reveal: opening a country can reveal its previously selected projects, but never
changes their individual preferences. GPS/GIS items keep their existing panel
behavior.

The Managers menu closes before launching a manager. Manager focus handling
suspends for details/child dialogs. Back uses an explicit manager callback, not
a hidden toolbar-button click. Close/Escape restore focus to Managers. Modal
keyboard input must not trigger the geometry editor's document-level shortcuts
behind it. Drafts remain intact when Settings or a manager opens; cancel
preserves preferences.

The private fullscreen host contains the same toolbar, map, and static overlays.
`getMapOverlayHost()` routes dynamic visual overlays there with a body fallback
outside this viewer. Download anchors keep their existing placement. This is a
container contract, not a rewrite of entity APIs.

## Extension, performance, and verification

Add category metadata/defaults in `DEFAULTS.DISPLAY`, compose its gate in the
renderer and lifecycle paths, and add regression coverage. Reuse Settings rows;
do not duplicate state or permission matrices. Document stable DOM hooks and
escape user/API values.

Category switches update tracked Mapbox layout/filter properties without record
fetches, bulk selection, GeoJSON reconstruction, style resets, or camera
movement. Individual selections retain lazy loading. Depth mode uses cached
project domains; marker visibility does not discard or rescan those domains.

The control handlers publish desired state before renderer work. GPS/GIS load
indicators and Settings' busy state describe pending work without disabling
visibility controls. A second click replaces the earlier choice. Panels patch
their existing rows, preserving focus and scroll position; metadata changes can
rebuild a list, and newly discovered GIS subtypes extend only their owning row.
Only current renderer failures produce an error; superseded operations do not
raise a failure notification. The source menu also selects and closes before its
queued raster/style changes, and removal cancels queued source work.

Run tests only in the existing application container. Cover real rendered
templates, persistence, visibility composition, late loads, public isolation,
manager focus, and editor keyboard isolation. Entrance regressions additionally
cover legacy preference restoration, data refresh/reconstruction, basemap
switching, project/country gate preservation, and unchanged linework/depth data.
Inspect the authenticated browser at 320/390px, tablet, desktop, short
landscape, fullscreen, 200% zoom, and reduced motion. Stop any watcher, build
cleanly, and verify manifest-matching served assets before final screenshots.
Check bounds/focus/network behavior as well as visuals; actual results live in
the task checklist.

Concurrency coverage must exercise the actual control handlers: reverse a switch
while its load is unresolved, change destination across panel types, hide a
pending destination, and replace/remove the map. Assert immediate checked state,
stable focused elements, newest final visibility, and absence of stale camera
moves. Persistence tests verify one write for a burst, pagehide flushing,
country-gate decisions before storage flush, and private/public isolation.
