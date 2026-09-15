# Task reviews

## Post-commit timeout test isolation

The hook timeout test's sleep mock intercepted Python subprocess polling via the
shared stdlib `time` module. Retry tests now replace only the retry helper's
module reference; real process cleanup retains its sleep. The hook regression
also asserts exactly one commit invocation. Application behavior is unchanged.
All four affected modules passed inside Docker: 70 tests and 31 subtests.

See [the review](todos/post-commit-timeout-sleep.md) and
[test isolation design](../docs/git-retry-testing.md).

## Plain export files and shared storage managers

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
