# Private map distance ruler

## Intent and scope

The ruler answers one immediate question: how far apart are these two map
locations? It is a temporary viewing tool, available to every authenticated map
viewer user independently of entity write permissions. It does not create GIS
geometry, call an API, or save browser preferences. The public viewer does not
initialize it.

Activate the ruler directly below Map Source. Left-click to start measuring,
move the pointer to preview, and left-click again to stop and retain the result.
Each subsequent measurement is independent. The connector has a gentle bow to
distinguish measurement annotations from survey lines; its shape is **not** the
path used to calculate distance.

Both metric and imperial values remain available together. The tool measures
shortest spherical surface distance using the viewer's existing mean-radius
Haversine model (6,371,000 meters). It does not account for terrain, station
depth/elevation, or cave-route length, and does not snap to survey features.
Displayed precision does not imply survey accuracy.

## Interaction contract

| Action                                     | Result                                         |
| ------------------------------------------ | ---------------------------------------------- |
| Ruler on                                   | Ready to start; map uses a crosshair           |
| First left-click/tap                       | Start measuring                                |
| Pointer preview, including camera movement | Update the distance under the pointer          |
| Next left-click/tap                        | Stop and keep the measurement; ready to repeat |
| Right-click or Escape                      | Cancel only the unfinished pair                |
| Ruler off                                  | Clear all pairs and restore normal interaction |
| Start geometry creation/editing            | End measurement and clear its pairs            |
| Basemap/display change or ordinary dialog  | Preserve the measurement session               |
| Page reload                                | Start with measurement off and no pairs        |

Dragging with the left mouse button pans rather than stopping a measurement.
Scroll/pinch zoom remains available. Touch uses tap-to-start and tap-to-stop,
with the ruler button providing exit and clear-all; long-press is not a required
gesture. There is no separate Cancel button. One click path commits endpoints
for mouse and browser-generated tap clicks, avoiding an additional commit on
touchend. Native touch cancellation invalidates a tap. Coincident endpoints and
repeated double-click/keyboard events cannot produce accidental extra
measurements.

Keyboard activation focuses the map canvas and shows a reticle within its
intersection with the visible viewport, clear of the instructions. Existing map
arrow and zoom keys move the target; Enter places it. Endpoint key handling
belongs to the focused canvas. Menus, dialogs, and form fields retain their own
keys. The source picker only handles Escape while its menu is open.

Instructions use concise, aligned action/meaning rows instead of tutorial
paragraphs or point A/B terminology. The card fits the concise rows instead of
reserving space for tutorial prose; responsive sizing preserves readability.
Mouse, touch, and keyboard users receive the applicable start/stop, navigation,
cancellation, and exit/clear gestures. Pointer movement previews the distance
and scrolling zooms without separate mouse instruction rows. The mouse reference
contains only left-click, left-drag, right-click/Escape, and “Ruler icon” for
exit. A horizontal divider separates the clear-all/exit row from the measurement
gestures.

The “Distance measurement instructions” header is a native button with a
right-hand chevron, `aria-expanded`, and `aria-controls`. It collapses only the
gesture reference, retaining the header and the active measurement session.
Every ruler activation expands it again. Toggling updates the existing layout so
the keyboard reticle can use the freed map area; no collapse preference is
persisted.

A polite live region announces state changes and completed results, not every
pointer movement. A visually hidden ordered list exposes completed distances to
screen readers. The live readout remains visible during pointer movement.
Completed distance labels use native alternative anchors and collision
placement, prioritizing the newest result; crowded older labels become visible
as zoom separates them. Their measurement geometry remains on the map.

## Ownership and extension boundaries

The private entrypoint creates `MeasurementTool` and adds its Mapbox control
after Map Source. The tool owns off/ready/drawing state, temporary records,
input gestures, instructions, accessible results, and cleanup. Its public
lifecycle includes `activate`, `deactivate`, `cancelDraft`, `isActive`,
`setAvailable`, and `destroy`.

`Interactions.getActiveTool()` is the single dispatch boundary for geometry
editing and measurement. While a tool is active, the normal entity hover, popup,
drag, and context-menu paths are not entered. This avoids a competing set of map
listeners and prevents permission-sensitive entity mutations from being
accidentally triggered by ruler gestures. `cancelPendingDrag()` releases a
pending entity drag before a new tool takes ownership: it restores any transient
position and feedback, restores the original camera handlers, and discards the
gesture without calling a persistence callback.

The editor exposes `isOpening()` and optional
`onActivityChange({ opening, active })`. It notifies before asynchronous loading
and before recording double-click-zoom state. The private entrypoint clears the
ruler and updates availability there, covering toolbar, panel, and deep-link
editor entry paths. Failed loading releases availability without resurrecting
old measurements. Existing geometry preview callbacks retain their separate
responsibility for saved/draft layer visibility.

`measurement/geometry.js` owns curve construction, unit formatting, and valid
map picking. `map/geodesy.js` is the shared pure distance implementation;
`Geometry.calculateDistanceInMeters` preserves its existing caller interface.
The measurement record keeps authoritative endpoints and raw meters separate
from its derived display geometry.

`MeasurementRenderer` owns two native GeoJSON sources, completed and draft, plus
line casing, line, endpoint, and completed capsule-label layers. It uses one
raw-pixel stretchable image for completed label backgrounds. The changing live
readout uses one pointer-transparent Mapbox Marker with a DOM capsule: native
symbol placement keys include text, so constantly changing distances otherwise
fade away during pointer movement. Completed labels retain native collision
management. Mapbox owns camera projection and globe clipping for both layers and
the single live marker; there is no custom SVG/DOM projection engine to
synchronize with it.

All measurement layer/image/source identities use the private
`speleo-measurement-` namespace. The source-switching overlay registry preserves
this namespace, and the shared layer-ordering operation restores measurement
order after asynchronous entity updates. Geometry editor handles retain their
established topmost order. The public viewer imports no measurement tool or
renderer.

## Geometry and rendering limits

A smooth perpendicular spherical offset produces the decorative curve. Its peak
is six percent of endpoint angular separation, capped at 0.01 radians. Sampling
uses at most one-degree steps with bounded segment counts. Endpoint coordinates
remain exact; antipodal degeneracy has a deterministic fallback. Date-line
crossings are split into valid parts. Curve styling and sampling never affect
the endpoint distance.

The current native GeoJSON renderer has a Web Mercator polar latitude limit.
Endpoint picking outside its supported band is rejected instead of silently
moving a point. Curve sections outside that band are clipped instead of being
flattened along the boundary. Distances retain their geographic meaning.

Picking uses the public surface API and a projection/unprojection round trip.
This extra check is necessary because the pinned Mapbox version can clamp sky
coordinates to the globe horizon. Invalid preview positions hide the preview and
preserve the start location.

Meters/kilometers and feet/miles derive from the same raw value. Formatting uses
at most one decimal for meters, whole feet, and two decimals for large units,
promotes rounded unit boundaries, and uses a less-than representation for
positive sub-resolution distances.

## Lifecycle and performance

Measurement state is independent of `State.resetLayerState`, display
preferences, and backend models. Genuine style reloads restore the owned
sources/layers/image idempotently. Ordinary basemap changes preserve overlays
without reloading survey data.

Pointer movement updates only the draft, coalesced to an animation frame. The
latest mouse screen point is re-picked when the camera moves, keeping the
preview consistent with the next click. Leaving the canvas, suspending for a
dialog, canceling, or changing input mode invalidates that point. Completed
curves and distances are cached; camera movement does not regenerate them, and
measuring does not query or rescan survey features. Updating the completed
source occurs when a pair completes. Native label decluttering avoids a custom
collision solver or a DOM marker for every completed result; only the current
preview has a DOM label.

Turning the tool off removes owned overlays and pending animation work.
Destruction removes listeners and restores previous camera-handler state.
Delayed callbacks must not recreate overlays after clearing or removal. Control
and instructions remain inside the fullscreen host. Private coarse pointer
controls use consistent touch targets, with a two-column rail for short map
viewports.

## Verification

Run all tests in the already-running application container. Colocated tests
cover pure geodesy, curve/formatting limits, real tool DOM/state, renderer
lifecycle, dispatcher exclusivity, editor activity ordering, source
preservation, and both viewer entrypoints. Use a minimal Mapbox boundary harness
rather than mocking the measurement modules.

Real authenticated Chromium verification uses the existing Playwright setup
inside that container and the actual clean Vite build served by Django. Check
multiple pairs, canceled drafts, right-click, mouse pan, touch tap/pinch/cancel,
keyboard placement, dialogs, editor launch, source/style changes, globe edges,
label contrast/collisions, fullscreen, small mobile and landscape layouts, 200%
zoom, reduced motion, and repeated activation/teardown. Confirm the served
manifest hash and inspect runtime errors. Record outcomes and remaining limits
in the task review; JSDOM results alone are not visual or gesture evidence.

Future route length, snapping, editing, area measurement, persistence, or export
must be designed as explicit product extensions. Keep their data contracts
separate from this temporary point-to-point session.
