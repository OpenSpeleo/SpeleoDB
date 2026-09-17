# Private map display settings

## Intent and ownership

The private Survey Viewer separates authoring from display preferences. Its
toolbar contains four equal-width buttons: **Create Geometry**, **Import GPS**,
**Managers**, and **Settings**. Import GPS uses green, Managers blue, and
Settings purple, with matching hover/open states. The selected color mode uses
an indigo fill and white text so its state is immediately visible. All manager
rows share full-width hit areas and highlights; obsolete ID-specific toolbar
widths must not override their menu styling. Managers gives direct access to
Survey Stations, Surface Stations, and Landmarks; entity management is separate
from display preferences. Settings contains compact color controls and marker
visibility. Per-project and per-record panels remain on the map and own record
selection. Hiding a marker category never rewrites those selections.

Changes apply immediately. Close, Escape, and backdrop dismissal keep changes.
Desktop uses a centered, constrained dialog; phones use the viewport with a
scrolling body and persistent header/footer. Station types expand inline. A
danger-styled Reset button sits left of Close. Managers remain available even
when their marker category is off.

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

All five marker categories/types default on; color defaults to By Survey.
Individual GPS, GIS layer, and GIS geometry selections keep their existing
session-off defaults. Reset restores marker/type visibility and color defaults,
preserving map source, project, country, network, and item selections, cached
data, and camera position.

## Visibility composition

| Content                                      | Required conditions                            |
| -------------------------------------------- | ---------------------------------------------- |
| Survey lines, section labels, entrance stars | Country + project                              |
| Survey stations and labels                   | Country + project + stations setting + subtype |
| Surface stations and labels                  | Network + surface-stations setting             |
| Exploration leads / safety cylinders         | Existing project filter + category setting     |
| Landmarks and labels                         | Landmark setting                               |
| GPS tracks / GIS layers                      | Item selection                                 |
| Saved GIS geometries                         | Item selection + editing suppression           |

Linework remains controlled by project selection. Existing zoom thresholds and
permissions still apply. Station parent off/on preserves subtype choices; it is
not a select-all checkbox.

`Layers.setCategoryVisibility()`, `setStationTypeVisibility()`, and
`setColorMode()` apply the shared model. Settings and persistence subscribe to
`speleo:display-preferences-changed`. Color changes also emit
`speleo:color-mode-changed`. `applyDisplayPreferences()` reapplies current
values.

Creation, refresh, async completion, and style reconstruction must compose every
gate. Type switches filter the shared station-label layer as well as symbols.
Pending marker loads cannot bypass a category hidden while they were loading.

## Navigation, managers, and fullscreen

Ordinary toggles retain global gates and never move the camera. Explicit Go to /
Show on map reveals the required category, subtype, and owning project/network
before navigating. `ProjectPanel.revealProject()` owns country reveal: opening a
country can reveal its previously selected projects, but never changes their
individual preferences. GPS/GIS items keep their existing panel behavior.

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

Run tests only in the existing application container. Cover real rendered
templates, persistence, visibility composition, late loads, public isolation,
manager focus, and editor keyboard isolation. Inspect the authenticated browser
at 320/390px, tablet, desktop, short landscape, fullscreen, 200% zoom, and
reduced motion. Stop any watcher, build cleanly, and verify manifest-matching
served assets before final screenshots. Check bounds/focus/network behavior as
well as visuals; actual results live in the task checklist.
