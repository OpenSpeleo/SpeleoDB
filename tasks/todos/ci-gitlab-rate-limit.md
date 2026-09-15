# CI GitLab rate limiting and upload failure verification

## Plan

- [x] Inspect the reported job, supplied live traceback, and preceding run.
- [x] Identify the false-positive rollback assertion and duplicate provisioning
      triggered by error cleanup.
- [x] Audit token propagation and the rate-limit source; distinguish CI's
      service configuration from the local test instance.
- [x] Stop upload cleanup from creating/cloning repositories.
- [x] Replace the affected GitLab and upload test doubles with real Git, GitLab,
      HTTP, storage, and database behavior; assert the specific failure.
- [x] Remove redundant creation requests for existing remotes and verify
      authenticated integration behavior. Do not boot GitLab per CI job.
- [x] Create the explicitly requested Railway `test` environment and deploy one
      always-on, self-contained GitLab with a persistent volume and HTTPS.
- [x] Verify real authenticated API access, HTTPS Git push, and a fresh clone.
- [x] Verify actual 429 responses with an isolated bot and restore the temporary
      rate-limit configuration and credentials afterward.
- [x] Record the user-created CI group/token and the user's manual GitHub
      environment update; revoke and remove the administrative bootstrap token.
- [x] Verify final deployment `3debd5be-5a0b-4299-af87-e00e6b0ad39a` and reread
      persisted credentials/repository contents after restart.
- [x] Diagnose and resolve the remaining full-suite failures, then complete
      relevant regression checks, lint, type checking, and review.
- [ ] After this commit is pushed, verify a GitHub Actions run using the new
      service; the requested local commit does not trigger that run.
- [x] Document architecture, completed evidence, lessons, and verification
      limits.

## Scope and user constraints

The user explicitly requires real integration behavior for all GitLab and upload
tests. Do not substitute a fake HTTP service or patched SDK for GitLab. Do not
mask unexpected service failures with generic HTTP 500 assertions. Production
API clients pass a token; actual request observations also verify its presence
and authenticated identity for the tested configuration.

The supplied traceback proves project-creation POSTs receive HTTP 429. Cleanup
then accesses the lazy repository property and repeats the creation retry cycle.
A test intended to fail at commit accepts this earlier failure instead.
Lookup-first acquisition and cleanup of only existing worktrees remove both
sources of redundant creation traffic. PostgreSQL transaction tests now check
persisted rollback results with production's `ATOMIC_REQUESTS` semantics.

CI used GitLab.com; local tests used a separate, older GitLab Compose service.
Authentication does not exempt CI from service quotas. The exact enabled limiter
and threshold of the historical GitLab.com job remain unconfirmed.

The user rejected starting GitLab for every CI job, then requested a dedicated,
always-on GitLab in Railway's `test` environment. The service embeds PostgreSQL,
Redis, and Gitaly; configuration secrets, repositories, database, and logs share
a persistent 5 GB volume. GitHub jobs use the running service directly.

## Deployment and credentials

The service is `GitLab` in the existing `speleoDB` project, reachable at
`https://gitlab-test.speleodb.org`. Deployment `b011d7cb` reached `SUCCESS`.
Actual authenticated API and HTTPS push/fresh-clone verification preserved
project `2` at commit `683c8420d5528ed23f158cd93ac4125cfbf700c6`.

The user created private group `github-ci` (ID `3`) and owns its active token
`github CI` (ID `4`), created at 21:30:17 UTC, with `api`, `read_repository`,
and `write_repository` scopes. The earlier agent-created CI token was revoked.
GitHub secret metadata confirms host/group updates at 21:27 UTC and the token
update at 21:30:43 UTC. Plaintext is not retrievable, and no Actions run has
independently validated the effective configuration. The bootstrap admin token
was revoked (204), its reuse rejected (401), and its Railway variable removed.

The instance disables signup, sets project/group creation quotas to `0`, and
retains deleted test data for one day. An initial sample measured 3.789 GB RAM
and 0.603 GB used on the 5 GB volume. Final deployment
`3debd5be-5a0b-4299-af87-e00e6b0ad39a` reached `SUCCESS` at 21:38:47 UTC with
boot-time settings enforcement and stale runtime-file cleanup. Root login and
the private project survived restart; a fresh HTTPS clone matched the original
SHA and file bytes. Its temporary verification token was revoked (204), and the
agent-owned smoke project was scheduled for deletion (202). The user-owned
active CI token was preserved.

## Review

Completed targeted Docker/PostgreSQL checks include core GitLab API/manager
suites (41 passed), Compose provisioning/cleanup (30 passed), upload/error/proxy
migration (56 passed), and Git supervisor/GeoJSON rebuild/commit retry
regressions (35 passed). Additional GPX, GIS-layer, error-reporting, and
landmark GPX/KML tests passed 25 cases. These are targeted runs, not an
aggregate count of distinct tests or proof of a passing full suite. Final
targeted verification passed 17 tests, including all five failed/error cases,
corrected landmark imports, browser upload/storage cleanup, CI preflight, and
restart filesystem checks. A separate final upload error-handling run passed all
eight tests.

The full local pytest run was interrupted at about 77% after Docker stalls:
3,464 passed, 154 skipped, 46 subtests passed, four failed, and one setup error.
Three query-budget assertions now include the two fixed transaction statements
from production-compatible ATOMIC_REQUESTS. The existing-remote assertion allows
legitimate GET retries while rejecting creation POSTs. The remaining setup error
was a real local GitLab timeout. All five cases passed the final targeted rerun;
the complete suite was not rerun to completion.

Ruff and formatting passed all 33 changed Python files; full mypy passed 715
source files. JavaScript lint passed. The full JavaScript run had 1,008 passes
and two timeouts during Docker stalls; both affected files subsequently passed
all 90 tests. The changed frontend rendering group passed 58 tests. The work is
prepared as one local commit; no push or new CI run is claimed.

A controlled probe on the new GitLab obtained a real first-project 201, then 429
responses with exactly one attempt when rate-limit retry was disabled and two
attempts with a two-attempt budget. Real response hooks verified token presence.
Temporary settings, feature gates, bot credentials, and group cleanup were
restored; cached feature-flag state required a recovery cleanup pass. This
one-off probe does not add recurring CI coverage for arbitrary 429/5xx sequences
or resource-lock conflicts, and does not identify the historical hosted quota.

Architecture and operational evidence are in
[the Railway GitLab document](../../docs/gitlab-test-railway.md); test
boundaries and the original failure explanation are in
[the integration design](../../docs/ci-gitlab-testing.md).
