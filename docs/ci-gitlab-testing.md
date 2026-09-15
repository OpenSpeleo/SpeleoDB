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

## What the September 2026 failure established

The supplied GitHub job log contains a real HTTP 429 response to project
creation. CI used GitLab.com, while the local Compose service was GitLab
18.7.0. These are different servers with different service policies and load.
A passing local run therefore did not establish that the CI endpoint had
remaining capacity.

Two application behaviors amplified the failure:

1. Repository acquisition attempted project creation even when the remote
   already existed. A rejected duplicate POST still consumes server work and
   can count against a creation quota.
2. Upload error cleanup accessed the lazy `project.git_repo` property. After
   creation failed, cleanup attempted creation again, with a fresh retry budget.

Five attempts with 1/2/4/8-second delays cannot resolve a quota whose window is
longer than that retry budget. Increasing retries adds traffic and delays.
GitLab documents a project-creation limiter introduced in 19.3 behind
`namespace_create_rate_limit`, with a default of 200 requests per day per user.
Its creation check and response wording are consistent with the observed
error, but the supplied log does not identify GitLab.com's enabled flag or
effective threshold. Do not present that exact quota as confirmed for the
failed job. Response headers, a request ID and server-side evidence are needed
to identify the effective limiter. See [GitLab project API rate limits](https://docs.gitlab.com/rate_limits/api/projects/)
and [the implementation change](https://gitlab.com/gitlab-org/gitlab/-/merge_requests/245318).

Authentication does not exempt a caller from rate limits. Production API
clients pass the configured token, and the real-service regression verifies
that outgoing requests carry it and that `/user` returns the authenticated
identity. That verifies the tested configuration; it does not reveal a GitHub
secret's value or prove the historical job's identity.

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
- Use `TransactionTestCase` for upload rollback checks, with PostgreSQL and
  `ATOMIC_REQUESTS=True`. Query persisted rows after the request transaction
  exits; the surrounding transaction of `TestCase` cannot prove that rollback.
- Observe the real Sentry SDK's `before_send` event hook with external delivery
  disabled. This proves exception/event construction, not remote Sentry delivery.
- Observe real SDK response hooks to check token presence, response bodies,
  request counts, and the absence of a duplicate creation POST. Observation
  must not replace or manufacture responses.
- Exercise transport refusal through a reserved, non-listening local socket.
  This validates actual connection errors and bounded retry attempts. It does
  not claim coverage for synthetic 429/5xx response sequences or server headers.
- Use disposable UUID repositories and subgroups. Cleanup suppresses only
  confirmed absence and respects GitLab's delayed-deletion state; authentication
  and availability failures remain failures.

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
`scripts/test-frontend-uploads.mjs`. The script loads the rendered GIS-layer page,
uses its actual CSRF token and the vendored jQuery library, and imports the
production upload modules. JSDOM supplies its unmodified XMLHttpRequest and
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

## Validation and performance

Run tests inside the Django Docker container against PostgreSQL, using
`TEST_DATABASE_URL` when the private local dotenv otherwise selects SQLite.
Keep suites sharing a database or cleanup namespace serial. Never print the
database URL, GitLab token, or credential-bearing Git URLs during diagnostics.

Relevant targets include the GitLab API-policy and manager suites, upload error
handling, proxy, archive initialization, preload history, cleanup commands, and
local provisioning. An always-on service must also be verified by authenticated
API calls, project creation, actual push/clone, and a redeploy persistence check.

The lookup-first path adds one GET to new creation and removes a rejected POST
from existing-remote acquisition. Avoiding provisioning during cleanup removes
an entire second retry cycle. Fresh test UUIDs still create real projects, so
eliminating redundant POSTs does not eliminate legitimate creation load; the
dedicated service must be sized and configured for that workload.
