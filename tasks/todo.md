# Task reviews

## Export storage reuse and flat filenames

Exports now use the shared private storage backend: CloudFront signing in
production, browser-facing S3 signing locally, and generic streaming upload and
version cleanup operations. New keys are flat exports/{filename}.zip and use
unique attempt IDs; historical nested keys remain supported. Existing public
backends retain their unsigned URLs. No schema migration is needed.

Validation completed with 139 targeted tests passed, 1 skipped, full mypy, and
Ruff on task-owned files. Independent review found no actionable regression.
The complete production policy and CloudFront configuration steps are prepared.
Live reads proved missing version/cleanup permissions and dropped version query
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
