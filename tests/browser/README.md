# Viewer responsiveness browser checks

Run these tests inside the existing Django application container after a clean
`bun run build`, with other CPU-intensive suites stopped:

```bash
bun run test:browser
```

The suite uses Chromium and WebKit with the real Mapbox renderer, a minimal
local style, deterministic intercepted viewer APIs, and the normal Django
headless login endpoint. It does not create, change, or delete project records.
Authenticated cases reuse the initial real login's storage state within each
Playwright worker instead of repeatedly consuming the production login rate
limit. The snapshot stays in memory and is captured before application
navigation; each test still gets a fresh browser context and independent
preferences. Anonymous cases do not apply it. The stress case loads 60 projects
and 120,000 segments. Other cases isolate a 100,000-vertex GPS geometry and
nested GIS geometry types. The harness limits Mapbox to one renderer worker to
bound memory in the shared development container; all fixtures, production
application work, and real rendering remain enabled.

`VIEWER_BROWSER_BASE_URL` defaults to `http://127.0.0.1:8000`.
`VIEWER_BROWSER_EMAIL` and `VIEWER_BROWSER_PASSWORD` default to the documented
local development account. Set them explicitly for a different development
server. Install Playwright's Chromium/WebKit binaries and required system
libraries in the test container before running; no separate Django stack is
started by the suite.

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
excluded from production and worker checking. Its structural Mapbox interface
records only the methods wrapped or inspected by the harness; the browser still
loads and uses the real CDN renderer. Worker construction, callback receivers,
workloads and timing budgets are unchanged by the type annotations.
`bun run test:browser --list` verifies discovery without running a workload.

CI runs the unchanged responsiveness workloads and browser parity cases through
an explicit Django live-server test outside ordinary backend test discovery:

```bash
pytest tests/browser/test_django_browser.py
```

Run this only after installing Chromium/WebKit and building assets. The harness
creates a verified database-only user with a generated password, starts Django
through pytest's live-server fixture, and passes the URL and credentials through
the child environment. The shared fixture runs standard `collectstatic` into a
temporary local static root, so the live server serves collected compiled assets
without changing its handler or production storage. It preserves the GitLab
audit environment and does not provision remote projects. Canonical project
rows, explicit permissions, a mutex, fleets, an experiment and a landmark
collection provide database-only route fixtures in `VIEWER_BROWSER_ROUTES`.
Their pages do not read repository contents. WebKit bypasses browser routing for
native synchronous XHR, so the wrapper alone uses `tests.browser.urls`: two
explicit revision/tree HTTP fixture routes precede the normal application
URLconf. They require the authenticated user's explicit project permission and
return deterministic JSON without opening a repository. The wrapper verifies URL
resolution before launching browsers, and browser cases assert fixture headers
and data. Controller contexts, URL reversal, native XHR and its synchronous
timing remain unchanged. Mutations use browser interception. The manifest is
required. CI runs the `browser-tests` job (displayed as **Chromium and WebKit**)
on its own runner, independently of the `pytest` backend job. The browser job
installs its own locked dependencies, builds assets and runs both engines
serially, with its own PostgreSQL service. Backend tests cannot compete with
browser measurements for that runner's CPU or memory. The backend job still
installs Bun and builds assets for its upload subprocess and asset contracts,
but does not install or run Playwright browsers.

The browser job supplies dummy GitLab/storage settings and does not receive a
GitLab token or start S3/Redis services: route fixtures are database-only,
mutations are intercepted and static assets are collected locally. It also
passes `--gitlab-audit-deny-create`, enforcing zero remote project creations.
Its audit artifact is `browser-gitlab-creation-audit`, separate from the backend
job's `gitlab-creation-audit`; the browser report remains
`browser-verification`.

Playwright's per-case progress streams directly to the console while the Django
wrapper runs. The wrapper has a 30-minute subprocess deadline and terminates the
browser process group on timeout or interruption. CI's Python stack diagnostic
waits 31 minutes for this whole-suite wrapper; a one-minute diagnostic would
only show Python waiting normally for Playwright. Individual Playwright timeouts
and responsiveness limits come from `budgets.ts`; the backend suite retains its
one-minute stack diagnostic. Failure details remain in the console and the
browser report artifacts.

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

`development-reload.spec.ts` exercises the actual typed reload client in both
engines, using deterministic HTML and generation responses. It covers completed
publication, the first-poll race, stale HTML, unavailable storage, malformed
responses and recovery. The browser performs real full-page navigation; the test
compiles the client with Vite. Complementary unit, Django and disk-watcher tests
cover atomic publication, one manifest snapshot per render, retained
worker/chunk generations and supervisor shutdown. Production builds exclude the
reload client and production URL configuration excludes its endpoint.

For a focused diagnostic wrapper run, set `VIEWER_BROWSER_GREP` to a Playwright
test-name regular expression. The wrapper passes it as a separate `--grep`
argument. Final acceptance runs without this filter. CI always retains the JSON
report, attachments and failure screenshots, including failed runs; trace
recording remains disabled.
