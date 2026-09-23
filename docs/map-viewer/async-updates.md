# Responsive viewer updates

## Intent and boundaries

Display controls acknowledge user intent immediately. Map work starts after a
rendering opportunity and converges on the latest choice. This applies to
settings, project/country/network selection, GIS and GPS visibility, geometry
types, source selection, and navigation. It does not make a save or deletion
successful before the server confirms it. Direct drawing and drag feedback
retain their immediate gesture semantics.

An `async` declaration alone does not allow the browser to paint. In particular,
a cached load can perform all its work before its first asynchronous boundary.
The viewer therefore separates state changes, preparation, map application, and
preference persistence.

## State and application

`viewer_updates.js` owns keyed, serial map application. Two animation frames
precede a future task, leaving an intervening rendering opportunity before map
work. Every job has a cancellable paint gate, including intent received while
the queue is already running or another job's frame has already elapsed. Map
work never executes in a frame callback. Replacing a pending key supersedes the
old operation. Running work checks its context after yielding and before further
map mutations. Jobs return `applied`, `superseded`, `cancelled`, or `failed`;
failure of one job does not prevent unrelated work. Network requests and large
data preparation belong outside this serial queue.

Layers setters publish validated preferences immediately. `setDepthLimit`
retains its synchronous boolean validation result. Rendering callers use
`Layers.whenDisplayApplied()` when subsequent behavior needs completed map
application. Country gates are maintained in memory and composed with individual
project choices before rendering or persistence. Newly installed layers use the
current gates rather than the choices captured when their download began.

Display concerns accumulate until a successful application. One pass updates
project/network visibility, shared marker filters, cached depth domains, and
line colors as required. The pass yields within large project/layer collections.
Visibility checks inspect known layer IDs without serializing the entire map
style. Layer ordering is separately coalesced and yields while classifying and
moving registered layer IDs, without serializing source geometry through a style
snapshot. Category changes preserve source data and cached depth domains.

Controls represent desired state while application is pending. The depth cursor
and legend are withheld during an incomplete display update, then use the
matching completed domain and color mode. A partially failed application keeps
them hidden until a successful retry; settings reports the failure. The existing
hover is retained when possible so changing units or a depth limit does not
require moving the pointer.

The scheduler is reused by public rendering, but public initialization continues
to reset defaults without loading private display preferences.

## Loading and navigation

GPS and GIS downloads deduplicate in-flight detail/file requests. Their
completion checks the current map, data generation, metadata revision, and
latest intent. Requests, caches and installed sources use the content revision
rather than metadata object identity, so a routine list refresh cannot strand
loading state or reuse an older file. Cached data and layer installation are
separate: an item hidden during its download cannot become visible when the
download finishes. A stale failure cannot clear a newer choice, loading
indicator, or camera request. Current failures are visible and can be retried
explicitly. Map removal cancels outstanding work.

Navigation uses one shared intent across projects, tracks, GIS, stations, and
landmarks. An explicit locate action waits for its required visibility work;
newer navigation, hiding its target, a user pan, or teardown invalidates it.
Ordinary visibility controls never move the camera. Editor callbacks await saved
baseline installation before preview navigation; editor suppression remains an
immediate gate.

## Preparation and storage

Project preparation uses immutable structural copies, cached depth domains,
prepared snap endpoints, and prepared bounds. It yields within coordinate
arrays, including a single large line. GIS presentation preparation and
geographic bounds also yield. Large JSON downloads are parsed in a module worker
with bounded node delivery (including coordinates within a single feature) and
main-thread acknowledgment; the source payload and properties remain unchanged.
See [data flow](data-flow.md) for algorithms and measurement details. Renderer
ingestion remains a distinct measured cost.

Display preference writes are coalesced after paint and flushed on page exit and
owner teardown. They serialize current in-memory values, not stale event
snapshots. Storage failure leaves controls usable. No authentication credentials
or source geometry are added to display persistence.

## Verification

Vitest tests cover scheduler ordering, supersession, failures and cancellation;
real layer setters and delayed API completions; stable control identity; shared
camera intent; country gates before storage flush; cached depth work; immutable
preparation and large coordinates; worker transfer, errors and cancellation. The
asset graph test includes worker bundles so workers cannot silently fall out of
the production graph.

Run the complete JavaScript suite, lint, clean production build and browser
tests inside the existing application container. Browser checks use actual
rendering, large deterministic inputs, a second interaction during work, and
final-state assertions. Record input-to-control-paint separately from map
completion and renderer long tasks. The target is p95 control feedback within
100 ms on the recorded workload, with application work slices around 8 ms. These
are measured workload targets, not guarantees for arbitrarily large payloads or
every device.
