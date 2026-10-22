# Browser UI/UX checks

Chromium and WebKit exercise behavior that requires a real browser: rendered
maps and icons, native input, keyboard navigation and focus, dialogs,
fullscreen, loading feedback, visible validation, and recovery after a server
error. The suite uses real compiled templates, controllers, vendor libraries and
MapLibre.

Application correctness belongs under `make test`: pytest owns backend
validation, permissions, persistence, serializers, API contracts and processing;
Vitest owns frontend logic, payloads, request counts, caching, scheduling,
workers and renderer configuration. Before adding a browser test, name the
browser-specific regression it protects and check for existing lower-layer
coverage. Before removing an application-logic assertion from a browser test,
verify the lower-layer replacement or add the missing test.

For example:

| Browser UI/UX assertion                                                      | Lower-layer responsibility                                                                                                               |
| ---------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| Selecting an icon updates the picker and displays a decoded colored preview  | Vitest verifies form payloads and renderer image sizing/collision configuration; pytest verifies accepted icons and database persistence |
| A failed GIS download shows an error and the retry restores visible geometry | Vitest verifies request deduplication, failed-cache cleanup and stale response handling                                                  |
| A hidden project disappears from the rendered map                            | Vitest verifies visibility composition, cached depth work and absence of source rewrites                                                 |
| Deletion opens a confirmation dialog and presents a rejection                | Vitest verifies no request before confirmation and the exact DELETE/CSRF contract; pytest verifies authorization                         |
| Removing an upload updates the selected-file list                            | Vitest inspects the multipart body; pytest verifies processing and storage                                                               |

Use small deterministic data and controlled HTTP responses. Shared map fixtures
contain two small representative surveys, a short GPS line, and tiny nested GIS
geometry examples. Hold a response behind a gate when testing interaction during
loading; do not manufacture loading time with large inputs or fixed sleeps.
Database-only fixtures and real authentication are allowed to render real pages,
but browser tests must not prove persistence through API write/readback/reload
chains. Controlled mutations select the UI response without modifying real
application records. Seed editing independently of creation.

Actual rendering, image decoding and native interaction remain real. Renderer
readiness checks are appropriate for pointer targeting and visible map results;
private source counters, layer expressions and worker messages are not UI
assertions. Do not replace meaningful readiness with forced clicks.
Authentication storage state is reused once per worker, while each test receives
a fresh browser context and independent preferences.

The former large-data settings and GPS latency benchmarks are intentionally
removed from routine browser CI. Unit tests retain large-data preparation,
bounded worker transfer, cancellation and cooperative yielding contracts. Those
checks do not establish real-browser latency at scale. Adding an opt-in
performance suite or putting scale workloads back into default browser CI
requires explicit authorization.

## Running the suite

Run checks in the existing application container after a successful checked
production build, with other CPU-intensive checks stopped:

```bash
bun run build
pytest tests/browser/test_django_browser.py --gitlab-audit-deny-create \
  -o faulthandler_timeout=1860
```

Install the Playwright Chromium/WebKit binaries and required system libraries
before running. Use PostgreSQL for the live-server wrapper, as CI does. Set
`TEST_DATABASE_URL` to the existing PostgreSQL connection when the local test
dotenv selects SQLite; pytest uses its isolated test database. Concurrent viewer
requests cannot safely share an in-memory SQLite connection.

The harness starts Django through pytest's live-server fixture, creates a
verified database-only user, and passes generated credentials through the child
environment. Standard `collectstatic` collects the compiled assets into a
temporary local root. Canonical project rows, explicit permissions, a mutex,
fleets, an experiment, and read-only/writable landmark collections supply actual
Django route fixtures without opening remote repositories. The writable
collection has one independently seeded landmark for its edit form.

The wrapper uses `tests.browser.urls`: two explicit revision/tree HTTP fixtures precede the
application URLconf, enforce project permission, and return deterministic JSON.
The wrapper verifies URL resolution before launch. The browser exercises the
actual revision menus and Git tree navigation; transport fixture headers and
request-count contracts belong outside browser assertions.

For map cases that do not need database-backed route fixtures, a running
application can also be targeted directly:

```bash
bun run test:browser --grep 'settings|GPS loading|GIS load'
```

`VIEWER_BROWSER_BASE_URL` defaults to `http://127.0.0.1:8000`.
`VIEWER_BROWSER_EMAIL` and `VIEWER_BROWSER_PASSWORD` default to the documented
local development account. Override them for a different development server. Use
`VIEWER_BROWSER_GREP` with the pytest wrapper for focused checks requiring its
database fixtures. `bun run test:browser --list` verifies discovery.

## Coverage and timing

The suite retains one worker, zero retries, and both engines. Investigate any
individual execution over five seconds, but do not weaken coverage to force it
under that number. Optimize duplicated setup, fixture size and non-UI assertions
before increasing workers or runner resources. Keep existing centralized timeout
limits in `budgets.ts`; a timeout is a hang guard, not an acceptable latency
measurement or performance guarantee.

The JSON report records each execution's duration and status. Sort durations
descending and assess slow cases individually. Compare equivalent environments,
commits and browser versions, and report setup/build/install time separately
from Playwright execution. Failed or skipped cases do not count as speed wins.
Use ordinary subsequent CI runs to check repeatability rather than adding CI
load solely to collect timing samples.

`controllers-parity.spec.ts` covers actual public/private menus, preference
toggles, feedback reset, custom field validation, fleet dialogs, upload removal,
permission dialogs, deletion confirmation, mutex recovery, revision menus, Git
tree navigation, country collapse, tags, exports, experiment retry, and
read-only forms. Spreadsheet tools retain contenteditable keyboard interaction;
DMP tools retain visible file rejection and server-error recovery.

`viewer-parity.spec.ts` covers public/read-only composition, visibility changes,
unavailable mutation controls, settings focus, Escape restoration and supported
fullscreen. Measurement and drawing cases exercise keyboard/pointer input,
history, cancellation, discard and tool ownership. Camera cases preserve the
original framing regression viewport; globe cases assert real rendered pixels.

`gis-metadata-icons.spec.ts` checks rendered aliases and all landmark icons
after style changes, decoded colored picker previews, independent edit
selection, manual/context-menu creation, visible failures and completion.
Collection forms use a seeded row and intercepted mutations; completion reloads
test navigation, not persistence. Renderer image registration policy and API
persistence are covered by Vitest and pytest respectively.

`viewer-assets.spec.ts` checks the real context menu and station, lead and
cylinder dialogs, shared icon decoding and provider attribution. Build graph,
raw TypeScript protection and absence of reload polling are checked under
`make test`, without browser-only metadata/network assertions. Live provider
checks remain opt-in.

The report and failure screenshots go to the OS temporary directory, overridable
with `VIEWER_BROWSER_ARTIFACTS`. Network traces remain disabled to keep session
cookies and credentials out of artifacts. The pytest wrapper streams per-case
progress, terminates the browser process group after its 30-minute deadline, and
preserves the GitLab audit environment. CI supplies dummy GitLab/storage
settings and denies remote project creation; its audit artifact remains separate
from the backend suite's artifact.

CI's **Chromium and WebKit** job runs independently of backend tests with its
own PostgreSQL service, locked dependencies and checked asset build. It needs no
GitLab token, S3 or Redis service. Keep this ownership boundary: `make test`
validates application logic; browser CI validates UI/UX.

Additional UI regression suites introduced upstream cover projection-crossing
gestures, resource edit forms and GIS View geographic bounds. Their browser
coverage must retain real input and visible output while application processing,
request bodies and persistence remain owned by pytest and Vitest.
