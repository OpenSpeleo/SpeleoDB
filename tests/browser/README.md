# Viewer responsiveness browser checks

Run these tests inside the existing Django application container after a clean
`npm run build`, with other CPU-intensive suites stopped:

```bash
npm run test:browser
```

The suite uses Chromium and WebKit with the real Mapbox renderer, a minimal
local style, deterministic intercepted viewer APIs, and the normal Django
headless login endpoint. It does not create, change, or delete project records.
The stress case loads 60 projects and 120,000 segments. Other cases isolate a
100,000-vertex GPS geometry and nested GIS geometry types. The harness limits
Mapbox to one renderer worker to bound memory in the shared development
container; all fixtures, production application work, and real rendering remain
enabled.

`VIEWER_BROWSER_BASE_URL` defaults to `http://127.0.0.1:8000`.
`VIEWER_BROWSER_EMAIL` and `VIEWER_BROWSER_PASSWORD` default to the documented
local development account. Set them explicitly for a different development
server. Install Playwright's Chromium/WebKit binaries and required system
libraries in the test container before running; no separate Django stack is
started by the suite.

Assertions cover native control state in the first animation-frame callback and
verify that map mutations have not preceded it. A separate nested second-frame
callback measures time from the native change event after an intervening paint
opportunity; that feedback interval must meet the 100 ms p95 budget. All
expected samples must finish before their timings are evaluated. This is an
upper-bound observation around a paint opportunity, not an exact displayed-pixel
timestamp.

Other assertions cover source reuse, rapid reversal during network loading and
worker transfer, failure/retry, and geometry-type filters. A zero-delay timer
samples the single large geometry's parsing/preparation interval until the map
source is first installed, with a 50 ms maximum gap. Renderer source ingestion
is excluded from that preparation sample and remains a separate profiling
concern.

JSON timing attachments and failure screenshots go to the OS temporary directory
(override with `VIEWER_BROWSER_ARTIFACTS`). Network traces are disabled to keep
credentials and session cookies out of artifacts. Do not run performance checks
alongside builds, database suites, or other browser projects. These are local
reference-workload budgets, not claims about arbitrary hardware or data.

On the shared 7.5 GiB development VM, the 120,000-segment stress run exhausted
available memory with GitLab and the other services running (the Django
container recorded one kernel OOM kill). Limiting Mapbox to one renderer worker
still caused severe swapping, so that attempt was terminated. The unchanged
stress case requires a rerun with enough memory; it is not a passing acceptance
result. A separate 4,000-segment settings baseline uses the same assertions and
does not replace the stress case. To run the baseline and overlay cases alone:

```bash
npm run test:browser -- --grep 'settings baseline|GPS toggle|GIS load'
```

The Settings backdrop retains its dark scrim without blurring the live WebGL
canvas. Recorded feedback results use the second-frame interval described above;
earlier first-frame-only observations do not establish the feedback budget.

The final isolated baseline/overlay run on that VM passed both GIS cases and the
Chromium GPS case, and failed three timing cases; the stricter feedback targets
remain unmet:

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
