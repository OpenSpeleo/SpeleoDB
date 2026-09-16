# Task reviews

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
