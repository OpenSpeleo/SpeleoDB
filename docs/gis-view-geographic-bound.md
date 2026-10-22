# GIS View Geographic Bound

A GIS View can select one existing Polygon GIS Geometry as its **Geographic
Bound**. The public web viewer clips survey content to this polygon before it
builds map sources, calculates extents or depth ranges, and populates the
project panel. Existing views and new views default to **No geographic bound**.

## Display scope

This is a browser display feature, not an access-control boundary. The browser
still downloads the complete signed project GeoJSON, including coordinates
outside the polygon. OGC endpoints remain unrestricted by this setting and use
the same GIS View token as the public page. Share a view only with recipients
permitted to obtain its complete configured project data. This feature does not
redact downloads, change project permissions, or restrict the private viewer.

Points on the polygon boundary are included. Lines are cut at the boundary;
inside portions remain even when both original endpoints lie outside. Concave
polygons can split a line into several pieces. Boundary-aligned segments remain,
while isolated zero-length tangencies do not create line features. Projects with
no retained geometry disappear from the sidebar. The basemap remains visible and
can be panned outside the polygon. The bound is forced visible using the same
`Layers.addGISGeometry` renderer as the private map: the Geometry's configured
color, polygon fill, outline and optional alias label are preserved. The public
viewer exposes no Geometry management controls. Basemap changes restore it, and
initial camera framing includes the entire boundary even when no survey remains
inside it. It is not a camera constraint.

## Configuration and lifecycle

Create a Polygon through GIS Geometries, then select it in the GIS View create
or details form. The Django admin offers the same optional field. New selections
require an active Polygon that the view owner can read. Lines are never offered
as bounds. The shape retains the existing Geometry limits: a simple closed 2D
WGS84 outer ring, no holes or antimeridian crossings, at most 100 vertices and a
bounding-box area at most 30 km². See [GIS Geometry](gis-geometries.md).

The selection is a live reference. Polygon edits affect the next public page
load or metadata refresh; already open pages do not poll. Style/source reloads
reuse the accepted polygon. Removing the view owner's geometry permission does
not remove or disable an existing bound. The dashboard retains an inaccessible
selection with a neutral label and permits explicitly clearing or replacing it.
Selecting **No geographic bound** intentionally restores the unrestricted
display.

A geometry's LineString/Polygon type cannot change after creation, including
through raw JSON, API, and admin updates. Soft deletion is blocked while a GIS
View references the geometry; clear or replace those bounds first. The database
foreign key also protects hard deletion. Selection and soft deletion lock the
same geometry record, so concurrent operations cannot create a reference to a
newly deactivated shape.

## Contract and ownership

`GISView.geographic_bound` is a nullable foreign key with default `None`.
Management create/update/read representations use
`geographic_bound: UUID | null`. An omitted update field preserves the
selection; explicit `null` clears it. The public map metadata response includes
`geographic_bound: null` or `{id, revision, geojson, color, alias}`, where
`geojson` has the Polygon-only shape. It does not include the geometry's private
name, description, or permission records. The public response resolves the
linked geometry without requiring ongoing owner access. No new project download
endpoint is introduced.

The web application owns selection, permissions, lifecycle and the decision to
clip. `@speleodb/map-core` owns the reusable pure survey clipping algorithm.
`@speleodb/map-viewer` retains its renderer specifications. The generated
`@speleodb/api` contract comes from the SDK's local OpenAPI snapshot, explicitly
updated from the reviewed backend export. Each repository validates its own
schema independently.

The shared web survey loader accepts an optional asynchronous transformation
before survey preparation. Only the bounded public viewer supplies clipping. The
transformation does not mutate the downloaded input, preserves survey
properties, interpolates additional coordinate dimensions at cuts, and emits
separate LineString pieces with unique IDs. Multipart point/line components are
handled individually; unsupported or malformed source geometries do not pass
through the bounded display. Stale collection/feature bounding boxes are removed
so preparation derives extents from the retained coordinates. Invalid bound
metadata or processing errors never trigger an unrestricted fallback.

The public composition retains complete project inputs separately from the
visible project list. This lets style reloads rebuild clipped sources without
losing projects that previously clipped to empty. Colors still use configured
project metadata. Camera framing includes the boundary and clipped data; depth
calculations use only the prepared clipped data; depth properties retain their
existing meaning rather than being invented from altitude.

## Performance and verification

Clipping runs when project data loads, not on camera movement or depth-mode
changes. Polygon bounds reject nonintersecting work early. The edge count is
bounded by the existing 100-vertex authoring contract. Remaining segment work is
cooperatively scheduled and cancellable using the existing preparation runner.
Splitting lines can increase feature count, proportional to segment
intersections. The live reference adds related-object loading rather than
per-project database queries; it creates no additional storage artifacts or
server clipping cache.

Backend coverage exercises null defaults, selection access, unchanged selections
after revocation, live edits, deletion protection, immutable types, admin
choices, management contracts and unchanged OGC/private output. Geometry tests
cover boundary/concave/multipart cases, altitude interpolation, input
immutability, invalid input, empty results, scheduling and cancellation. Viewer
tests verify clipped sources, extents/depth, hidden empty projects, style
reloads and null-bound parity. Browser cases use the existing Django/Playwright
harness with small deterministic HTTP responses and database-only dashboard
records. They check the real rendered polygon fill, outline, alias and color
across style changes, and native selection, error recovery and save feedback.
They do not upload surveys, inspect map sources, assert request payloads or read
back a browser mutation. Exact clipping and renderer configuration remain in
`frontend_common/test/viewer-composition.test.ts`; selected UUID/null payloads
remain in `frontend_common/controllers/gis-view-form.test.ts`. The pytest suites
`speleodb/gis/tests/test_gis_view_geographic_bound.py` and
`frontend_private/tests/test_gis_view_geographic_bound.py` own persistence,
permissions, lifecycle, metadata and server-rendered selector contracts.

Run web verification inside the existing `speleodb-monorepo-django` container at
`/app`: focused pytest suites, the full backend suite, frontend tests/lint,
TypeScript checks and the production build, followed by browser checks. Run
map-core's independent test/type/lint/build commands and the SDK's generation
drift, type, lint, test and build checks. Export/check the backend's canonical
schema locally; SDK generation checks its own committed snapshot and digest. The
monorepo's separate root integration test requires both checked-out schema
snapshots and the SDK's recorded hash to agree. See
[API contract](api-contract.md) and
[TypeScript client](typescript-api-client.md) for explicit snapshot updates.
