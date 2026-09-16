# Reuse real GitLab repositories and enforce their creation budget

## Correction

The user rejected the Django suite's unbounded creation of GitLab repositories.
Real integration coverage does not require one repository per test. The agreed
contract is four fresh canonical repositories per invocation, reused throughout
the suite, plus at most five explicitly allocated creation/deletion lifecycles.
Extra database-only project identities are allowed. Every test runs inside the
already-running application container.

## Root cause

`ProjectFactory.create()` saves a database row; it does not itself provision
GitLab. The provisioning boundary is lazy `Project.git_repo` access when the
local UUID directory is missing. Parameterized upload/processor tests, fresh
project fixtures, and per-test working directories multiplied that path. Direct
SDK creations in archive and maintenance tests bypassed manager-only accounting.
Creation followed by teardown deletion still consumed a repository and server
work, so a small final group listing concealed the cumulative cost.

## Rules that prevent recurrence

- Start from canonical project/user helpers and explicit permission grants.
  Database-only cardinality/identity tests may add rows without obtaining a
  remote allocation. Team-only cases must not inherit a working direct grant.
- Keep session state to identifiers, baseline Git metadata, and remote clients;
  recreate Django rows inside each transaction so rollback/flush stays valid.
- Lease existing remotes with fresh local checkouts. Restore branches, tags,
  settings, and the complete `all=True` commit set. Distinct initial author
  identities prevent cross-project collisions in the globally keyed commit
  table. Disable GitLab builds/MRs on the pool to avoid retained hidden refs.
- Read the current SHA and extra-ref inventory through `git ls-remote` before
  reset. GitLab's REST branch cache can lag a completed push, causing a stale
  force-with-lease or leaving an additional branch behind. Use REST readback
  afterward to verify the restored state.
- Never delete a pooled repository from an individual test. Destructive
  lifecycle tests own sacrificial repos and scoped subgroups; authenticate,
  provoke the intended failure, assert preservation, and delete only at the end.
- Register exact-path cleanup before a sacrificial creation or write-check
  command starts. GitLab can commit creation before its response is lost;
  cleanup must recover the remote without relying on a returned project object.
- Attempt restoration for every borrowed role even if another reset fails.
  Retain failed roles as needing restoration and require a successful reset
  before their next lease. Repeated preparation within a healthy current lease
  must preserve the test's own mutations.
- Consolidate compatible empty/create/delete states within one test lifecycle.
  Do not rely on collection order or silently generate a replacement UUID.
- Keep the nine-success budget and fixed allocation names. Healthy full-suite
  operation expects ten creation POSTs because invalid-namespace coverage
  deliberately sends one rejected request. Retry attempts remain visible and
  retain their original namespace/path allocation.
- Audit below both manager and direct SDK calls, before Requests sends a
  creation POST. Propagate the same durable ledger through subprocess test
  settings. Treat swallowed violations and uncertain outcomes as run failures.
- Nested pytest must join an inherited ledger instead of starting another
  budget. An inherited deny-create policy may be tightened, never weakened.
- Preserve real GitLab responses, Git operations, and transaction failures. A
  guard is observation/enforcement, not a replacement response. Use real bare
  repos when only Git semantics are being tested.
- Keep CI preflight read-only and serialize tests with scheduled cleanup. Verify
  deletion by 404 or the actual delayed-deletion marker; never assume that
  deleting a parent group has synchronously deleted its repositories.
- Do not infer workflow-wide policy changes from a repository-reuse request.
  Follow the user's latest explicit direction: keep workflow-level
  `cancel-in-progress: false`. The user explicitly rejected reverting it to
  true.
- Run `docker exec -w /app speleodb_local_django make test-py`, then inspect the
  run's `.artifacts/gitlab/` summary and events. Report measured cumulative
  creations, attempts, violations, unresolved outcomes, and cleanup separately.
  Do not claim the contract passed before the full run and audit are reviewed.

## Review lint correction

Exception regressions must use an `Error` suffix and keep `pytest.raises()`
around one operation. Extract a lifecycle helper when an exception must cross
its cleanup boundary. Run Ruff on review-agent edits before claiming review
verification is complete; passing pytest does not establish lint compliance.
