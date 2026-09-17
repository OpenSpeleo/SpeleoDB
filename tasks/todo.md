# Task reviews

## Folded map cards and lighter GIS Geometry

Projects, GPS Tracks, GIS Layers, and GIS Geometry now share a 160 × 48 px
folded card size. Chromium verified identical chevron/label offsets and no
overflow using production CSS. GIS Geometry polygon opacity is halved to 17.5%
when saved and 9% in the editor, with constants centralized and no new UI
control.

See [the follow-up checklist](todos/folded-map-panels.md).

## GIS Geometry

Implemented private line/polygon authoring, shared GIS Layer management
patterns, direct-user access, editable GeoJSON, revision-safe persistence, and a
native Mapbox draft editor. One JSON contract supplies both Python and
JavaScript with the 30 km² bounding-box maximum, 8 km² warning, supported types,
and vertex/coordinate limits; paired runtime tests verify those values against
the same source.

The viewer starts geometry hidden, fetches coordinates on demand, preserves
drafts after failed saves, and restores saved visibility on Revert. Creation
lives beside Import GPS, overlay sections use consistent chevrons, and camera
framing accounts for the inspector, panels, and visible viewport. The mobile
sheet keeps its actions reachable during scrolling, keyboard use, and
fullscreen.

Verification: 1,155 JavaScript tests pass. The full Python run passed 4,863
tests with 178 skips and found one native Node JSON import failure, fixed and
verified in a final PostgreSQL run of 67 tests plus three subtests. Ten final
private-page tests pass. GitLab audit stayed at nine creations and ten POSTs,
with zero violations/unresolved outcomes and verified deletion marks for all
nine. Repository hooks, types, migrations, clean builds, and real browser
workflows pass. See [the feature review](todos/gis-geometry.md) and
[design documentation](../docs/gis-geometries.md).

## Local GitLab stale branch-protection cache

Diagnosed an empty protection-rule list with a stale `protected=true` result in
local GitLab 18.7. Invalidating only the affected project's cache restored
branch push authorization. Local bootstrap now configures unprotected default
branches on the dedicated test group, avoiding the initial protection/deletion
transition for disposable repositories. Normal UUID-based manager provisioning
is retained.

The focused container run passed 52 tests with four skips, including all
reported uploads, lease restoration, and real repeated bootstrap. Audit: four
creations and POSTs, zero violations or unresolved outcomes, and verified
cleanup for all four repositories. Ruff, formatting, combined mypy, and diff
checks pass. See [the review](todos/gitlab-protected-push.md).

## Reuse production GitLab repository provisioning

Removed the pool's custom remote naming, Git initialization, and commit
authorship. It now delegates to `GitlabManager.create_or_clone_project()`, using
ordinary UUID names and initial commits. This fixes the supplied CI job's
duplicate-name HTTP 400 failures without adding another fixture-specific
provisioning path.

The full Python suite passed 4,568 tests with 178 skips inside the existing
container. Audit: nine creations, ten POSTs, zero violations or unresolved
outcomes, and verified deletion marks for all nine repositories. Focused tests,
Ruff, formatting, mypy, and diff checks pass. See
[the review](todos/ci-gitlab-project-names.md).

## CI dashboard and dark document assertions

Updated stale inline-style assertions to check dashboard utility classes and
replaced exact meta-tag strings with parsed HTML contract checks. All 84 tests
in the affected Python modules and all 1,040 JavaScript tests pass in the
existing application container. JavaScript lint, focused Ruff/formatting, mypy,
and diff checks pass. GitLab audit: zero creations/POSTs, violations, or
unresolved outcomes; no cleanup required. See
[the review](todos/ci-template-contracts.md).

## Pytest concurrency across branches

Pytest uses a branch-specific job concurrency group with cancellation disabled.
Manual cleanup preserves repositories younger than 24 hours, and pytest jobs
have a 60-minute limit. This replaces the global test/cleanup lock while
retaining serial workers and each invocation's nine-repository budget. At the
user's request, the cron trigger was removed; cleanup is available only through
`workflow_dispatch`. Container YAML checks verified the manual-only trigger.

All 11 focused container tests passed, including real GitLab preservation and
deletion. Ruff, formatting, mypy, YAML/policy checks and diff checks passed. The
audit recorded one creation/POST, zero violations or unresolved outcomes, and
verified cleanup. Update cleanup on the default branch before enabling parallel
runs on other branches. See [the review](todos/pytest-branch-concurrency.md).

## Django tests reuse four GitLab repositories

Ordinary Git integration tests now reuse four canonical project identities with
isolated database rows and local checkouts. Five self-contained lifecycles
retain creation/deletion coverage. A mandatory transport guard enforces nine
cumulative creations, tracks each request through subprocesses, and publishes
cleanup evidence. CI preflight is read-only, and CI shares a concurrency key
with scheduled cleanup.

The final Python suite in the existing container passed **4,526 tests**, with
178 configured skips, creating **nine repositories across ten POSTs**. The extra
POST was an intentional HTTP 400. There were zero violations or unresolved
outcomes, and all nine repositories had verified deletion marks. PostgreSQL
rollback/pool checks, all five live-worker tests, 1,010 JavaScript tests, mypy,
and Ruff within the existing CI scope also passed. AGENTS.md now preserves this
contract. See
[the analysis and measured review](todos/gitlab-test-repository-budget.md) and
[the test architecture](../docs/ci-gitlab-testing.md). The
[adversarial review](todos/gitlab-budget-adversarial-review.md) fixed
lost-response cleanup and failed-reset isolation; all pre-commit hooks passed.

## Official GitLab image and patch updates

Connected the existing Railway test GitLab service to the official
`gitlab/gitlab-ce:19.3.2-ce.0` image. Startup files now persist on its existing
volume and Railway has an explicit start command. A pre-migration volume backup
exists; patch-only updates are configured for 09:00–10:00 UTC daily.

Deployment `8fd607fd` reached SUCCESS. HTTPS, the existing repository commit,
root password, and original CI token records survived. Authenticated API
create/read/delete verification passed, and its temporary token was revoked.
Both Linux startup tests passed. See
[the image migration review](todos/gitlab-official-image.md).

## GitLab cleanup protocol and repeated runs

The test cleanup Makefile target now selects test settings, avoiding local
settings' forced HTTP and Railway's HTTP-to-HTTPS redirect. The SDK rejected
that redirect after GitLab accepted the first deletion. Cleanup now reports safe
error details and skips projects already marked for deletion, which otherwise
return HTTP 400 on a subsequent run. All 10 real cleanup tests passed, including
the actual Makefile entrypoint, repeat cleanup, and invalid-token failure.
Direct Ruff, formatting, and mypy passed; no hooks ran. See
[the cleanup review](todos/gitlab-cleanup-protocol.md).

## CI progress masking and portable Git errors

Created the GitLab group-ID Actions variable and updated CI and cleanup to read
it. Deleted the obsolete secret at the user's explicit request; the local commit
must be pushed before the next CI or cleanup run. The checkout regression
accepts both observed missing-tree messages while checking the exact failed
operation, SHA, exit status, and unchanged history. All five real
checkout/history tests passed, alongside Ruff, formatting, and mypy. See
[the migration review](todos/ci-progress-and-git-diagnostics.md).

## Restore local validation after GitLab test migration

Corrected the five PostgreSQL-only rollback tests with temporary owner-scoped
unique constraints enforced by both SQLite and PostgreSQL. Corrected the 49
static endpoint failures by opting eight static/discovery views out of request
transactions, preserving their database-free contract. All 60 targeted cases
passed on both engines; no reported failure was skipped or weakened to a generic
response assertion.

Mypy's normal command had raised a malformed SQLite cache error in the shared
checkout. Cache ownership now follows the invoking user's home outside that
mount; direct host and container checks pass with cold and warm caches. Ruff and
formatting pass for the changed Python files. No hooks were run, as explicitly
requested. See [the regression review](todos/local-test-regressions.md) and
[cache evidence](../docs/mypy-cache.md).

## CI GitLab quotas and real upload verification

GitLab acquisition now looks up existing projects before creating them, and
upload error cleanup opens only an existing working tree. Tests require the
intended Git/GitLab/storage/database failure and verify persisted transaction
results. Real frontend uploads reach Django and the configured storage service.
These changes remove redundant creation traffic and prevent unrelated GitLab
outages from satisfying error-path assertions.

An always-on GitLab CE service is deployed at `https://gitlab-test.speleodb.org`
in Railway's isolated `test` environment. Authenticated API access, HTTPS
push/fresh clone, and actual bounded 429 responses were verified. Its database,
repositories, and configuration share a 5 GB persistent volume. Signup is
disabled, test project/group creation quotas are disabled, and deleted test data
has one-day retention. The administrative bootstrap token was revoked and
removed; CI uses the user-owned `github CI` token in group `github-ci`. GitHub
secret-update timestamps were verified, but secret plaintext is unavailable and
no effective Actions run has been verified.

Final deployment `3debd5be-5a0b-4299-af87-e00e6b0ad39a` reached `SUCCESS` at
21:38:47 UTC. Root login and the private repository persisted; a fresh HTTPS
clone after restart matched the original SHA and file bytes. Temporary
verification credentials were revoked and the smoke project scheduled for
deletion; the user-owned CI token remains active.

Targeted integration groups passed, but full-suite validation remains open. The
local pytest run stalled at about 77% with four failures and one error and is
being interrupted for diagnosis and targeted reruns. Do not report the full
suite as passing.

See [the task review](todos/ci-gitlab-rate-limit.md),
[the test design](../docs/ci-gitlab-testing.md), and
[the Railway deployment](../docs/gitlab-test-railway.md).

## Post-commit timeout test isolation

The hook timeout test's sleep mock intercepted Python subprocess polling via the
shared stdlib `time` module. Retry tests now replace only the retry helper's
module reference; real process cleanup retains its sleep. The hook regression
also asserts exactly one commit invocation. Application behavior is unchanged.
All four affected modules passed inside Docker: 70 tests and 31 subtests.

See [the review](todos/post-commit-timeout-sleep.md) and
[test isolation design](../docs/git-retry-testing.md).

## Plain export files and shared storage managers

The subsequent caching decision keeps the existing CloudFront managed policies.
The user accepts caching; documentation no longer requires a custom policy or
zero minimum TTL. Signed access and URL expiry remain required on cache hits.
Export uploads now reuse the shared `public, max-age=86400` metadata; only the
authenticated redirect retains no-store. Cache-header verification passed 85
storage/API tests and the isolated live export case, plus full mypy and Ruff.
See [the cache-header review](todos/export-cache-headers.md).

This review supersedes the earlier export version-tracking and CloudFront query
requirements below. Exports overwrite the existing key and use ordinary signed
URLs. The new migration removes the obsolete fields, and setup removes obsolete
version permissions and retention rules.

Every S3 backend now shares transport and endpoint handling through
`BrowserFacingS3Storage`, with common public/private classes. Local and CI
RustFS use rc.1 to fix stored headers missing from GET responses for all
backends. Existing file naming and access/cache policies remain with their
owning classes.

Verification: 256 targeted tests passed, followed by all 5 live Celery tests;
the eight-backend integration matrix includes actual transfers, overwrites,
headers, unsigned/private access and cleanup. Full mypy (710 files), Ruff,
formatting, migration drift checks, YAML checks and policy parity passed. Local
RustFS was upgraded with its volume preserved and pre-upgrade object integrity
verified. No production AWS settings were changed. See
[the completed plan](todos/plain-export-files.md).

## Pytest collection scope

Default collection now searches the six source roots and inherits pytest's
directory exclusions. Docker profiling identified 58,800 `.workdir` directory
scans as the main cost. Collection fell from 36.80 to 1.83 seconds; the complete
profiled invocation fell from 39.87 to 3.73 seconds. All 4,619 ordered node IDs
match after normalizing five existing random parameter labels. Only collection
ran; test bodies and database setup were not exercised.

See [the collection review](todos/pytest-collection-performance.md) and
[discovery documentation](../docs/pytest-collection.md).

## Bounded retries and CI hang

The diagnostic CI stack identified python-gitlab's server-directed retry sleep
during project creation. Retry attempts/delays and subprocess cleanup are now
bounded across GitLab, Git, startup, and export recovery. Durable counters keep
periodic sweeps from resetting failure budgets. See
[the retry review](todos/bounded-retries.md) and
[design](../docs/bounded-retries.md).

The user's typing/lint reports were corrected. Direct checks inside Docker
passed: mypy on 705 source files and Ruff on `speleodb`, `config`, and
`compose`. Tests and full hooks were not rerun. Earlier test results below
predate these retry changes.

## Export storage reuse and flat filenames

Exports now use the shared private storage backend: CloudFront signing in
production, browser-facing S3 signing locally, and generic streaming upload and
version cleanup operations. New keys are flat exports/{filename}.zip and use
unique attempt IDs; historical nested keys remain supported. Existing public
backends retain their unsigned URLs. No schema migration is needed.

Validation completed with 139 targeted tests passed, 1 skipped, full mypy, and
Ruff on task-owned files. Independent review found no actionable regression. The
complete production policy and CloudFront configuration steps are prepared. Live
reads proved missing version/cleanup permissions and dropped version query
parameters; production rollout requires those external AWS settings first.

See [the storage review](todos/export-shared-storage.md) for verification scope,
live evidence, and deployment prerequisites.

## CI Compose test environment

Fixed missing runner-side PostgreSQL administrator variables and the reloader
probe's missing Django secret. The 12 reported failures now pass in Docker;
related tests finished with 51 passed and one root-only skip. Ruff, full mypy,
and workflow YAML validation passed.

See [the completed plan](todos/ci-compose-test-environment.md) for reproduction,
verification scope, and review details.

## CI GitLab initial commit

Added a bounded retry for HTTP 404 on the first commit in a newly created GitLab
test project. Real HTTP regression tests and the live archive module passed: 45
tests total. Ruff and full mypy passed; review found no blockers.

See [the completed plan](todos/ci-gitlab-initial-commit.md) for hosted CI
evidence, retry scope, and verification limits.

## Railway background service rollout

Deployed Celery-Worker, Celery-Beat, Kanchi, and the updated production web
service. All exact deployments reached `SUCCESS` on the intended application
commit or pinned Kanchi image. Git source read-back confirms `master`, enabled
GitHub checks, and no fixed application commit pin. Following the user's scope
corrections, no environment-wide shared variables remain. All four services
reference Redis's broker variable; Kanchi references PostgreSQL's private
hostname and keeps its own database/authentication credentials. The web
service's `KANCHI_URL` references Kanchi's public domain. Sensitive values use
`preserve()` in IaC.

Redis durability settings, Kanchi's dedicated database/role, application
migration state, and periodic schedule installation are verified. Kanchi has
deployed successfully. Its custom hostname/DNS and certificate are verified,
HTTPS health returns 200, and its protected config API rejects anonymous access
with 401. The operator's settings were preserved, credentials sealed, and
pending shared username cleared. Kanchi reaches the private Redis broker on
database 1 and stores 30-day task retention with daily 03:00 UTC cleanup
enabled. Its first automatic cleanup succeeded, and workflow automation remains
disabled.

One worker consumes both intended queues, one PostgreSQL advisory-lock owner
holds the Beat scheduler lock, and Beat dispatched maintenance and artifact
cleanup. Read-only application tasks succeeded in Django's results and appeared
as successful in Kanchi; a normal web `.delay()` dispatch also succeeded.
Effective deployment manifests preserve the intended commands, web schedule
installation, and worker/Beat 120-second draining. The initial copied broker URL
was corrected to direct owner-service references, with exact rendered URL
equivalence verified before deleting the shared copy. Container Railway
typechecking and `git diff --check` passed. Harmless normalized-default plan
differences did not trigger repeat applies.

The infrastructure rollout is complete. Successful login using the operator's
sealed password was not tested; login UI availability and anonymous API
rejection were verified. Real-account export, email, and full expiry-cycle
checks are separate future operator smoke tests. See
[the completed rollout plan](todos/railway-background-rollout.md) for exact
deployment IDs, task evidence, and verification limits.

See [the reference correction review](todos/railway-reference-wiring.md) for raw
variable expressions, all-service consumer inventory, post-deletion equivalence,
and successful live Redis/PostgreSQL and HTTP checks. The reference correction
required no restart. A subsequent operator Git push queued web, worker, and Beat
releases behind GitHub checks, confirming their automatic deployment wiring.

## Django clock consistency

Fixed both reported retry-budget failures: centralized job/attempt creation now
uses explicit Django timestamps, with the same instant for attempt creation and
initial dispatch. The repository audit also corrected five captured factory
callbacks and aligned OGC timestamps, the debug cachebuster, and storage expiry
assertions with `timezone.now()`.

Verification: 167 distinct tests passed, 1 skipped; the final factory-only rerun
also passed all three cases. Full mypy checked 708 source files, and Ruff and
format checks passed. Independent review found no actionable issue. No schema
migration is needed. See
[the completed review](todos/retry-budget-test-clock.md).

## Complete shared storage policy and setup

The production storage document now embeds the complete three-statement policy,
and its JSON example matches exactly. Application version/multipart actions and
CloudFront version reads extend the existing bucket-wide grants. Production
setup reuses those grants and removes only recognized obsolete export policies.
Downloads use the existing shared signed-URL flow. Only retention is scoped to
exports, keeping other files out of the two-day cleanup rule.

Local setup now merges that same lifecycle fallback while preserving unrelated
rules, private exports, public photos, and versioning settings. Verification: 40
production policy/command tests plus 23 local setup and real storage tests
passed; full mypy checked 708 source files, and Ruff/format checks passed all
task-owned Python files. Independent review found no actionable issue. No live
AWS configuration was changed. See
[the completed review](todos/shared-storage-policy.md).

## Generic AWS policy identifiers

Replaced production account, distribution, IAM identity, and bucket identifiers
in the full policy documentation/examples with explicit placeholders. Commands
quote placeholders and the existing example test substitutes fictional values.
The example test, full mypy (708 files), Ruff, formatting, JSON parity, and the
repository identifier search passed. See the
[privacy correction review](todos/shared-storage-policy.md).

## Upload Sentry reporting review

Git, file-processing, and input-processing failures now explicitly report to
Sentry regardless of HTTP status. Input rejection messages, DRF parsing errors,
optional conversion/storage failures, and Git cleanup errors are covered while
preserving response and rollback behavior.

Container verification: 33 tests passed, one existing PostgreSQL-only test
skipped; Ruff/formatting and full mypy (725 files) passed. The final GitLab
audit recorded two creations/two POSTs, zero violations or unresolved outcomes,
and both repositories marked for deletion by session cleanup. Independent review
completed. Production ingestion/alert delivery remains unverified; no deployment
was performed. See the [completed review](todos/upload-error-reports.md).

## Railway configuration authority review

Removed the deprecated `railway.toml` and its Docker build-context exception.
`.railway/railway.ts` is now the sole service configuration in the repository;
`railpack.json` retains image-build ownership. Updated operational documentation
and agent guidance while preserving existing commands and IaC ownership.

Container Railway TypeScript validation and `git diff --check` passed. Read-only
live configuration checks found no custom legacy config path for the managed
production services or staging web service. No deployment or infrastructure
mutation was performed. See the
[completed review](todos/railway-config-authority.md).

## djLint template review

Reviewed, repaired, and individually staged 108 changed templates after enabling
HTML pre-commit checks. All 112 tracked HTML files pass both djLint hooks and
Django compilation. Container validation: 1,032 JavaScript tests, 19 Django
render tests, JavaScript lint, Python test lint/type checks, and a clean Vite
production build passed. GitLab audit: zero requests/creations, violations, or
unresolved allocations; no remote cleanup needed. Fixed invalid nesting and
preserved permissions, form actions, model colors, modal visibility, and map
controls. See [the completed plan](todos/djlint-template-review.md) and
[template linting design](../docs/template-linting.md).

## Current logo asset documentation review

Updated `docs/logo-assets.md` to name `logo-sdb-dark.svg` and
`logo-sdb-light.svg`, both with blue `#3852fc`. Their lettering and icons are
white (`#ffffff`) and almost-black grey (`#111111`), respectively. Container
verification confirmed documented colors, dimensions, path geometry, and
embedded-icon filtering. Artwork was unchanged. See
[the completed review](todos/logo-assets-current-palette.md).

## USAH Institute logo review

Created `logo-usah-dark.svg` and `logo-usah-light.svg` with the original Meedori
Sans Light typography. `USAH` uses white/almost-black and `Institute` uses the
shared blue `#3852fc`. Existing icon and tagline artwork is preserved; the
canvas is wider to fit the new wording. Both browser previews were inspected,
container SVG checks passed, and all 1,032 JavaScript tests passed before the
A/H correction. The A and H now use complete letterforms; tests were not rerun
for this correction, per user request. See
[the completed plan](todos/usah-logos.md) and
[asset documentation](../docs/logo-assets.md).

## Project edition and upload controls review

Enable Project Edition now acquires the lock directly and immediately reloads
the current page after success. The shared mutex helper prevents duplicate
pending actions; all project pages share one error modal. Upload Revision and
Enter use the same native form submission handler, preserving files/title on
validation or API errors.

Container verification: 1,040 JavaScript tests and 57 focused Django tests
passed, along with root JavaScript lint, focused Ruff/mypy, template
formatting/lint, and a clean Vite build. Verified all 99 manifest outputs and
exact changed-controller bytes served by Django. Restored the development
watcher after production asset verification. GitLab audit recorded zero
creations/POSTs/violations/unresolved allocations; no remote cleanup needed.
JSDOM covers submit/reload calls rather than actual browser Enter/navigation.
See [the completed plan](todos/project-edition-upload-controls.md) and
[feature design](../docs/project-edition-and-upload.md).

## Required user names and Git authorship review

Require nonblank names in account writes and enforce the invariant in SQL. The
migration repairs legacy names to `NO NAME`; supervised Git commits also fall
back for stale/invalid author names while retaining email and committer. Admin,
CLI, headless signup, and post-sanitization profile updates are covered.
Existing nameless test fixtures now provide names explicitly.

Container full suite: **4,796 passed, 178 skipped**. An additional 348
PostgreSQL user/profile tests passed, as did the real Ariane upload regression,
application Ruff, full mypy, Django system checks, and migration drift checks.
GitLab audit: **9 creations / 10 POSTs**, zero violations or unresolved
outcomes; all nine repositories have verified deletion marks. Broad root Ruff
also reports 44 pre-existing issues in untouched `bin/squash_dependencies.py`.
Final evidence is in [the task review](todos/required-user-names.md). See
[the design and rollout notes](../docs/user-identity.md).

The requested adversarial review found no actionable application issues. Its
final full container run passed 4,796 Python tests (178 skipped) and all 1,040
JavaScript tests. The repeat GitLab audit stayed at nine repositories and ten
POSTs with no violations or unresolved outcomes; deletion marks were verified.
Final `prek run -a` passed every hook after test-lint and formatting fixes.

# GIS Geometry visibility controls review

Replaced the bare geometry checkboxes with the existing map panel toggle markup
and shared styling. Label activation, visibility state, loading locks, and edit
locks are covered. All 1,156 JavaScript tests, lint, and the clean production
build pass in the application container; Chromium confirmed the rendered
switches in both states. See [the task](todos/geometry-visibility-toggles.md).

# Geometry creation defaults review

Swapped the toolbar actions to Create Geometry, Import GPS. New drafts randomly
select from the existing server-provided palette once when opened; editing keeps
the stored color. All 1,158 JavaScript tests, lint, and the clean production
build pass in the application container. See
[the task](todos/geometry-creation-defaults.md).

# Live toolbar refresh review

Confirmed the running development server was serving cached pre-swap markup.
Restarted it with automatic reload enabled and verified actual browser positions
at desktop and mobile widths: Create Geometry is left of Import GPS. See
[the reproduction and verification](todos/geometry-toolbar-live-refresh.md).

# Backend GIS menu order review

Historical placement below is superseded by
[GIS navigation section](todos/gis-navigation-section.md).

Reordered the existing sidebar blocks to My GIS Geometries, My GIS Layers, then
My GPS Tracks. Verified the actual authenticated HTTP response from the running
server. Template lint and all 1,158 JavaScript tests pass. See
[the task](todos/geometry-menu-order.md).

# GIS Geometry export review

Account exports now include each readable active GIS Geometry as stored GeoJSON
in `geometries/`, with revision and metadata in the manifest. Imported layer
files use `layers/`; new archives identify the layout as format version 2. The
existing permission snapshot, staging, checksums, progress, and archive upload
are reused.

Passed 69 focused Python tests, 1,158 JavaScript tests, all applicable
pre-commit checks, and the clean Vite build inside the running container.
Confirmed the live export page lists six datasets. See
[the task](todos/gis-geometry-export.md).

# GIS Geometry adversarial review

Three reviewers covered backend authorization/validation, editor interactions,
and frontend integration; the main review covered exports and final integration.
Corrected gesture boundaries, keyboard focus/activation, GPS updates at the
vertex cap, and metadata retry races. Added real PostgreSQL concurrent-writer
tests. The user's architecture correction removes the GIS-only generic
permission view and serializer base: Geometry uses explicit typed endpoints and
the existing shared validators, while GIS Layer's original implementation is
restored.

All 4,870 Python tests (181 skips), 1,174 JavaScript tests, and 79 PostgreSQL
tests (plus three subtests) passed. The full GitLab audit stayed within nine
creations and ten POSTs, with zero violations/unresolved outcomes and confirmed
deletion marks for all nine repositories. Real Chromium verified the
keyboard/GPS/save flow, visibility focus, direct-link close behavior, editing at
the vertex cap, and mobile controls using the clean production build. Final
full-suite and pre-commit evidence is recorded in
[the review task](todos/gis-geometry-adversarial-review.md).

# GIS Geometry second adversarial review

The requested independent second pass found and fixed three asynchronous
failures: conflict reload could discard a replacement editor, clipboard
completion could access a closed/replaced draft, and an older failed detail
request could overwrite a newer save's visibility. Existing session/cache
boundaries now guard those completions, with eleven additional regressions.

All 1,185 JavaScript tests and 4,870 Python tests (181 skips) passed. Chromium
reproduced the conflict-reload and delayed-clipboard flows against the running
app and confirmed the fixes without runtime errors. Backend, permissions,
validation, migrations, and exports were re-reviewed with no additional
actionable findings. Full final verification is recorded in
[the second review](todos/gis-geometry-second-review.md).

# GIS Geometry read-only specification review

Added an agent-facing specification for the resource and its three GET
endpoints, including exact response schemas, examples, permissions, error
handling, caching, and centralized opacity/transparency constants. Corrected the
documentation index's stale Point/10 km² summary. Container checks validated all
six JSON examples against serializers and geometry validation; an independent
backend review confirmed the HTTP contracts. No runtime changes. See
[the specification](../docs/gis-geometry-read-api.md).

# GIS Geometries collection labels review

Pluralized the map card/header, accessible controls, and management collection
loading/empty/error messages. Individual record labels remain singular. The
existing 160 × 48 px card still fits the longer text at desktop/mobile widths.
All 1,185 JavaScript tests, ten page tests, lint, and the production build
passed in the running container. See
[the task](todos/gis-geometries-plural-labels.md).

# Profile application token copy review

Follow-up: applied the requested sky-blue info button style. All 1,191
JavaScript tests, template checks, and the production build passed again.

Added a right-side Copy button to the account token field using the shared
clipboard controller, now supporting input values. Includes accessible
success/failure feedback and preserves existing integration text copying. All
1,191 JavaScript tests, JavaScript lint, template formatting/lint, and the clean
production build passed in the running application container. See
[the task](todos/profile-token-copy.md).

# Feedback navigation icon review

Removed the default black fill from the main sidebar's Give us Feedback
paper-plane icon and aligned SVG-level stroke/color styling with its neighbors.
Container JavaScript tests, template formatting/lint, and clean production build
passed. See [the task](todos/feedback-icon-fill.md).

# GIS navigation section review

Moved GIS Geometries and GIS Layers into the alphabetized second sidebar
section, removed their navigation My prefixes, and preserved shared desktop/
mobile markup, icons, links, and route-family highlighting. Reviewed and updated
current docs and stale ordering guidance; independent review found no issues.
All 125 focused Python tests and 1,191 JavaScript tests passed, as did final
template regression checks, lint, typing, and the production build. GitLab
audit: zero creations/POSTs/violations, no unresolved outcomes or cleanup
needed. See [the task](todos/gis-navigation-section.md).

# Shared info copy buttons review

Placed the profile token Copy control inside its field and unified all 12 site
copy buttons under one shared info-style component. Removed feature color resets
and conflicting modal styles; clipboard behavior and disabled controls remain
intact. Updated docs and the styling lesson. Browser verification confirmed
matching styles and desktop/mobile field fit at 1440, 390, and 320px. Python
checks (64), JavaScript coverage (1,194, with load-related timeout retries),
lint, template checks, and production build completed successfully. See
[the verification details](todos/shared-copy-buttons.md).

# Celery worker container name review

Configured `${COMPOSE_INSTANCE_PREFIX:-speleodb}_local_celery_worker` in
`local.yml` and documented the resulting single-container scaling constraint.
Validated resolved worker and Beat names with assertions inside the running
Django container. Renamed the live worker to `speleodb_local_celery_worker`; its
ID, running state, and start time remained unchanged. Diff whitespace checks
passed. See [the task](todos/celery-worker-container-name.md).

# GIS Tooling disclosure review

Follow-up: added the supplied map-pin/layers SVG to **GIS Tooling** and indented
the submenu with a subtle guide, keeping desktop/mobile disclosure behavior.
Final icon/indent checks: 1,197 JavaScript tests, 68 template tests, template
checks, and build passed; browser verified 1440/390/320px layouts without
overflow. Sidebar follow-ups set its width to 290px (all nested labels remain
one line) and replace header `mb-10 mt-3` with `my-3`, preserving mobile logo
styles and full-width drawer dismissal. Final JavaScript tests, template checks,
and build passed.

Moved GIS Survey Map below Survey Tools and gave it a subtle blue accent. The
shared desktop/mobile sidebar now groups the remaining GIS entries under native
GIS Tooling disclosure, closed by default and automatically opened for a current
child page. Included missing cylinder inspection watchlist route highlighting.
Fixed the live new-entry error by building assets and reloading Django's cached
registry; the reported landmark page returns HTTP 200. All 178 focused Python
tests, 1,197 JavaScript tests, lint, typing, and build passed. Chromium verified
desktop/mobile expansion, keyboard toggling, and final styling. See
[the task](todos/gis-tooling-collapse.md).

# Profile and navigation adversarial review

Reviewed the complete copy-button and responsive sidebar change set with the
independent review agent; no actionable findings or corrective code edits were
needed. Full container JavaScript tests passed: 1,197 tests across 74 files.
Full Python tests reported 4,918 passed, 181 skipped, and one fixture setup
timeout from local GitLab. All 32 archive tests passed on rerun without changes.

The full run used 9 GitLab repositories and 10 creation POSTs; the archive retry
used 2 repositories and 2 POSTs. Both audits had zero violations, no unresolved
creations, and verified deletion marking for every created repository. The first
full `prek` run passed all code, security, type, lint, URL, and build checks;
Markdown formatting was applied and reviewed before the final rerun. See
[the verification record](todos/profile-navigation-adversarial-review.md).

# Private map toolbar and Settings review

Implemented four equal-width actions: Create Geometry, green Import GPS,
Managers, and Settings. Settings now contains compact color controls and marker
visibility; Managers directly opens the three entity managers. Removed retired
preference gates, preserved item selections, and corrected focus/fullscreen and
station Back navigation behavior. Documented the architecture and both user
feedback lessons.

Verified in the existing application container: **1,258 JavaScript tests**, **80
Python tests**, lint, typing, template checks, Django check, and clean Vite
build. Authenticated browser checks covered desktop/mobile, narrow breakpoints,
fullscreen, persistence, keyboard behavior, and actual existing map records.
Independent architecture and interface reviews found no remaining blockers. See
[the task](todos/map-viewer-settings.md) for exact scope and evidence.

Hover/color follow-up: removed the old fixed width from Survey Stations so all
three menu rows highlight fully. Managers is blue and Settings purple, including
hover/open states. Real desktop/mobile browser checks confirm identical 210px
menu rows and equal toolbar widths. Clean build, template formatting, and all
1,258 JavaScript tests pass.

Final review: the selected color mode now has an indigo highlight. The
adversarial reviewer accepted corrections to two stale test expectations
(toolbar markup and the documented worker container name). A fresh full run
passed **4,920 Python tests, 181 skipped**, and **1,258 JavaScript tests**. Both
full GitLab audits stayed within nine repositories and ten creation requests,
with zero violations/unresolved creations and confirmed cleanup of every created
repository. The first `prek run -a` passed code, security, type, URL, lint, and
build checks; its Markdown formatting changes were reviewed before the final
rerun.

Final `prek run -a`: all checks passed. Final browser checks passed again.

Import label follow-up: renamed the green toolbar action to Import GPX/KML.
Build, 1,258 JavaScript tests, and 79 focused Python tests passed. Chromium
verified the label, sizing, and import dialog at desktop and phone widths.
