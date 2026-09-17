# GIS Geometry

GIS Geometry is the private authoring counterpart to GIS Layers: a user draws
one small line or polygon and shares it with collaborators. GIS Layers retain
their file-based import workflow. Geometry stores a directly editable GeoJSON
document in the database, so editing needs neither source uploads nor conversion
jobs, object storage, or polling.

Account Settings → Export / Backup includes accessible active geometries in
`geometries/<name>--<uuid>.geojson`. Files preserve the stored LineString or
Polygon coordinates; the export manifest includes revision, name, color,
creator, timestamps, and checksums. READ_ONLY access is sufficient. Data and
permissions are captured at generation start, consistent with the existing
export contract.

## User workflow

The backend navigation orders My GIS Geometry, My GIS Layers, then My GPS
Tracks. The GIS Geometry navigation entry opens the same responsive listing and
settings workflow as GIS Layers. Each record has a name, creator, color,
Details, User Access, and an administrator-only Danger Zone. Create geometry
opens the Survey Viewer without creating an empty database record. Details also
offers View/Edit on map and an Advanced: GeoJSON field. Readers can inspect and
copy JSON; writers can edit it. Name, color, and changed geometry save in one
atomic request.

The Survey Viewer loads geometry metadata alongside its other lists. All stored
geometries start hidden on each fresh viewer load. Visibility uses the same
toggle switch markup and styles as GIS Layers and the other map panels, keeping
keyboard access and loading/editing locks. The visibility toggle does not change
the camera; clicking a name shows and frames the shape. The geometry panel stays
discoverable when empty and uses the same chevrons as other map panels. Create
Geometry sits immediately before Import GPS in the compact viewer toolbar; the
geometry panel holds visibility and editing controls. Coordinates are fetched
only on demand. Each new draft starts with a randomly selected color from the
server-provided palette; editing preserves the stored color. The initial color
remains stable during drawing and can be changed with the existing swatches.

Metadata retries preserve successful local saves made while a request is in
flight, without retaining unchanged records omitted by the server. A failed
retry keeps locally saved rows available alongside its Retry action. Panel
expansion, collapse, and visibility changes preserve keyboard focus on a visible
control; asynchronous responses never take focus away from the editor. An older
failed detail request cannot undo a newer saved shape's visibility or the user's
subsequent hide action.

Folded Projects, GPS Tracks, GIS Layers, and GIS Geometry cards share one 160 ×
48 px size in the shared map stylesheet, keeping their labels and chevrons
aligned without per-component sizing overrides.

Polygon fills use 17.5% opacity when saved and 9% while editing, keeping the
underlying map legible. These rendering constants are centralized in
`DEFAULTS.GIS_GEOMETRY`; there is no transparency setting in the UI.

Create offers Line and Polygon, defaulting to Line. Place vertices on the map or
enter signed decimal GPS coordinates. Select a vertex to drag it, edit its
latitude/longitude, insert a point, or remove it. Polygon closure is automatic.
Finish drawing switches to selection; a valid drawing can also be saved
directly. Undo/Redo changes only the draft. Coordinate fields flush before Save,
including the field that currently has focus.

Save persists the entire candidate, closes the editor, and leaves the saved
shape visible for that session. Revert restores the previous saved state and
visibility. Discarding a new geometry makes no API request. Unsaved dismissal
requires confirmation, and failed saves retain the draft.

## Interaction design

The map remains the primary workspace. A compact inspector sits beside it on
desktop and becomes a bounded bottom sheet on narrow screens. Only the inspector
body scrolls; the measured area, limit explanation, and Save/Revert actions stay
visible. Color and GPS entry use disclosure controls to keep the initial drawing
flow focused on naming a shape, choosing its type, and placing points.

Geometry framing uses the complete coordinate bounds and the unobstructed map
rectangle after the inspector is laid out. Transient camera padding excludes
panels and the offscreen portion of the canvas; it does not persist into other
map navigation. On mobile, the sheet tracks the visual viewport so its footer
stays reachable during page scrolling, keyboard changes, and fullscreen.

The currently selected vertex appears on the map and in a compact previous/next
navigator. This supports precise keyboard/GPS editing without filling the screen
with a long coordinate table. Existing vertices update from the same draft
commands as dragging. Unsaved coordinates count as changes and are validated
before another action can replace them. The saved overlay is hidden while its
draft is active, and its panel controls are locked until editing ends.

Each drag is one undo command, including when a keyboard command arrives before
pointer release. A second touch cancels a vertex drag so pinch navigation cannot
change its coordinates. Click suppression ends at the next pointer gesture;
Mapbox can omit the click after a drag. Native Enter activation and vertex
navigation focus remain available throughout inspector refreshes, and reaching
the vertex cap disables additions without disabling GPS updates to existing
points. These rules share the existing draft commands and add no per-feature map
scans.

Errors remain next to the Save action. A revision conflict offers copying the
draft and reloading the saved version; it never retries an overwrite silently.
Editor switching waits until an active save or reload finishes. Clipboard
completion belongs to its initiating draft and cannot modify a later editor.
Area warnings use both words and color, and the Save button cannot bypass an
invalid pending coordinate or an oversized bounding box.

## Limits and geographic meaning

**The bounding box cannot exceed 30 km² for performance reasons.** It is the
smallest north–south/east–west rectangle around the coordinates, not the area
inside a polygon. A diagonal line can therefore exceed the limit. The editor
shows the box and updates its area during changes:

| Area                    | Feedback                         | Saving                       |
| ----------------------- | -------------------------------- | ---------------------------- |
| At most 8 km²           | Neutral                          | Allowed if otherwise valid   |
| Above 8, at most 30 km² | Orange warning                   | Allowed if otherwise valid   |
| Above 30 km²            | Red, explicit over-limit message | Disabled and rejected by API |

Every shape is also limited to **100 editable vertices**. A polygon's repeated
closing coordinate does not count. This independent cap limits complexity even
for dense shapes with very small bounds. There is no separate line-length limit:
a straight horizontal or vertical line can have zero bounding-box area.

Validation accepts one bare 2D GeoJSON `LineString` or `Polygon` with `type` and
`coordinates`. Coordinates are finite `[longitude, latitude]` numeric pairs in
WGS84 decimal degrees (longitude ±180°, latitude ±90°). A line requires two
distinct vertices; a polygon requires three, a closed outer ring, and valid
nondegenerate topology. Holes, self-crossing/touching polygon edges, multipart
geometries, standalone points, feature collections, altitude, and
antimeridian-crossing segments are unsupported. Both polygon winding directions
are accepted. Source precision is preserved rather than rounding coordinates
during editing.

The server derives bounds from the coordinates and never trusts claimed bounds.
The browser and Python use this same spherical rectangle calculation:

```text
R = 6,371,008.8 metres
area_m2 = R² × radians(east − west)
            × 2 × cos(radians((north + south) / 2))
            × sin(radians((north − south) / 2))
```

This is a consistent map-performance measurement, not ellipsoidal survey area.
The product form avoids cancellation at high latitudes. Compare full precision
against 8,000,000 and 30,000,000 m²; round only for display. An over-limit value
always has explicit text, even if a rounded number looks like 30.00. Ordinary
min/max longitude bounds agree with the supported non-crossing render geometry.

`speleodb/gis/geometry_contract.json` is the canonical policy for supported
types, area thresholds, vertex limits, coordinate bounds, and measurement
constants. Python validation and the browser's `DEFAULTS.GIS_GEOMETRY` both read
this contract. Management help derives its limits from these values, and
contract tests keep the public policy and both validation paths aligned.

## Ownership, permissions, and persistence

`GISGeometry` owns UUID identity, name, color, creator-email provenance,
GeoJSON, timestamps, active state, and a content revision. Creation atomically
creates an ADMIN permission for the authenticated creator.
`GISGeometryUserPermission` rows are the sole application authorization source
afterward; provenance never grants an implicit bypass. READ_ONLY views,
READ_AND_WRITE edits, and ADMIN edits, shares, and soft-deletes. Team and
WEB_VIEWER access are not part of this feature.

Soft deletion preserves the document and permission history and deactivates
access. The Django admin preserves its established administrative authorization
while using the same validators and mutation services. Admin creation assigns
creator provenance and an ADMIN grant; hard deletion is unavailable.

Updates require the last-read `expected_revision`. The service locks the record,
checks current authorization and revision, validates the complete candidate, and
writes once. A successful update increments revision. Stale writes return 409;
the UI retains the draft rather than silently overwriting another collaborator.
Sharing changes do not increment the geometry content revision.

The Geometry permission endpoint and serializer follow the existing typed GPS
Track and GIS Layer implementations. Their model queries and transaction
boundaries stay explicit; Geometry sharing locks the geometry before checking
current access or changing grants. The established direct-user request parser
remains shared for collaborator, level, and self-edit validation. There is no
additional GIS-only permission base class or dynamically selected model field.

## API

| Endpoint                                   | Methods                | Purpose                              |
| ------------------------------------------ | ---------------------- | ------------------------------------ |
| `/api/v2/gis-geometries/`                  | GET, POST              | Accessible metadata / create         |
| `/api/v2/gis-geometries/<id>/`             | GET, PATCH, DELETE     | Detail / atomic update / soft-delete |
| `/api/v2/gis-geometries/<id>/permissions/` | GET, POST, PUT, DELETE | Direct-user sharing                  |

Creation sends `name`, `color`, and `geojson`. PATCH sends changed fields and
`expected_revision`; it never partially commits metadata after invalid geometry.
Metadata includes `geometry_type`, revision, permission level, and capability
booleans. Detail/save responses include `geojson`, derived bounding-box area,
and vertex count. Creator, lifecycle state, timestamps, and revision are
server-owned.

```json
{
  "name": "Entrance approach",
  "color": "#377eb8",
  "geojson": {
    "type": "LineString",
    "coordinates": [
      [-87.5, 20.5],
      [-87.501, 20.502]
    ]
  }
}
```

## Frontend architecture and performance

The feature follows the existing API → Config/State → Layers lifecycle. Config
contains metadata and centralized capability helpers. State owns session
visibility, coordinate cache, in-flight detail requests, and which saved overlay
is temporarily hidden during editing. Layers owns persisted overlay rendering. A
small shared vector renderer is also used by GIS Layers without changing their
source documents, popups, storage, or loading semantics.

The private-only editor maintains an isolated vertex draft. Its commands power
both mouse/touch and GPS editing. Draft handles and bounds occupy dedicated
`gis-geometry-draft-*` sources/layers, ordered above survey overlays. The
existing Interactions dispatcher gives the active editor exclusive event
ownership, so drawing cannot move a landmark or trigger a survey context menu
simultaneously. Pan/zoom remain available outside vertex drags. Raster source
switching preserves overlays; genuine style resets restore the draft.

Shared settings templates, list markup, forms, permissions, color palette, and
notifications preserve familiar product behavior. No new drawing library or
generic overlay runtime is needed. Geometry is not imported or fetched by the
public viewer. Querysets annotate permissions in bulk and metadata listings
defer the GeoJSON field. Validation work is bounded by the 100-vertex cap.

## Verification

Run all tests, builds, and checks inside the existing application container at
`/app`. Geometry tests use database-only identities and allocate no GitLab
repositories. Shared fixtures compare Python/browser area calculations.

Coverage includes permissions and revocation, atomic failures and stale
revisions, model/API/admin validation, exact area/vertex boundaries, topology,
escaping, query counts, default-hidden lazy loading, concurrent show requests,
style restoration, draft command history, GPS/mouse equivalence, focused-input
Save, and interaction ownership. Existing GIS Layer, GPS Track, private/public
viewer, and shared form tests guard the reused contracts.

PostgreSQL concurrency regressions use two real connections and observe blocked
database writers. They prove that a waiting edit rechecks the committed
revision, revoked access, and soft deletion after acquiring the geometry lock.
These checks require the PostgreSQL test database; SQLite runs skip them because
it does not implement row-level `SELECT FOR UPDATE` locking.

Visual checks exercise desktop/mobile, fullscreen, keyboard/GPS-only authoring,
touch, oversize correction, Save/Revert, raw JSON, and retained failed drafts.
Always use a clean production Vite build and verify the manifest served by
Django before recording browser evidence. Results are tracked in the feature
todo and repository review log.
