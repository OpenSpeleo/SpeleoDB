# Map Viewer Refactor Plan (multi-iteration, exhaustive)

## Scope and goals

- **Primary scope**: `frontend_private/templates/pages/map_viewer.html` (≈9300 lines) containing inline CSS and a massive inline `<script>` with many responsibilities.
- **Goals**:
  - Extract CSS to `static/private/css/map_viewer.css`.
  - Split JS into coherent modules under `static/private/js/map_viewer/`.
  - Separate concerns:
    - Map core (Mapbox GL initialization, controls, base styles/filters)
    - GeoJSON visualization (load by project, style, color modes, altitude fix)
    - Stations (markers, CRUD, drag, snapping, manager/modal)
    - POIs (markers, CRUD, drag, confirmation, manager/modal)
    - Resources for stations (previews, add/edit/delete, viewers)
    - UI layer (context menu, tabs, modals, notifications)
    - API client (fetch, auth/CSRF, endpoints)
    - State and events (central store, decouple globals)
  - Preserve existing behaviors; reduce duplication and complexity.
  - Enable reuse to build a public viewer page for a single GeoJSON at a given commit (no stations/POIs/resources).

## Current-state summary (from code scan)

- Inline `<style>` at top; numerous classes for stations/resources/POIs/modals.
- External `poi_functions.js` already referenced (may be legacy/overlapping).
- All logic for:
  - Access control helpers `hasProjectWriteAccess`, `hasProjectAdminAccess`.
  - CSRF handling, notification system, overlays.
  - Context menu handling for map clicks, stations, and POIs.
  - Magnetic snap logic and distance calculations.
  - Stations: load/display per project, CRUD flows, drag/move with confirmation, station manager modal, station modal with tabs.
  - Resources: previews for photo/video/sketch/note/document, add/edit/delete flows, viewers and modals, sketch canvas tools and undo/redo.
  - POIs: separate CRUD, drag/confirm modal, listings modal.
  - Map: Mapbox GL init, layer filtering/toggles, color modes for line features, geojson loading per project with refresh, altitude-zero processing, bounds/fit logic.
  - Numerous globals: `stationMarkers`, `allStations`, `allPOIs`, `currentProjectId`, `projectLayerStates`, `map`, etc.

## Target architecture

- `static/private/css/map_viewer.css` — consolidated styles from inline `<style>`.
- `static/private/js/map_viewer/`
  - `index.js` — bootstraps page; wires modules; minimal glue.
  - `mapCore.js` — map creation, controls, height, base filters (hide roads/poi if desired).
  - `geojsonLayer.js` — project-geojson fetching, refresh, source/layer management, color modes, altitude-zero transform.
  - `stations.js` — markers, CRUD APIs integration, drag/snap, manager modal, station modal tabs routing.
  - `resources.js` — resource previews, add/edit/delete, viewers (photo/video/note), sketch tool.
  - `pois.js` — POI markers, CRUD, drag confirm, manager modal.
  - `ui.js` — context menu, tabs, modals, notifications, overlays, lightboxes.
  - `api.js` — CSRF-aware fetch wrapper; typed endpoints: projects, stations, POIs, resources.
  - `state.js` — central store (projects visibility, current station/poi, map ref); event bus/pub-sub.
  - `utils.js` — small helpers (distance, formatting, deep copy, DOM helpers).
- Public viewer reuse: `static/public/js/geojson_viewer/`
  - `index.js` uses `mapCore` and `geojsonLayer` to render a single GeoJSON at commit without stations/POIs/resources.

## Step-by-step execution plan (fine-grained)

1) Create directories and placeholders

- Create `static/private/css/map_viewer.css` (empty initially).
- Create `static/private/js/map_viewer/` with stub files listed above.
- Ensure static collection paths correct with Django `{% static %}`.

2) Inventory inline CSS

- Extract all CSS blocks related to:
  - Station markers `.station-marker` (+ modifiers like `.has-resources`)
  - Resource grid/cards/thumbnails `.resource-grid`, `.resource-card`, `.resource-preview`, etc.
  - POI markers `.poi-marker`.
  - Modals: station manager, station modal, drag confirm, resource delete confirm.
  - Context menu styles and notifications/overlays.
- Move rules verbatim to `map_viewer.css`, preserving cascade and specificity.
- Add comment anchors dividing sections.

3) Replace inline `<style>` with link tag

- In `map_viewer.html`, remove `<style>` contents; add:
  - `<link rel="stylesheet" href="{% static 'private/css/map_viewer.css' %}">`
- Validate styles load visually.

4) Inventory globals and top-level data flows

- Collect all global `let/const` and functions.
- Assign each to a target module (mapCore, geojsonLayer, stations, pois, resources, ui, api, state, utils).
- For each function, note its dependencies (map instance, state, DOM IDs).

5) Implement `api.js`

- CSRF token getter.
- `apiFetch(path, options)` wrapper: sets headers, JSON parsing, errors.
- Endpoints:
  - projects: list, geojson (latest/commit), toggle visibility.
  - stations: list per project, create/update/delete.
  - resources: list/create/update/delete, upload support.
  - pois: list/create/update/delete.

6) Implement `state.js`

- Store structure:
  - `map` reference; `projectVisibility` map; `currentProjectId`.
  - `allStations` Map; `stationMarkers` Map; station drag state.
  - `allPOIs` Map; `poiMarkers` Map; poi drag state.
  - UI selections: `currentStationId`, active tab, modals open.
- Event bus:
  - `on(event, handler)` / `emit(event, payload)`.
  - Core events: map-ready, project-geojson-loaded, station-updated, poi-updated, resource-updated, ui-open/close.

7) Implement `mapCore.js`

- Initialize Mapbox map; set height logic; controls; base style filter (hide roads/poi labels for clarity).
- Expose: `createMap(containerId, options)`, `getMap()`, `fitBounds(bounds)`.
- Emit `map-ready` when done.

8) Implement `geojsonLayer.js`

- Fetch geojson per project with refresh fallback.
- Process altitude to zero for LineString/Polygon rings.
- Add/update source and layers; support color modes with functions:
  - computeLineColorPaint, parseDepthValue, getFeatureSectionName, getFeatureDepthValue, setColorMode.
- Expose: `loadProjectGeojson(projectId)`, `toggleProjectVisibility(projectId, visible)`, `setColorMode(mode)`.
- Emit: `project-geojson-loaded`, `project-visibility-changed`.

9) Implement `ui.js`

- Notifications; loading overlays; context menu open/close (map/station/poi variants).
- Tabs switching; modal open/close for station manager, station details, drag confirm, resource delete, poi modals.
- Keep DOM IDs stable; expose functions used by other modules.

10) Implement `stations.js`

- Display stations from API per project; create markers; add drag with snapping; context menus; CRUD flows.
- Integrate station manager modal and station modal tabs; call `resources` for previews within.
- Use `state` for station maps; emit `station-updated`, `station-selected`.

11) Implement `resources.js`

- Resource previews per type; add/edit/delete forms and flows; viewers (photo/video/note) and sketch canvas with undo/redo.
- Use `api` for uploads; use `ui` for modals; emit `resource-updated`.

12) Implement `pois.js`

- Similar to stations but separate data and modals; drag confirm flow; listing modal.

13) Wire modules in `index.js`

- Create map with `mapCore`.
- On `map-ready`, load visible projects via `geojsonLayer` and then stations/pois as required.
- Register UI event handlers and keyboard shortcuts.
- Expose minimal global `window` hooks only if template bindings require it; otherwise convert inline handlers to delegations.

14) Template refactor

- Replace big inline `<script>` with `<script type="module" src="{% static 'private/js/map_viewer/index.js' %}"></script>`.
- Remove or adapt `poi_functions.js` if superseded.
- Keep data attributes/IDs for now to minimize template change. Convert inline `onclick` to event listeners progressively.

15) Build public viewer

- New template: `frontend_public/templates/pages/geojson_viewer.html`.
- New assets: `static/public/js/geojson_viewer/index.js` using `mapCore` + `geojsonLayer` only.
- Accept URL params: project, commit or file id; load only that GeoJSON; hide stations/POIs/resources UI and context menus.

16) QA & acceptance

- Manual test plan covering: map loads, project toggle, color modes, snapping, station CRUD, resource previews and editing, poi flows, modals, context menus, keyboard shortcuts.
- Performance checks; console errors; network failures resilience.

---

## Iterative refinement (15+ iterations)

### Iteration 1 — Module cut-lines and ownership

- Validate function-to-module mapping to avoid cross-dependencies.
- Decide: snap logic in `stations` vs `utils`? Move reusable math to `utils`; snap orchestration in `stations`.

### Iteration 2 — State boundaries

- Clarify who owns `currentProjectId`: UI selects; `state` stores; modules read.
- Consolidate station/poi collections: use `state` Maps only; modules never keep hidden copies.

### Iteration 3 — Events taxonomy

- Define event names and payload shapes; document in `state.js` header.
- Ensure no circular event chains; avoid "echo" updates.

### Iteration 4 — CSS organization

- Use sections: Base, Map, Modals, Stations, Resources, POIs, ContextMenu, Notifications.
- Preserve specificity; avoid unintended regressions.

### Iteration 5 — API surface stability

- Keep endpoint URLs as-is; wrap in `api` to ease later changes.
- Upload handling uses `FormData` and CSRF in wrapper.

### Iteration 6 — Template binding strategy

- Replace inline `onclick` with delegated events gradually.
- Expose minimal globals during transition: e.g., `window.goToStation`, `window.openPhotoLightbox` routed to modules.

### Iteration 7 — Error handling

- Standardize notifications for API errors; centralize in `ui.notify` called by modules.
- Use try/catch within modules and rethrow only when necessary.

### Iteration 8 — GeoJSON styling and color mode

- Extract color computation helpers; support future modes via `setColorMode`.
- Ensure altitude-zero processing is idempotent and deep-copies input.

### Iteration 9 — Drag and snap UX

- Maintain overlays and confirm dialogs in `ui`; stations/pois call into `ui` for prompts; `state` keeps drag temp data.

### Iteration 10 — Modals and tabs

- Consolidate modal open/close; avoid direct DOM queries sprinkled across modules.
- Provide functions like `ui.openStationModal(stationId, tab)`.

### Iteration 11 — Resource viewers

- Abstract lightbox/video modal creation; sanitize inputs; close on ESC/backdrop.

### Iteration 12 — Performance and memory

- Clean up markers on visibility toggle; de-register events on modal close.
- Debounce map resize/height and expensive refreshes.

### Iteration 13 — Testing hooks

- Expose debug toggles behind `window.__DEBUG__` for dev only; console summaries for loaded layers.

### Iteration 14 — Public viewer constraints

- Make `geojsonLayer` accept config to hide interactivity; prevent context menu; hide extra layers.
- Public `index.js` keeps only essential map controls.

### Iteration 15 — Documentation and comments

- Top-of-file docs in each module listing responsibilities, public API, events.
- README section in this file for quick start and dev notes.

### Iteration 16 — Accessibility pass

- Ensure modals/tabs keyboard-nav and ARIA where feasible.

### Iteration 17 — Security review

- Confirm CSRF applied; validate user inputs; guard against XSS in HTML insertions.

### Iteration 18 — Dependency cleanup

- Remove legacy `poi_functions.js` if redundant; or wrap into `pois` module.

### Iteration 19 — Rollout plan

- Behind a feature flag in template: switch to modular assets; fallback to legacy if needed initially.

---

## Acceptance checklist (condensed)

- CSS fully externalized; no inline styles left except necessary dynamic ones.
- Page loads with external JS modules; all major features intact.
- Public viewer page works with single GeoJSON@commit and no stations/POIs/resources.
- No console errors; network failures handled gracefully.
- Readability and maintainability improved: no giant function blob; minimal globals.

## Ultra-detailed step-by-step action plan (with verifications)

This section breaks work into atomic, verifiable steps. After each step, we pause for review before proceeding.

### Phase 0 — Preparation

0.1) Create directories (no code changes)

- Create `static/private/css/` if missing.
- Create `static/private/js/map_viewer/`.
- Create `static/public/js/geojson_viewer/`.
- Verify: directories exist; no template changes yet.

0.2) Baseline snapshot

- Open browser console while on `map_viewer.html`; record current console warnings/errors.
- Note approximate time-to-interactive and key flows that must keep working.
- Verify: we have a written baseline to compare regressions.

0.3) Identify critical DOM anchors and IDs

- Catalog IDs used by JS: `station-manager-modal`, `station-modal`, `poi-manager-modal`, `poi-drag-confirm-modal`, context menu containers, tab button selectors, canvas IDs for sketches.
- Verify: list compiled for ref usage; no changes yet.

### Phase 1 — CSS extraction (safe, no-JS move)

1.1) Extract inline CSS to `static/private/css/map_viewer.css`

- Copy all rules from `<style>` block to the new file, in sections:
  - Base and layout (overlays, general typography/spacing if any)
  - Map and height (`setMapHeight` related container sizing)
  - Stations (`.station-marker`, modifiers like `.has-resources`)
  - Resources (grids, cards, preview thumbnails, hover effects)
  - POIs (`.poi-marker`)
  - Context menu
  - Modals (station manager, station details, drag confirms, delete confirms)
  - Notifications/overlays/spinners
- Preserve order and specificity; do not change selectors.
- Verify: no lint errors; file saved.

1.2) Replace inline `<style>` with `<link>`

- In `frontend_private/templates/pages/map_viewer.html`, remove the whole `<style> ... </style>` block.
- Add `<link rel="stylesheet" href="{% static 'private/css/map_viewer.css' %}">` near other CSS links.
- Verify (manual): refresh page; visuals match baseline; no missing styles. If regression, fix ordering/specificity in CSS file.

### Phase 2 — JS scaffolding and minimal boot

2.1) Create module stubs

- Files with exported placeholders only:
  - `static/private/js/map_viewer/index.js`
  - `static/private/js/map_viewer/mapCore.js`
  - `static/private/js/map_viewer/geojsonLayer.js`
  - `static/private/js/map_viewer/stations.js`
  - `static/private/js/map_viewer/resources.js`
  - `static/private/js/map_viewer/pois.js`
  - `static/private/js/map_viewer/ui.js`
  - `static/private/js/map_viewer/api.js`
  - `static/private/js/map_viewer/state.js`
  - `static/private/js/map_viewer/utils.js`
- Verify: each file exports at least one named function (even if stub) to ensure ES module loading works.

2.2) Switch template to module loader (behind feature flag)

- Add at bottom of `map_viewer.html`, above existing inline `<script>`:
  - `<script type="module" src="{% static 'private/js/map_viewer/index.js' %}"></script>`
- Keep legacy inline script intact for now.
- In `index.js`, only log a message to confirm load.
- Verify: page loads, no module import errors in console.

2.3) Optional feature flag

- Wrap new `<script type="module">` tag in a Django feature flag if available to allow quick rollback; else leave as-is but non-invasive.
- Verify: both scripts co-exist without conflict (new code is inert for now).

### Phase 3 — Function-to-module mapping catalog

3.1) Map functions from inline script to target modules

- Access/auth/util:
  - `hasProjectWriteAccess`, `hasProjectAdminAccess` → `api.js` or `utils.js` (decision: `utils.js` for predicates, `api.js` for server-driven checks if any)
  - `getCSRFToken` → `api.js`
- UI and overlays:
  - `showNotification`, `hideLoadingOverlay`, `updateLoadingText`, modal open/close helpers → `ui.js`
  - `initializeTabs`, `switchTab`, `modalBackdropHandler` → `ui.js`
  - `openPhotoLightbox`, `closePhotoLightbox`, `openVideoModal`, `closeVideoModal`, `openNoteViewer`, `closeNoteViewer`, `copyNoteToClipboard`, `downloadPhoto`, `openPhotoInNewTab`, `formatNoteContent` → `ui.js` (resources-specific bits coordinated with `resources.js`)
- Context menu:
  - `showContextMenu`, `hideContextMenu`, `showContextMenuForStation`, `showContextMenuForPOI`, `copyCoordinates` → `ui.js`
- Map core:
  - `setMapHeight` and Mapbox GL map initialization, base controls, style layer filters → `mapCore.js`
- GeoJSON visualization:
  - `attachLineClickHandler`, `attachAllLineHandlers` → `geojsonLayer.js`
  - Color/depth helpers: `computeLineColorPaint`, `parseDepthValue`, `getFeatureSectionName`, `getFeatureDepthValue`, `updateDepthLegendVisibility`, `applyColorModeToAllLines`, `setColorMode`, `getProjectColor` → `geojsonLayer.js`
  - Altitude processing: `ensureAltitudeZero`, `processGeoJSONForAltitudeZero`, `forceAltitudeZero`, `extendBounds` → `geojsonLayer.js` (+ math helpers to `utils.js`)
  - Project visibility control: `toggleProjectVisibility` → `geojsonLayer.js` (state stored in `state.js`)
  - Data loading: API calls for project geojson and refresh fallback → `geojsonLayer.js` using `api.js`
- Stations:
  - Data: `loadStationsForProject`, `displayStationsOnMap` → `stations.js`
  - Drag/snap: `handleStationDrop`, `showDragConfirmModal`, `hideDragConfirmModal`, `confirmStationMove`, `cancelStationMove`, `cleanupStationDrag` → `stations.js`, with `ui.js` for modals
  - Snap math: `findMagneticSnapPoint`, `calculateDistanceInMeters`, `showSnapIndicator`, `hideSnapIndicator` → `stations.js` (math in `utils.js`)
  - CRUD APIs: `createStationAPI`, `updateStationAPI`, `deleteStationAPI` → `api.js` (called by `stations.js`)
  - CRUD orchestration: `createStation`, `saveStationEdits`, `deleteStation`, `showDeleteConfirmModal`, `cancelDeleteStation`, `confirmDeleteStation` → `stations.js` and `ui.js`
  - Manager & modal: `loadStationManagerContent`, `showStationDetailsEmpty`, `loadStationDetails`, `displayStationDetails`, `closeStationModal`, `setupStationModalHandlers` → `stations.js` (+ `resources.js` cooperation)
  - Editing flows: `editStation`, `showStationEditForm`, `handleEditKeyboard`, `cancelStationEdit`, `showCancelEditModal`, `closeCancelEditModal`, `confirmCancelEdit`, `proceedWithCancelEdit`, `pickLocationFromMap`, `handleLocationPick`, `handleEscape`, `cleanupLocationPicker` → `stations.js` (+ `mapCore.js` for temporary map listeners)
- Resources (station-scoped):
  - Listing and previews: `loadStationResources`, `getResourcePreview` → `resources.js`
  - Add/edit forms: `loadAddResourceTab`, `showAddResourceEmpty`, `setupAddResourceTabHandlers`, `showAddResourceForm`, `setupResourceFormHandlers`, `hideAddResourceForm`, `updateFileDisplay`, `resetFileDisplay` → `resources.js`
  - CRUD APIs: `saveStationResource`, `updateStationResource`, `deleteResource`, `cancelDeleteResource`, `confirmDeleteResource` → `resources.js` via `api.js`
  - Sketch: `initializeSketchCanvas`, `startDrawing`, `draw`, `stopDrawing`, `clearSketch`, `undoSketch`, `redoSketch`, `updateUndoRedoButtons`, and edit variants → `resources.js` (sketch submodule or internal)
- POIs:
  - Data and display: `loadAllPOIs`, `displayPOIsOnMap`, `cleanupPOIDrag` → `pois.js`
  - CRUD orchestration: `createPOIHere`, `deletePOIFromContextMenu` and related forms/modals → `pois.js` + `ui.js`
  - Drag confirm flow: modal open/confirm/cancel functions (`poi-drag-confirm-modal`) → `pois.js` + `ui.js`
- Utils:
  - Deep copy, DOM helpers, number/formatting utilities → `utils.js`
- Verify: mapping reviewed; ambiguities flagged for decision.

3.2) Define central state and events

- `state.js` contents:
  - `setMap(map)`, `getMap()`
  - `projectVisibility: Map<projectId, boolean>`; `setProjectVisible(id, visible)`
  - `allStations: Map<stationId, Station>`; `stationMarkers: Map<projectId, Marker[]>`
  - `allPOIs: Map<poiId, POI>`; `poiMarkers: Map<projectId, Marker[]>`
  - Selection: `currentProjectId`, `currentStationId`, `activeTab`
  - Event bus: `on(event, handler)`, `off`, `emit`
  - Event names/payloads documented in file header
- Verify: stubs added; no runtime behavior change yet.

### Phase 4 — Implement base modules (no behavior move yet)

4.1) `api.js`

- Implement `getCSRFToken()` (reads cookie) and `apiFetch(path, { method, headers, body, formData })`.
- Implement endpoints used by code: projects/geojson, stations CRUD, resources CRUD/upload, pois CRUD.
- Verify: unit test a simple GET against a known API (e.g., list project geojson with `limit=1`) in isolation from page logic (console result only).

4.2) `utils.js`

- Implement `deepCopy(obj)`, `haversineDistance(a,b)` or use simple distance, `formatDate`, `qs(selector, root)`, `qsa(selector, root)`, `on(el, evt, handler)`.
- Verify: smoke usage in console from `index.js`.

4.3) `state.js`

- Implement store setters/getters; small event bus (Map of eventName → Set of handlers).
- Verify: register a test handler in `index.js` and emit an event; confirm logs.

### Phase 5 — Move non-map UI utilities first (low risk)

5.1) Notifications and overlays to `ui.js`

- Move `showNotification`, overlay helpers.
- Replace their usages in inline script by window shims temporarily: e.g., `window.showNotification = ui.showNotification` from `index.js`.
- Verify: trigger a notification from console; visually appears.

5.2) Tabs and generic modal helpers to `ui.js`

- Move `initializeTabs`, `switchTab`, `modalBackdropHandler`.
- Wire `index.js` to call `ui.initializeTabs()` after DOM ready.
- Verify: open station modal and switch tabs manually; behavior unchanged.

### Phase 6 — Map core bootstrapping

6.1) Create map in `mapCore.js`

- Implement `createMap(containerId, options)` that sets height, creates Mapbox GL map, attaches basic controls.
- Expose `getMap`, `fitBounds`.
- From `index.js`, on DOM ready, call `mapCore.createMap('map', initialOptions)` and `state.setMap(map)`.
- Verify: map renders; no existing features yet.

6.2) Style layer filters and base visibility preferences

- Implement optional style filtering (hide roads/POIs) in `mapCore` via toggling style layers by id match (as currently done inline).
- Verify: logs show hidden layer counts; map visually simplified.

### Phase 7 — GeoJSON layer migration

7.1) Move altitude helpers and color mode helpers to `geojsonLayer.js`

- Implement moved functions: `processGeoJSONForAltitudeZero`, `ensureAltitudeZero`, `computeLineColorPaint`, `parseDepthValue`, `getFeatureSectionName`, `getFeatureDepthValue`, `updateDepthLegendVisibility`, `setColorMode`.
- Accept configuration via `geojsonLayer.init({ state, mapCore, ui })` if needed.
- Verify: unit test these functions with sample data in console.

7.2) Implement project GeoJSON loading

- Port API calls for `/api/v1/projects/{id}/geojson/?limit=1` and refresh fallback sequence.
- Add source `project-geojson-{id}` and layers (lines, etc.) to map.
- Store visibility in `state.projectVisibility`; implement `toggleProjectVisibility(id, visible)`.
- Verify: with one known project, data loads; lines visible; toggling hides/shows.

7.3) Wire line click handlers

- Move `attachLineClickHandler` and `attachAllLineHandlers` to `geojsonLayer`.
- Verify: clicking a line logs intended info; no station/poi yet.

### Phase 8 — Stations (display only)

8.1) Port station listing per project and markers

- Move `loadStationsForProject`, `displayStationsOnMap` to `stations.js`.
- Use `state` to store `allStations` and `stationMarkers`.
- Markers use current classes `.station-marker` and `.has-resources`.
- Verify: stations appear on the map; tooltip/hover effects preserved.

8.2) Minimal interactions

- Port `window.goToStation` to call into `mapCore.fitBounds` or `map.flyTo` via `mapCore.getMap()`.
- Verify: calling `goToStation` scrolls/focuses map correctly; no modals yet.

### Phase 9 — Stations CRUD and modals

9.1) Move Station Manager modal

- Move `loadStationManagerContent` and related helpers to `stations.js`; UI open/close via `ui.js`.
- Wire delegated click handlers instead of inline `onclick` where feasible; add shims for remaining globals.
- Verify: manager opens, lists stations, go-to works.

9.2) Station Details modal + tabs

- Move `loadStationDetails`, `displayStationDetails`, `showStationDetailsEmpty`.
- Ensure resources tab calls into `resources.js` (stub for now) to render previews.
- Verify: open station → tabs render; resources tab shows empty state.

9.3) Create Station flow

- Move `showCreateStationModal`, `hideCreateStationModal`, `createStation` (using `api.js`).
- Verify: can create a station; marker appears; manager updates.

9.4) Edit/Move/Delete flows

- Move editing helpers: `editStation`, `showStationEditForm`, `handleEditKeyboard`, `cancelStationEdit`, `saveStationEdits`.
- Move delete helpers: `showDeleteConfirmModal`, `cancelDeleteStation`, `confirmDeleteStation`, `deleteStation`.
- Verify: edit persists; delete removes marker and station.

9.5) Drag + Magnetic snap

- Move drag orchestration: `handleStationDrop`, confirm modal show/hide, `confirmStationMove`, `cancelStationMove`, `cleanupStationDrag`.
- Move snap helpers: `findMagneticSnapPoint`, `calculateDistanceInMeters`, `showSnapIndicator`, `hideSnapIndicator` (math shared in `utils.js`).
- Verify: dragging shows snap indicator; confirm modal appears; accept/cancel updates state and marker.

### Phase 10 — Resources

10.1) Previews and listing

- Move `getResourcePreview`, `loadStationResources` to `resources.js`; sanitize HTML insertions.
- Verify: existing stations with resources render previews and metadata.

10.2) Add Resource form

- Move `loadAddResourceTab`, `showAddResourceEmpty`, `setupAddResourceTabHandlers`, `showAddResourceForm`, `setupResourceFormHandlers`, `hideAddResourceForm`, `updateFileDisplay`, `resetFileDisplay`.
- Verify: can open Add tab; form validations work; file UI updates.

10.3) CRUD and uploads

- Move `saveStationResource`, `updateStationResource`, `deleteResource`, `cancelDeleteResource`, `confirmDeleteResource`; make `api.js` handle `FormData` uploads.
- Verify: upload an image/video/doc; preview works; edit and delete function.

10.4) Viewers and sketch

- Move lightbox/video/note viewers to `ui.js` facing APIs consumed by `resources.js`.
- Move sketch canvas functions (init/draw/undo/redo) to `resources.js` under a `sketch` namespace.
- Verify: lightbox opens/closes; video modal works; notes viewer works; sketch drawing and undo/redo operate.

### Phase 11 — POIs

11.1) Display and listing

- Move `loadAllPOIs`, `displayPOIsOnMap`; store in `state.allPOIs` and `poiMarkers`.
- Verify: POI markers render; manager modal lists entries.

11.2) CRUD and drag confirm

- Move `createPOIHere`, `deletePOIFromContextMenu`, and POI confirm modal flows.
- Verify: create/delete works; drag confirm modal behaves as before.

### Phase 12 — Context menus and remaining UI glue

12.1) Map/station/poi context menus

- Move `showContextMenu`, `hideContextMenu`, `showContextMenuForStation`, `showContextMenuForPOI` to `ui.js`; they call back into `stations`/`pois` for actions.
- Replace direct DOM constructions with template strings sanitized where needed.
- Verify: right-click behaviors match baseline; actions route correctly.

12.2) Keyboard shortcuts and backdrop handlers

- Move `modalBackdropHandler` and any ESC handlers to `ui.js`; centralize keydown listeners.
- Verify: ESC closes modals; backdrop clicks behave.

### Phase 13 — Wire-up and cut-over

13.1) `index.js` boot orchestration

- On DOM ready → `mapCore.createMap` → `geojsonLayer` loads visible projects → `stations` and `pois` load for those projects.
- Register `window` shims only for remaining inline `onclick`s.
- Verify: page fully works with modules in place.

13.2) Remove legacy inline handlers progressively

- Replace inline `onclick` in template by delegated listeners in modules; leave only unavoidable globals.
- Verify: no console warnings for missing globals; all UI ops work.

13.3) Remove legacy/duplicate code

- Remove parts of the inline `<script>` replaced by modules; keep a small bootstrap if required.
- Remove `poi_functions.js` if superseded by `pois.js`.
- Verify: no references to removed functions remain.

### Phase 14 — Public GeoJSON-only viewer

14.1) New template `frontend_public/templates/pages/geojson_viewer.html`

- Minimal HTML: map container, a simple toolbar if needed for color mode.
- Include `<script type="module" src="{% static 'public/js/geojson_viewer/index.js' %}"></script>`.

14.2) Public `index.js`

- Import `mapCore` and `geojsonLayer` from a shared location (reuse private modules or duplicate minimal code under public path if access rules demand).
- Read URL params: `project`, `commit` or `file`.
- Load exactly one GeoJSON source/layer; disable context menus and hide stations/POIs/resources UI.
- Verify: viewer loads; no extra UI elements; navigation/zoom works.

### Phase 15 — Cleanup, QA, and documentation

15.1) Fix duplicates and dead code

- `getResourceTypeLabel` duplicates: consolidate into one implementation under `resources.js`.
- Remove any now-unused CSS selectors.

15.2) QA pass

- Run full manual test plan (see Acceptance section). Fix issues.
- Verify: console clean; network errors handled; performance acceptable.

15.3) Developer documentation

- Header docs in each module: responsibilities, exported functions, events used/emitted.
- Update this plan with final mapping and any deviations.

### Verification gates (pause points)

- After each Phase (1 through 15), pause and request user verification:
  - Confirm no visual regressions (Phase 1)
  - Confirm module load without errors (Phase 2)
  - Confirm mapping decisions (Phase 3)
  - Confirm base modules compile and can be called (Phase 4)
  - Confirm UI utilities behave (Phase 5)
  - Confirm map renders (Phase 6)
  - Confirm GeoJSON loads and toggles (Phase 7)
  - Confirm stations display (Phase 8)
  - Confirm station CRUD and snap (Phase 9)
  - Confirm resources end-to-end (Phase 10)
  - Confirm POIs (Phase 11)
  - Confirm context menus (Phase 12)
  - Confirm full cut-over (Phase 13)
  - Confirm public viewer (Phase 14)
  - Confirm QA green (Phase 15)

### Risk log and mitigations

- CSS specificity regressions → Keep order, test early (Phase 1 verification).
- Hidden global dependencies → Introduce temporary `window.*` shims in `index.js` and remove gradually.
- Event loops/cycles → Document events; avoid emitting on read-only operations; guard re-entrancy in handlers.
- Upload/CSRF issues → Centralize in `api.js`; test with small files first.
- Mapbox style IDs drift → Query style layers dynamically; apply filters by includes() checks.
