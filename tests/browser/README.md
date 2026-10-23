# Complex browser workflows

Browser tests cover complex behavior that depends on a real browser: native
input combined with state transitions, asynchronous work and recovery, or
interaction between map tools, dialogs and visibility scopes. Keep real compiled
Django pages, controllers, vendor libraries and MapLibre.

Icon artwork, asset availability, colors, fonts, credits, camera configuration,
static read-only markup, basic validation and simple open/close or button
feedback do not belong in this suite. There are no pixel comparisons, screenshot
color checks or GPU-frame captures. Screenshots are failure diagnostics only.

Backend permissions, persistence, serialization, API contracts and processing
belong in pytest. Frontend logic, form wiring, request payloads, caching,
scheduling, renderer configuration and asset contracts belong in Vitest. Both
lower layers run under `make test`. Removing cosmetic browser coverage does not
claim that a unit test certifies browser pixel output.

## Retained workflows

| File                            | Scenarios per engine | Browser-specific failure protected                                                                                                                                             |
| ------------------------------- | -------------------: | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `controllers-parity.spec.ts`    |                    2 | Native file removal or rejected upload loses retained state; contenteditable Tab navigation and row operations lose focus or data.                                             |
| `viewer-gestures.spec.ts`       |                    4 | Wheel/projection crossings change pan direction; releasing one touch loses the remaining contact.                                                                              |
| `viewer-parity.spec.ts`         |                    5 | Public/private composition or country/project gates lose visibility across changes; focus/fullscreen interaction, measurement cancellation, or drawing history/discard breaks. |
| `viewer-responsiveness.spec.ts` |                    2 | Pending GPS work ignores the final toggle intent; failed GIS loading cannot recover or preserve independent geometry visibility.                                               |
| `resource-edit.spec.ts`         |                    1 | Rejected note/file editing loses input or the native file selection and cannot complete after recovery.                                                                        |
| `gis-view-bound.spec.ts`        |                    1 | A public boundary disappears when changing sources, or a rejected bound selection loses its draft before retry.                                                                |

All 15 scenarios run in Chromium and WebKit, serially with one worker and zero
retries. Use one representative of shared form/table implementations. Additional
browser variants need a distinct complex failure, rather than another icon,
color, value or page using the same controller.

Use small deterministic HTTP responses and loading gates. The map fixture has
two small surveys, a short GPS line and tiny nested GIS geometry. Provider
styles and ESRI tiles stay local while the actual renderer and raster decoding
remain real. Never manufacture a loading delay with large inputs or fixed
sleeps. Rendered feature visibility and renderer-idle checks support workflow
assertions and native pointer targeting; private source counters are not browser
evidence.

Controller readiness observes the normal bootstrap and reports initialization
errors immediately. Authentication is reused once per worker; every test has a
fresh browser context and independent preferences. Controlled mutations exercise
visible recovery without proving backend persistence through write/readback
chains. Resource editing starts from independently seeded responses.

## Running

Run in the existing application container with other CPU-intensive checks
stopped, after a checked production build:

```bash
bun run build
pytest tests/browser/test_django_browser.py --gitlab-audit-deny-create \
  -o faulthandler_timeout=1860 --durations=20
```

Install matching Chromium/WebKit binaries and system libraries first. The
wrapper uses PostgreSQL and pytest's isolated test database. If the local test
dotenv selects a different connection, set `TEST_DATABASE_URL` explicitly; never
point tests directly at the development database.

The wrapper uses Django's normal URL configuration and standard `collectstatic`
with a temporary static root. It creates a verified user and public GIS view.
Native upload needs one canonical ADMIN project, explicit permission and mutex;
the geographic-bound workflow owns its database-only records. No Git remote is
prepared, and no browser-only Git/revision transport fixtures are installed.

Use `VIEWER_BROWSER_GREP` with the wrapper for focused checks. Direct browser
runs default to `http://127.0.0.1:8000`; `VIEWER_BROWSER_BASE_URL`,
`VIEWER_BROWSER_EMAIL` and `VIEWER_BROWSER_PASSWORD` can select an existing
application and account. Database-backed scenarios need the wrapper.
`bun run test:browser --list` verifies discovery.

## CI and timing

The independent browser job uses its own PostgreSQL service and the official
Playwright Noble image. Keep that image version equal to `@playwright/test` in
`package.json`. Browsers and their system libraries are preinstalled; only the
small `unzip` package is needed by `setup-bun`. Do not reintroduce a large
`playwright install --with-deps` step. PostgreSQL uses the service hostname
inside the job container. Controlled provider responses need only a dummy Mapbox
token; no real provider, GitLab, S3 or Redis service is required.

Ordinary desktop cases use 1280×800 at one device pixel per CSS pixel. Mobile
and gesture cases use their explicit viewport/input settings. Reduced motion
avoids unrelated initial camera flights; native gesture cases explicitly select
their motion policy and retain natural completion and their original geometric
assertions.

JSON results and failure screenshots go to the OS temporary directory,
overridable with `VIEWER_BROWSER_ARTIFACTS`. Traces remain disabled so artifacts
do not retain session cookies or credentials. The pytest wrapper streams case
progress, preserves the GitLab audit environment and terminates its browser
process group after the existing deadline. CI denies GitLab project creation and
uploads its separate audit artifact.

The total browser CI job target is 10–12 minutes, with 1–2 minutes for browser
environment setup. Report install/build, pytest setup/call/teardown and browser
wall time separately. Compare the same command, worker count, database lifecycle
and services. Investigate slow workflows and reduce unnecessary work; do not
hide cost behind skips, retries or additional workers. Centralized timeouts in
`budgets.ts` remain hang guards. Scale/performance benchmarks require explicit
authorization and stay outside this workflow suite.
