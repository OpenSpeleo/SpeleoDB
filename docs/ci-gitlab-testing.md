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
is destructive and must never target production or overlap another run using
that group. A `test` environment isolates the service; it does not by itself
configure GitHub Actions or prove that its secrets point at that service.

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
model instances. `canonical_user()` and `canonical_project()` materialize
database rows inside the requesting test's transaction, including after
`TransactionTestCase` flushes. Database-only tests do not contact GitLab.
`project_matrix()` explicitly creates the complete A/B ownership and permission
matrix.

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
| `empty-archive` | Empty/disabled archive behavior, recorded-history inconsistency, initial API commit and duplicate-file rejection  |
| `manager-empty` | Initialization of an existing empty remote, subgroup confirmation, dry run, authentication failure and deletion   |
| `write-check`   | The management command's real authenticated create/delete check                                                   |

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
`write-check` allocation. CI and scheduled group cleanup share a concurrency key
so cleanup cannot delete active test repositories.

## Isolation when reusing a remote

Each test gets a fresh local checkout directory. Git consumers explicitly call
`get_pool().prepare(project)` to acquire a remote lease. A `skip_if_lighttest`
marker does not provision or authorize GitLab: media-only tests also use that
marker. The lease restores the original default-branch SHA, removes additional
public branches and tags, and restores the pool's repository settings. Both the
current branch SHA and extra-ref inventory come from `git ls-remote`, because
GitLab's REST branch metadata can lag a push. The lease then verifies the entire
REST history with `all=True`, not just the default branch.

Pool repositories disable GitLab builds and merge requests before initial
publication, and tests do not create GitLab notes. Those GitLab features can
retain hidden references after a public branch is reset. The initial empty
commits use project-specific author identities so their SHAs remain distinct:
`ProjectCommit.id` is globally unique across survey projects. A dirty lease
fails instead of silently replacing the repository. Restoration attempts every
borrowed role even when another reset fails, and failed roles remain pending
until their reset succeeds. Preparing such a role must complete restoration
before granting the next lease; preparing an already healthy active lease does
not reset the current test's changes. Local Git-only behavior can use real bare
repositories without a GitLab lease.

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
project UUID. An existing remote requires no creation POST. Only a real 404
permits creation; other lookup failures propagate. Creation conflicts still
require a successful lookup before cloning, which handles concurrent creation
without treating authentication, validation, or throttling errors as success.

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
these tests. Local bare repositories remain appropriate for Git-only behavior.
The existing `skip_if_lighttest` marker explicitly selects an offline test mode;
a required live service becoming unavailable must not trigger an automatic skip.

Local bootstrap provisioning tests additionally require the local administrator
bootstrap token. They run only against the local infrastructure addresses and
create their own groups. Those local setup tests are inapplicable to a remote
test service; ordinary authenticated integration checks still run there.

## Browser upload transport

`test_frontend_upload_integration.py` starts Django's real live server with a
database-backed authenticated session, then invokes
`scripts/test-frontend-uploads.mjs`. The script loads the rendered GIS-layer
page, uses its actual CSRF token and the vendored jQuery library, and imports
the production upload modules. JSDOM supplies its unmodified XMLHttpRequest and
FormData implementations; requests reach Django and persist files in the
configured S3-compatible service. Python reads those files back to verify exact
bytes and checks the database for unexpected writes.

The integration observes real progress events, DOM mutations, and completed list
requests. It covers modal dismissal while uploading, one successful list
refresh, processor rejection, CSRF rejection, alternate HTTP methods, empty HEAD
responses, HTML response parsing, connection refusal, and native cancellation.
It does not synthesize HTTP status codes or replace upload callbacks. Empty HEAD
responses exercise the no-content behavior without claiming a real 204 outcome.
Pure progress rendering remains in Vitest with the actual upload component.

Node and the root npm dependencies are required in the pytest job. Missing Node,
an unavailable server, a failed upload, or an unreadable stored file fails the
test; none of these conditions silently removes coverage. Session credentials
travel through the child process's stdin and are never printed or put in its
command arguments.

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

Run tests with the normal local SQLite configuration and repeat
database-sensitive checks against PostgreSQL using `TEST_DATABASE_URL`.
Verifying only an overridden CI database misses regressions in the supported
local configuration. Keep suites sharing a database or cleanup namespace serial.
Never print the database URL, GitLab token, or credential-bearing Git URLs
during diagnostics.

Relevant targets include the GitLab API-policy, manager and lifecycle suites,
upload error handling, proxy, archive initialization, preload history, cleanup
commands, audit/pool contract checks, and local provisioning. Verification
results and measured creation counts belong in the task's review record; this
document describes the required behavior rather than claiming a particular run
passed.

The lookup-first path adds one GET to new creation and removes a rejected POST
from existing-remote acquisition. Four reusable remote identities bound
provisioning independently of the number of database fixtures or upload
parameters. Lease restoration adds bounded Git/ref operations, but prevents
unbounded remote history and cross-test contamination. The immutable creation
allocations provide a stronger regression check than counting repositories left
in a group after teardown.
