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

Controller checks observe both successful initialization and the application's
controller-error event. A reported initialization error fails immediately with
its exception instead of waiting for a ready state that cannot arrive. Error
messages retain URL origins and paths while removing credentials, query strings
and fragments from diagnostics.

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
temporary local root. Canonical project rows, explicit permissions, a mutex, a
read-only fleet, an experiment, and read-only/writable landmark collections
supply actual Django route fixtures without opening remote repositories. The
writable collection has one independently seeded landmark for its edit form.

The wrapper uses `tests.browser.urls`: two explicit revision/tree HTTP fixtures
precede the application URLconf, enforce project permission, and return
deterministic JSON. The wrapper verifies URL resolution before launch. The
browser exercises the actual revision menus and Git tree navigation; transport
fixture headers and request-count contracts belong outside browser assertions.

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
toggles, feedback reset, custom field validation, upload removal, deletion
confirmation, mutex recovery, revision menus, Git tree navigation, country
collapse, exports, experiment retry, and read-only forms. Spreadsheet tools
retain contenteditable keyboard interaction; DMP tools retain visible file
rejection and server-error recovery. Basic Git instructions, fleet and
permission modal open/close/reset wiring belongs to existing controller/template
tests; tag cancellation does not warrant a separate browser startup. Prioritize
consequential regressions over exhaustive variants of the same shared dialog.

`viewer-parity.spec.ts` covers public/read-only composition, visibility changes,
unavailable mutation controls, settings focus, Escape restoration and supported
fullscreen. Measurement and drawing cases exercise keyboard/pointer input,
history, cancellation, discard and tool ownership. Camera cases preserve the
original framing regression viewport; globe cases assert real rendered pixels.
Keyboard measurement first waits for the survey to render and the camera to
settle, then waits for its keyboard pan to finish before placing the endpoint.
`map.loaded()` alone does not establish that the initial fit has finished;
native keyboard input can interrupt it while the map is still at globe scale.
These checks use the existing renderer-idle helper and retain real key input,
unchanged assertions, one worker and zero retries.

`gis-metadata-icons.spec.ts` checks rendered aliases and all landmark icons
after style changes, decoded colored picker previews, independent edit
selection, manual/context-menu creation, visible failures and completion.
Collection forms use a seeded row and intercepted mutations; completion reloads
test navigation, not persistence. Renderer image registration policy and API
persistence are covered by Vitest and pytest respectively.

`viewer-assets.spec.ts` decodes every shared icon in the real manager/context
menu and checks one representative station dialog plus the separate lead and
cylinder dialogs. This exercises the shared dialog template without repeating
its native interactions for every station type. The browser also checks provider
attribution. Build graph, raw TypeScript protection and absence of reload
polling are checked under `make test`, without browser-only metadata/network
assertions. Live provider checks remain opt-in.

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

`viewer-gestures.spec.ts` uses real wheel, pointer and touch input to protect
projection-crossing anchor stability and paused-pinch handoff in private and
public viewers. Small shared geometry replaces the former large-source matrix.
The normal/reduced-motion cases retain natural gesture completion and visible
screen-space stability; source updates and projection configuration remain in
Vitest.

`resource-edit.spec.ts` uses independently seeded note/document responses for
fixed types, native file selection, filename previews, retained input after
errors, retry and completion. It needs no storage service. DOM form
serialization and multipart transport are verified by Vitest; pytest verifies
permissions, immutable types, persisted Unicode/empty values and replacement
file bytes.

`gis-view-bound.spec.ts` checks actual polygon fill, outline and local CJK
labels across style changes, plus the dashboard selector's initial selection,
clear, error recovery and completion feedback. Its database-only fixture creates
no survey artifacts. Vitest verifies clipping, sources and request payloads;
pytest verifies selection, permissions, persistence and public metadata.
