# Viewer responsiveness browser checks

Run these tests inside the existing Django application container after a clean
`bun run build`, with other CPU-intensive suites stopped. Use the Django wrapper
as the default entrypoint; it creates isolated users, public views and
controller fixtures. Configure its PostgreSQL test database as described below.

```bash
pytest tests/browser/test_django_browser.py --gitlab-audit-deny-create \
  -o faulthandler_timeout=1860
```

The responsiveness fixtures use Chromium and WebKit with the real MapLibre
renderer, a minimal local style, deterministic intercepted viewer APIs, and the
normal login form and its generated allauth operation. They do not create,
change, or delete project records. Authenticated cases reuse each account's
initial real login storage state within each Playwright worker instead of
repeatedly consuming the production login rate limit. The snapshots stay in
memory; each test still gets a fresh browser context and independent
preferences. Anonymous cases do not apply them. The stress case loads 60
projects and 120,000 segments. Other cases isolate a 100,000-vertex GPS geometry
and nested GIS geometry types. The harness observes the imported engine instance
through `speleo:map-created` and intercepts provider HTTP data. Native engine
worker behavior, all fixtures, production application work and real rendering
remain enabled.

`viewer-gestures.spec.ts` independently exercises real private/public viewer
initialization, provider HTTP and application APIs without interception or
method replacement. It measures every step of repeated cardinal pans following
wheel crossings through the globe/Mercator transition, with normal/reduced
motion and concurrent updates to 24,000 generated line features. Additional
touch cases pause after releasing one pinch contact, verify that the remaining
contact survives camera completion, then measure every step of its drag. Run
through the Django wrapper below with
`VIEWER_BROWSER_GREP='projection-crossing gestures|paused pinch handoff'` for
isolated public/private database fixtures. The configured basemap provider must
be reachable. See the
[gesture regression contract](../../docs/map-viewer/testing-and-quality.md#projection-crossing-pan-regressions)
for the one-pixel invariant, evidence attachments and device limitations.

`VIEWER_BROWSER_BASE_URL` defaults to `http://127.0.0.1:8000`.
`VIEWER_BROWSER_EMAIL` and `VIEWER_BROWSER_PASSWORD` default to the documented
local development account. Set them explicitly for a different development
server. Install Playwright's Chromium/WebKit binaries and required system
libraries in the test container before running; no separate Django stack is
started by the suite.

Direct `bun run test:browser` execution against an existing server requires
`VIEWER_BROWSER_PUBLIC_URL` for public cases and `VIEWER_BROWSER_ROUTES` for
database-backed controller cases. Resource-edit cases also require
`VIEWER_BROWSER_RESOURCE_RECORDS`, which the wrapper seeds separately for each
browser. Prefer the wrapper for the complete suite; it supplies these values
from its isolated database instead of requiring persistent development records.

Assertions cover native control state in the first animation-frame callback and
verify that map mutations have not preceded it. A separate nested second-frame
callback measures time from the native change event after an intervening paint
opportunity; that feedback interval must meet the shared frame-feedback limit.
All expected samples must finish before their timings are evaluated. This is an
upper-bound observation around a paint opportunity, not an exact displayed-pixel
timestamp.

Other assertions cover source reuse, rapid reversal during network loading and
worker transfer, failure/retry, and geometry-type filters. A zero-delay timer
samples the single large geometry's parsing/preparation interval until the map
source is first installed, with the shared preparation-gap limit. Renderer
source ingestion is excluded from that preparation sample and remains a separate
profiling concern.

All browser timing limits are owned by `tests/browser/budgets.ts` and apply to
both Chromium and WebKit, locally and in CI. Playwright's configuration supplies
the test and assertion defaults to every spec; the shared viewer fixture and
responsiveness assertions import the same budget object. New browser cases must
use these limits instead of adding numeric timeout or latency thresholds.

| Limit                                             |      Value |
| ------------------------------------------------- | ---------: |
| Individual browser test                           |  5 minutes |
| Assertion/poll                                    | 60 seconds |
| Viewer startup wait                               |  3 minutes |
| Frame feedback (settings p95 and each GPS sample) | 15 seconds |
| Preparation timer gap                             |     250 ms |

These are intentionally relaxed regression limits for software-rendered CI, not
product responsiveness targets. The previous 100 ms feedback limit failed at
10,028 ms in the recorded Chromium stress run, so the common 15-second limit
provides headroom. The previous preparation-gap limit was 50 ms. Workload sizes,
sample counts, source reuse, mutation ordering, control state and final-state
assertions remain intact. Timing attachments record both measurements and the
effective limits, so a passing run does not conceal the measured latency.

The JSON run report (`report.json`), timing attachments and failure screenshots
go to the OS temporary directory (override with `VIEWER_BROWSER_ARTIFACTS`).
Network traces are disabled to keep credentials and session cookies out of
artifacts. Do not run performance checks alongside builds, database suites, or
other browser projects. These limits do not establish performance on arbitrary
hardware or data.

On the shared 7.5 GiB development VM, the 120,000-segment stress run exhausted
available memory with GitLab and the other services running (the Django
container recorded one kernel OOM kill). Limiting Mapbox to one renderer worker
still caused severe swapping, so that attempt was terminated. The unchanged
stress case requires a rerun with enough memory; it is not a passing acceptance
result. A separate 4,000-segment settings baseline uses the same assertions and
does not replace the stress case. To run the baseline and overlay cases alone:

```bash
bun run test:browser --grep 'settings baseline|GPS toggle|GIS load'
```

The Settings backdrop retains its dark scrim without blurring the live WebGL
canvas. Recorded feedback results use the second-frame interval described above;
earlier first-frame-only observations do not establish the feedback budget.

The historical isolated baseline/overlay run on that VM passed both GIS cases
and the Chromium GPS case, and failed three timing cases; the stricter feedback
targets were unmet under the original limits:

| Measurement                            | Chromium / SwiftShader | WebKit | Budget |
| -------------------------------------- | ---------------------: | -----: | -----: |
| Settings feedback p95, 4,000 segments  |               989.8 ms | 105 ms | 100 ms |
| GPS feedback maximum, 100,000 vertices |                31.7 ms | 257 ms | 100 ms |
| GPS preparation timer gap maximum      |                46.1 ms |  24 ms |  50 ms |

Both settings cases passed control-state, first-frame map-ordering,
source-reuse, download-count, and final depth-color assertions. Chromium
recorded no long tasks during the settings changes, but that does not establish
passing feedback latency. Both GPS cases reached the intended visible state
without duplicate downloads and received 103 bounded worker messages. Both also
passed the final-hide assertions, which run before timing budgets are evaluated.
These results do not establish acceptance for the unchanged 120,000-segment
stress workload.

The Playwright configuration, fixture and specs are TypeScript, checked in the
development project alongside unit tests, tools and the upload subprocess.
Browser instrumentation is declared in `ts-types/testing/browser/viewer.ts` and
excluded from production and worker checking. Its structural MapLibre interface
records only the methods wrapped or inspected by the harness; the browser still
loads and uses the real CDN renderer. Worker construction, callback receivers,
workloads and timing budgets are unchanged by the type annotations.
`bun run test:browser --list` verifies discovery without running a workload.

CI runs the unchanged responsiveness workloads and browser parity cases through
an explicit Django live-server test outside ordinary backend test discovery:

```bash
pytest tests/browser/test_django_browser.py --gitlab-audit-deny-create \
  -o faulthandler_timeout=1860
```

Use PostgreSQL for this live-server wrapper, as CI does. Set `TEST_DATABASE_URL`
to the existing PostgreSQL connection when the local test dotenv selects SQLite;
pytest creates its isolated test database. Concurrent real viewer requests
cannot safely share the in-memory SQLite connection: session reads and
transactions can fail even though sequential API requests succeed.

Run this only after installing Chromium/WebKit and building assets. The harness
creates a verified database-only user with a generated password, starts Django
through pytest's live-server fixture, and passes the URL and credentials through
the child environment. The shared fixture runs standard `collectstatic` into a
temporary local static root, so the live server serves collected compiled assets
without changing its handler or production storage. It preserves the GitLab
audit environment and does not provision remote projects. Canonical project
rows, explicit permissions, a mutex, fleets, an experiment and a landmark
collection provide database-only route fixtures in `VIEWER_BROWSER_ROUTES`.
Their pages do not read repository contents. The wrapper uses
`tests.browser.urls`: two explicit revision/tree HTTP fixture routes precede the
normal application URLconf. They require the authenticated user's explicit
project permission and return deterministic JSON without opening a repository.
The wrapper verifies URL resolution before launching browsers, and browser cases
assert fixture headers and data. The controllers fetch both through their
generated asynchronous operations. Other mutation cases use browser
interception; the GIS metadata cases create and clean up records in the
wrapper's isolated test database. The manifest is required. CI runs the
`browser-tests` job (displayed as **Chromium and WebKit**) on its own runner,
independently of the `pytest` backend job. The browser job installs its own
locked dependencies, builds assets and runs both engines serially, with its own
PostgreSQL service. Backend tests cannot compete with browser measurements for
that runner's CPU or memory. The backend job still installs Bun and builds
assets for its upload subprocess and asset contracts, but does not install or
run Playwright browsers.

The browser job supplies dummy GitLab settings and does not receive a GitLab
token or start Redis. It starts an isolated RustFS service and provisions the
test bucket for real resource document uploads. Other route fixtures are
database-only, legacy controller mutations are intercepted, GIS metadata/icon
cases use real database-only API mutations, and static assets are collected
locally. It also passes `--gitlab-audit-deny-create`, enforcing zero remote
project creations. Its audit artifact is `browser-gitlab-creation-audit`,
separate from the backend job's `gitlab-creation-audit`; the browser report
remains `browser-verification`.

Playwright's per-case progress streams directly to the console while the Django
wrapper runs. The wrapper has a 30-minute subprocess deadline and terminates the
browser process group on timeout or interruption. CI's Python stack diagnostic
waits 31 minutes for this whole-suite wrapper, as does the explicit override in
the command above. The shared four-minute diagnostic would otherwise show Python
waiting normally for Playwright. Individual Playwright timeouts and
responsiveness limits come from `budgets.ts`; the backend suite uses the shared
240-second stack diagnostic from `pyproject.toml`. Failure details remain in the
console and the browser report artifacts.

`controllers-parity.spec.ts` exercises real compiled controllers, templates and
vendor libraries: authentication errors, public/private Alpine menus,
independent preference scopes and serialization, feedback reset, custom
experiment fields, fleet modal reset, project upload/removal, permissions,
deletion confirmation, mutex failure recovery, revision clone scopes, Git tree
navigation, country storage, station-tag reset, export rejection, experiment
retry and read-only landmarks. Both spreadsheet formats retain contenteditable
keyboard navigation; both DMP upload tools exercise rejection and recovery.
Database grants explicitly distinguish writable and read-only forms.

`viewer-parity.spec.ts` covers anonymous public and read-only private
composition, source/visibility changes, unavailable mutation controls, modal
focus and Tab containment, Escape restoration, supported fullscreen and raw
TypeScript 404s. Measurement cases exercise keyboard placement, cancellation and
clearing; geometry cases exercise pointer drafting, undo/redo, discard, focus
and tool ownership. It supplements the unchanged performance workloads.
Coordinate-based pointer actions wait for camera motion to finish before
projecting the target. Fullscreen assertions retain the browsers' native Escape
policies: Chromium dispatches the key to the dialog, while WebKit first exits
fullscreen without dispatching it; the next Escape closes the dialog. Both paths
verify focus restoration, and ordinary dialog Escape behavior is tested
independently.

For development, `bun run dev` starts opt-in automatic asset rebuilds after
initial type checks and ownership audits; refresh the browser manually after
each successful build. Stop that watcher before running
`docker exec -w /app speleodb-monorepo-django bun run build`, and wait for
completion before starting browser checks. Container startup does not start an
asset watcher, and there is no asset reload client or generation polling
endpoint. `start` remains a finite production build alias.

`viewer-assets.spec.ts` opens the real survey context menu, station manager and
station, exploration-lead and cylinder dialogs. Every shared icon must decode,
and image failures or requests containing an `undefined` path fail the test.
Provider attribution coverage switches from Mapbox to ESRI and back through the
source picker, preserving source credits and the provider logo while excluding
only the provider's Improve this map action. API and tile data are intercepted;
compiled application assets and the native attribution control remain real.

`gis-metadata-icons.spec.ts` verifies optional geometry aliases with the real
renderer, device-persisted label visibility, and all five Landmark icons. It
checks the cold image decode's zoom sizing and collision policy, then switches
styles to verify image restoration and label preferences without repeat geometry
downloads. These cases use uniquely named test-owned collections, landmarks and
geometries created through the real authenticated APIs. They leave existing
developer records untouched and remove their own landmarks before deactivating
their collections and geometries in fixture teardown, including after failures.
The map's manual, coordinate, and edit dialogs and collection detail forms
submit successful real mutations, verify saved values through independent API
reads, and reopen after reload to check persistence. All five built CSS icon
masks decode in the collection color; DEFAULT also registers from default-only
test data. Assertions select the test collection's expected image IDs, allowing
other records to coexist in the development account. Provider styles, raster
tiles and font responses remain deterministic third-party boundaries. The font
response omits glyph contents, so label assertions cover symbol/source contracts
rather than typography. No first-party API response or renderer method is
replaced.

`resource-edit.spec.ts` saves a note and replaces a document using the actual
rendered viewer edit forms. The Django wrapper creates a fresh surface network,
ADMIN grant, station and both resources for each browser, using the real model
and attachment storage. Surface stations require no survey Git repository or
generated survey artifact. All application and provider HTTP remains real: the
test observes the multipart PATCH, verifies the response, independently reads
the saved resource and object bytes, and reloads the viewer. It checks that
disabled resource-type controls are omitted, empty descriptions are saved, and
omitted fields retain their values.

Browser debugging protocols omit uploaded file contents from captured request
bodies. A test-only Django middleware therefore records the actual body for
exactly the fixture-owned resource PATCH paths, bounded to 16 KiB, before the
unchanged application handler reads Django's cached body. It records only the
body and content type, never authentication or cookie headers. A response marker
confirms observation in the browser, and fixture teardown uses Django's real
multipart parser to check every received field, filename and Unicode file byte.
It rejects duplicate or missing companion saves for each exercised browser;
unrelated focused workloads need not edit resources. The saved note assertion
also respects the backend's existing accent normalization, while raw submitted
text and stored attachment bytes must retain their exact Unicode contents.

This fixture requires the test S3 endpoint, credentials and bucket configured by
`config.settings.test`, with presigned browser URLs reachable from the
application container. The existing local RustFS test bucket satisfies this; do
not start another local stack. CI starts its own RustFS job service and runs
`python manage.py create_s3_local_buckets --settings config.settings.test`
before the browser wrapper. Fixture teardown removes only original and
replacement keys owned by its newly created network, including after browser
failures. The basemap provider must be reachable, as for the gesture cases.

For a focused diagnostic wrapper run, set `VIEWER_BROWSER_GREP` to a Playwright
test-name regular expression. The wrapper passes it as a separate `--grep`
argument. Final acceptance runs without this filter. CI always retains the JSON
report, attachments and failure screenshots, including failed runs; trace
recording remains disabled.

## GIS View Geographic Bound

`gis-view-bound.spec.ts` uses `geographic_bound_records` from the Django wrapper
and its `VIEWER_BROWSER_BOUND_RECORDS` environment value. Each browser receives
independent GIS View/Polygon records, a crossing survey and a wholly outside
project, with actual GeoJSON uploads to the test storage namespace. A dedicated
owner created by `VerifiedUserFactory` keeps these surveys and geometries out of
other private viewer fixtures. The factory creates its verified primary email.
Its securely generated password is passed only through the fixture environment
records; the dashboard test uses the normal login form and the shared login
helper caches sessions separately for each account. No API or renderer methods
are replaced. The test checks clipped source coordinates and outside-project
omission and the forced-visible bound rendered through the same GIS Geometry
layers, color, fill and alias label as the private map, clears the bound through
the real dashboard form, and verifies that the unbounded project content
returns. The wrapper's test transaction isolates database records, and fixture
cleanup deletes only its own uploaded objects. These cases require the
configured map provider and test storage to be reachable by the browsers.
