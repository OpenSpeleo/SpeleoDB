# Real GitLab integration tests

## Intent and ownership

The API, repository manager, archive jobs, and maintenance commands use a real
GitLab service in integration tests. GitHub Actions runs the tests; GitLab owns
the repositories and serves its actual API and Git transport. A dedicated,
always-on test GitLab keeps these checks independent of GitLab.com's shared
service quotas without adding GitLab startup to every CI job.

The test service must have its own namespace and credentials. Configure
`GITLAB_HTTP_PROTOCOL`, `GITLAB_HOST_URL`, `GITLAB_GROUP_ID`,
`GITLAB_GROUP_NAME`, and `GITLAB_TOKEN` as a consistent set. Test-group cleanup
is destructive and must never target production. Unrestricted cleanup must not
overlap another run using that group. A `test` environment isolates the service;
it does not by itself configure GitHub Actions or prove that its secrets point
at that service.

## Repository budget and ownership

A complete Django test invocation may create **at most nine GitLab projects**.
This counts all successful creations, including repositories deleted during the
run. Deleting a project does not refund its allocation. Ordinary integration
tests reuse four repositories with fresh UUIDs for each invocation:

| Project                | Leader | User A's ordinary direct access |
| ---------------------- | ------ | ------------------------------- |
| ADMIN Project          | A      | ADMIN                           |
| Read and Write Project | B      | READ_AND_WRITE                  |
| Read only Project      | B      | READ_ONLY                       |
| Webviewer Project      | B      | WEB_VIEWER                      |

`speleodb/testing/gitlab_pool.py` owns the identifiers, remote client, initial
commit SHAs, leases, and final cleanup. It retains no session-scoped Django
model instances. Provisioning delegates to
`GitlabManager.create_or_clone_project()`, including UUID remote names and
paths, bounded creation attempts, ambiguous-response recovery, and the
application's normal initial commit. During this fixture-only provisioning, only
elapsed HTTP backoff is omitted with a scoped module clock replacement. Actual
requests and SDK responses remain real; ordinary borrowed-repository operations
retain their normal timing and cleanup behavior. Canonical role names are Django
fixture labels only; using those labels as remote names collides across
concurrent runs or with repositories awaiting deletion. `canonical_user()` and
`canonical_project()` materialize database rows inside the requesting test's
transaction, including after `TransactionTestCase` flushes. Database-only tests
do not contact GitLab. `project_matrix()` explicitly creates the complete A/B
ownership and permission matrix.

The base API cases select the canonical project for their tested permission
level. Grants remain explicit: `canonical_project()` does not silently grant A
access, and `set_test_project_permission()` creates the direct or team grant
being tested. This preserves cases involving no permission, inactive grants,
team-only access, and permission cardinality. Team tests must not inherit a
direct grant that could satisfy the request without exercising the team.
Additional `ProjectFactory` identities are permitted for database cardinality,
isolation, missing-project, and validation cases. They carry no permission to
create a remote. Child factories default to `CanonicalProjectFactory`, whose
`build()` supplies an unsaved project without database queries and whose
`create()` reuses a canonical row. Pass explicit projects when testing distinct
identities; canonical factories reject `id` and `pk` overrides.

### Five creation/deletion lifecycles

The remaining allocations cover operations whose correctness depends on a
genuinely absent, empty, or disposable remote. Each lifecycle is self-contained;
pytest collection order never determines whether a project is ready or deleted.

| Allocation      | Coverage sharing the repository                                                                                   |
| --------------- | ----------------------------------------------------------------------------------------------------------------- |
| `manager-new`   | Missing lookup, new-project initialization, cache recovery, user cleanup failure and deletion                     |
| `proxy-new`     | First-404 provisioning and retry, Make cleanup with invalid credentials, successful deletion and repeated cleanup |
| `empty-archive` | Empty/disabled archive behavior, recorded-history inconsistency and cleanup after failure                         |
| `manager-empty` | Initialization of an existing empty remote, subgroup confirmation, dry run, authentication failure and deletion   |
| `write-check`   | The management command's real authenticated create/delete check                                                   |

The absent-remote manager/proxy tests explicitly request `gitlab_retry_delays`
to record backoff without elapsed waiting. This function-scoped fixture replaces
only the bounded client's module clock reference: actual HTTP requests, attempt
counts, SDK errors and production delay settings remain intact. It never patches
process-wide `time.sleep`; ordinary propagation/recovery tests keep real
waiting. The API-policy suite separately asserts the complete requested delay
sequence.

Destructive command policies run against real GitLab through `call_command` with
scoped stdin/environment. Two actual Make subprocesses retain successful and
unauthorized cleanup, settings/flag wiring, exit codes and token secrecy;
already-deleted idempotency uses the real command without another Django
startup.

The healthy full-suite target is **nine creations and ten creation POSTs**. The
tenth POST is the separately authorized invalid-namespace request, which must
return HTTP 400 and create nothing. Transient failures can add bounded retries
to the same namespace/path. They cannot allocate a replacement UUID or increase
the nine-project budget. Focused subsets may use fewer allocations.

## Mandatory request audit

`config.settings.test` installs the test-only Requests transport guard in
`speleodb/testing/gitlab_audit.py`. The root pytest plugin starts a fresh SQLite
ledger before test setup, assigns test IDs and setup/call/teardown phases, and
exports a report at session completion. The wrapper forwards permitted requests
to the original transport; it does not manufacture GitLab responses or replace
SDK behavior.

Every `POST /api/v4/projects` must have a named `creation_allocation()` bound to
its exact namespace and path before transport. This catches both lazy
`Project.git_repo` provisioning and direct SDK calls. Ordinary leases reuse an
existing remote and have no creation permission. The guard rejects undeclared
creations before sending them, records attempts and responses, reconciles
uncertain outcomes through subsequent real project lookups, and records deletion
requests and verified cleanup outcomes. A recorded violation or unresolved
creation fails the pytest session even when application code catches the error.

The ledger path and current test attribution travel through environment
variables to Python subprocesses using test settings. Child processes join the
same ledger rather than receiving another budget. Preserve the inherited
environment when invoking management commands or browser integration helpers.
Tests for the audit itself exercise ledger policy without creating real remotes.

Reports live under `.artifacts/gitlab/<run-id>/`:

- `ledger.sqlite3`: durable accounting across DB rollbacks and subprocesses.
- `events.jsonl`: allocation, creation, response, cleanup, and violation events,
  including the initiating stack and pytest phase.
- `summary.json` and `summary.txt`: cumulative creations, POST attempts,
  allocation identities, violations, unresolved outcomes, and verified cleanup
  per allocation.

The audit omits credentials, request/response bodies, and credential-bearing
URLs. GitHub Actions uploads these artifacts even when tests fail. The CI
preflight uses `check_gitlab --read-only`; repository writes belong to pytest's
`write-check` allocation.

### Branch concurrency and manual cleanup

CI's pytest concurrency group includes `github.head_ref || github.ref`, allowing
different branches to run concurrently while retaining
`cancel-in-progress: false`. Each invocation owns fresh repository UUIDs;
workers within an invocation remain serial. Parallel jobs increase aggregate
GitLab load but do not change the nine-project budget per invocation.

Pytest jobs have a 60-minute timeout. The manual cleanup workflow passes
`--older-than-hours 24` to `wipe_test_gitlab`, so active jobs' repositories
remain untouched. The filter compares timezone-aware `created_at` values against
a cutoff captured once at command start; missing or invalid dates are preserved.
Normal session cleanup still deletes only the invocation's own repositories. The
cleanup workflow has only a `workflow_dispatch` trigger; there is no cron. Run
it manually to remove stale leftovers from interrupted or failed cleanup. The
unrestricted `make wipe_gitlab_test` command remains available for manual
maintenance only when no tests are active.

Deploy the safe cleanup workflow to the default branch before enabling parallel
CI on other branches: an older scheduled workflow still performs a full wipe.
Verification covers age boundaries and malformed dates plus preservation of a
real, fresh lifecycle repository before its normal deletion.

## Isolation when reusing a remote

Each test gets a fresh local checkout directory. Git consumers explicitly call
`get_pool().prepare(project)` to acquire a remote lease. A `skip_if_lighttest`
marker does not provision or authorize GitLab: media-only tests also use that
marker. The lease restores the original default-branch SHA, removes additional
public branches and tags, and restores the pool's repository settings. Both the
current branch SHA and extra-ref inventory come from `git ls-remote`, because
GitLab's REST branch metadata can lag a push. The lease then verifies the entire
REST history with `all=True`, not just the default branch.

After normal provisioning, pool repositories disable GitLab builds and merge
requests before granting a lease, and tests do not create GitLab notes. Those
GitLab features can retain hidden references after a public branch is reset.
Each slot records its actual initial commit as the restoration baseline; fixture
code does not customize commit authors or require distinct empty-commit SHAs.
The live pool regression checks UUID names and paths plus standard commit
authorship using the existing four allocations, without additional provisioning.
A dirty lease fails instead of silently replacing the repository. Restoration
attempts every borrowed role even when another reset fails, and failed roles
remain pending until their reset succeeds. Preparing such a role must complete
restoration before granting the next lease; preparing an already healthy active
lease does not reset the current test's changes. Local Git-only behavior can use
real bare repositories without a GitLab lease.

Individual tests must never delete pooled repositories. Session cleanup owns
them. Destructive command checks use isolated subgroups or an explicitly
allocated sacrificial project. Cleanup accepts a real 404 or a verified deletion
mark; it does not turn authentication or availability errors into success.
Subgroup cleanup verifies remaining children individually before requesting
deletion of the group. GitLab may retain projects marked for delayed deletion,
so a successful cleanup does not claim physical removal from storage.

Register `cleanup_remote_on_exit()` with the preallocated full project path
before creating a sacrificial remote or invoking the write-check command. It
recovers and deletes only that exact identity even when creation committed but
the caller never received its project object.

Pytest execution is serial; the plugin rejects parallel workers. Database
rollback, lease restoration, and session cleanup have separate responsibilities.
Keep real upload rollback tests on `TransactionTestCase` with
`ATOMIC_REQUESTS=True`; pooling must not weaken their transaction assertions.

## What the September 2026 failure established

The supplied GitHub job log contains a real HTTP 429 response to project
creation. CI used GitLab.com, while the local Compose service was GitLab 18.7.0.
These are different servers with different service policies and load. A passing
local run therefore did not establish that the CI endpoint had remaining
capacity.

Two application behaviors amplified the failure:

1. Repository acquisition attempted project creation even when the remote
   already existed. A rejected duplicate POST still consumes server work and can
   count against a creation quota.
2. Upload error cleanup accessed the lazy `project.git_repo` property. After
   creation failed, cleanup attempted creation again, with a fresh retry budget.

Five attempts with 1/2/4/8-second delays cannot resolve a quota whose window is
longer than that retry budget. Increasing retries adds traffic and delays.
GitLab documents a project-creation limiter introduced in 19.3 behind
`namespace_create_rate_limit`, with a default of 200 requests per day per user.
Its creation check and response wording are consistent with the observed error,
but the supplied log does not identify GitLab.com's enabled flag or effective
threshold. Do not present that exact quota as confirmed for the failed job.
Response headers, a request ID and server-side evidence are needed to identify
the effective limiter. See
[GitLab project API rate limits](https://docs.gitlab.com/rate_limits/api/projects/)
and
[the implementation change](https://gitlab.com/gitlab-org/gitlab/-/merge_requests/245318).

Authentication does not exempt a caller from rate limits. Production API clients
pass the configured token, and the real-service regression verifies that
outgoing requests carry it and that `/user` returns the authenticated identity.
That verifies the tested configuration; it does not reveal a GitHub secret's
value or prove the historical job's identity.

## Repository and cleanup boundaries

`GitlabManager._ensure_remote_project()` first looks up the exact namespace and
project UUID. An existing remote requires no creation POST. Acquisition retries
HTTP 404 within the bounded REST attempt budget before permitting creation;
other exhausted lookup failures propagate. Creation conflicts still require a
successful lookup before cloning, using the same opt-in HTTP 404 backoff without
restarting creation or treating authentication, validation, or throttling errors
as success.

Upload cleanup opens a working copy only if its directory already exists. It
never accesses the provisioning property. Cleanup failures remain secondary to
the original upload exception and cannot initiate another GitLab creation
attempt.

`GitlabClient` uses the shared bounded REST transport. Empty credentials fail
before any network request. Authentication, pagination, archive requests, and
cleanup use this policy; Git subprocesses retain their separate bounded policy.
The application owns retry sleeps, and preserves the SDK's actual response
status and body. See [GitLab reliability](gitlab-reliability.md).

## Test design

- Require successful real authentication and repository initialization before
  provoking an upload failure. Setup errors fail the test immediately.
- Assert the intended failure itself: an actual Git index lock, rejecting Git
  hook, invalid GitLab credential, malformed input, or SQL constraint violation.
  HTTP 500 alone is insufficient because an unrelated outage can also return it.
- Use `TransactionTestCase` for upload rollback checks on SQLite and PostgreSQL,
  with `ATOMIC_REQUESTS=True`. Query persisted rows after the request
  transaction exits; the surrounding transaction of `TestCase` cannot prove that
  rollback.
- Import rollback tests install a temporary, owner-scoped unique-name constraint
  through Django's schema editor. Two same-name records at different coordinates
  produce a real second-insert failure on both engines. Native signals prove the
  first insert succeeded, then database and storage reads prove rollback. The
  constraint is removed afterward; no model, ORM method, or response is
  replaced. Do not rely on PostgreSQL-only VARCHAR enforcement for portable
  failure input.
- Observe the real Sentry SDK's `before_send` event hook with external delivery
  disabled. This proves exception/event construction, not remote Sentry
  delivery.
- Observe real SDK response hooks to check token presence, response bodies,
  request counts, and the absence of a duplicate creation POST. Observation must
  not replace or manufacture responses.
- Exercise transport refusal through a reserved, non-listening local socket.
  This validates actual connection errors and bounded retry attempts. It does
  not claim coverage for synthetic 429/5xx response sequences or server headers.
- Reuse canonical repositories for existing-repository behavior. Reserve fresh
  UUIDs and subgroups for the five allocated lifecycles above; per-test remote
  creation is forbidden. Cleanup suppresses only confirmed absence and respects
  GitLab's delayed-deletion state.

No patched SDK methods, HTTP fakes, or replacement GitLab services are used by
these integration tests. Separate deterministic existence/backoff policy tests
script SDK-boundary outcomes for retry decisions and conflict handling; they do
not replace live-service coverage or participate in repository provisioning.
Local bare repositories remain appropriate for Git-only behavior. The existing
`skip_if_lighttest` marker explicitly selects an offline test mode; a required
live service becoming unavailable must not trigger an automatic skip.

Local bootstrap provisioning tests additionally require the local administrator
bootstrap token. They run only against the local infrastructure addresses and
create their own groups. Those local setup tests are inapplicable to a remote
test service; ordinary authenticated integration checks still run there.

### Local default branch protection

Local bootstrap configures only the dedicated test group's default branch
protection as unprotected, using GitLab's
[`default_branch_protection_defaults` API](https://docs.gitlab.com/api/groups/#options-for-default_branch_protection_defaults).
Disposable repositories need normal pushes and force resets for isolated leases.
The development group's protection policy is left to GitLab's defaults.
Provisioning still uses the application manager and UUID names.

This also avoids a demonstrated local GitLab 18.7 cache inconsistency: after a
successful protection-rule deletion, the rule list was empty while
`ProtectedBranch.protected?` remained true and branch authorization denied an
otherwise permitted owner. Repeated pushes did not repair it. For an affected
existing repository, verify the missing rules and refresh only that project's
`ProtectedBranches::CacheService`; do not flush the whole GitLab cache or add
application retry logic. Group defaults prevent creating and deleting the
automatic protection rule for future test repositories. This is infrastructure
configuration, not a second repository creation path.

The existing real bootstrap test checks the configured policy, and real upload
and lease restoration tests verify normal pushes and history resets. No extra
repositories are allocated for this coverage.

## Upload test boundaries

`test_frontend_upload_integration.py` protects the Django session/CSRF and
storage contract with the CSRF-enforcing test client. It obtains the token from
the rendered GIS-layer page, rejects an upload without that token and checks
that no layer was created, then uploads with the token and reads back the exact
bytes from the configured S3-compatible storage. It uses normal database
rollback because there is no second server connection requiring committed rows.

Frontend transport and controller behavior belongs in Vitest. The GIS-layer
controller tests exercise multipart serialization, upload errors, modal state,
and successful list refreshes through a real local HTTP server. The upload
component tests cover progress, generated methods, cancellation, controller
promise settlement, and the distinction between server rejection and ambiguous
network or unreadable responses. These tests use the actual generated SDK and
JSDOM XMLHttpRequest; the local server supplies controlled responses to exercise
frontend policy, without claiming to verify Django behavior. Backend format
validation, permissions, and storage integration remain in pytest. The separate
browser suite is reserved for UI/UX verification.

## Running and validating tests

Run every test inside the already-running application container. Do not start
another stack or execute pytest on the host. From the repository root:

```sh
docker exec -w /app speleodb_local_django make test-py
```

For a targeted check, invoke pytest through the same container:

```sh
docker exec -w /app speleodb_local_django pytest speleodb/git_engine/tests/test_gitlab_lifecycle.py
```

Use `--gitlab-audit-deny-create` for bounded investigations of accidental
provisioning. It records the responsible call and rejects every creation before
transport; a test reaching that path is expected to fail. Do not use this mode
as evidence that live integrations passed. Consult the report to distinguish an
application failure from a denied creation attempt.

Before declaring this contract verified, run the full `make test-py`, inspect
its cumulative audit, require zero violations and unresolved outcomes, and
verify cleanup. Also cover reordered live tests, two consecutive leases, remote
mutation/restoration, transaction flushes, direct SDK guard rejection, inherited
subprocess accounting, and positive and negative permission paths. Each full
invocation has its own fresh identifiers and nine-project limit.

The complete backend suite uses PostgreSQL for its retained advisory-lock,
immediate-constraint, and independent-worker integration contracts. Configure
`DATABASE_URL` explicitly in `.envs/test.env`; use the reachable PostgreSQL
service address (`postgres:5432` in the monorepo container, `localhost:5432`
with standalone host networking). Test settings honor that URL independently of
development `POSTGRES_*` configuration and reject other engines clearly.
`TEST_DATABASE_URL` is an explicit connection override. Pytest creates its own
`test_` database from pristine `template0`; it never tests against development
data. Keep suites sharing a database or cleanup namespace serial. Never print
the database URL, GitLab token, or credential-bearing Git URLs during
diagnostics.

The distributed environment template expands the existing `POSTGRES_*` service
address and credentials, with standalone defaults. Existing private environment
files are preserved by setup; replace an old SQLite `DATABASE_URL` explicitly
when migrating. A literal private URL or explicit `TEST_DATABASE_URL` remains
authoritative.

Relevant targets include the GitLab API-policy, manager and lifecycle suites,
upload error handling, proxy, archive initialization, preload history, cleanup
commands, audit/pool contract checks, and local provisioning. Verification
results and measured creation counts belong in the task's review record; this
document describes the required behavior rather than claiming a particular run
passed.

The lookup-first path adds up to five GETs and 15 seconds of default backoff to
new creation, and removes a rejected POST from existing-remote acquisition. Four
reusable remote identities bound provisioning independently of the number of
database fixtures or upload parameters. Lease restoration adds bounded Git/ref
operations, but prevents unbounded remote history and cross-test contamination.
The immutable creation allocations provide a stronger regression check than
counting repositories left in a group after teardown.

### Default test coverage and explicit exclusions

`make test-py` executes all collected backend tests. The selection plugin treats
collection and runtime skips as failures. Missing services, dependencies,
fixture files, or privileges must be fixed; the suite must not pass by omitting
them. The live Celery and storage integrations run without environment opt-ins.
The local Compose graph includes the dedicated test Redis process; CI reuses its
Redis service exclusively for these integrations. Ordinary tests retain the
in-process broker, while real workers explicitly select the dedicated endpoint.

For a deliberately partial development run, `--light` and `--offline` deselect
their existing marked tests. `-m 'not live_services'` excludes real
worker/broker checks. Pytest reports these exclusions as deselected cases. All
marker groups run without these explicit options. The GitHub job explicitly uses
`-m 'not local_infrastructure'` for exactly five local GitLab routing and
administrator-bootstrap cases: its hosted GitLab service cannot provide those
local contracts. Its output must report five deselections; that CI invocation is
a narrower scope than the complete default local run. It still runs every
worker, broker, database, signing, and small-artifact storage integration.

Real GitLab bootstrap tests require `GITLAB_BOOTSTRAP_TOKEN` for the configured
GitLab administrator in addition to the ordinary test-group token. The local
GitLab endpoint must also support the local browser and Compose Host headers
checked by its routing tests. Missing credentials or incompatible routing fails
the suite; it does not skip those contracts. Never use production administrator
credentials for test provisioning.
