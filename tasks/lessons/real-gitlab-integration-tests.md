# Verify GitLab behavior through real services

The user explicitly rejected mocked GitLab/error-path verification during the
September 2026 CI investigation. Use real GitLab, Git subprocesses, and database
transactions for the affected integration tests. Do not introduce HTTP fakes,
patched methods, or renamed test doubles as substitutes.

- A generic HTTP 500 and rollback flag do not establish which operation failed.
  Assert the actual failure cause and observable effects; verify prerequisites
  succeed before provoking the intended failure.
- An error cleanup path must never access a lazy property that provisions the
  external resource whose creation just failed.
- Authenticated requests can be rate limited. Check token presence and actual
  identity separately from quota, shared CI traffic, and retry amplification.
- Treat an external-service outage as a failed integration run. Do not conceal
  it with skipped tests or weakened assertions.
- The user rejected booting GitLab per CI job because startup/provisioning is
  too expensive. Diagnose and fix use of the existing remote service. Verify its
  hostname/version/quota instead of presenting a newer GitLab limiter as
  confirmed merely because local GitLab is older.
- When the user chooses a dedicated remote test GitLab, keep it running between
  jobs. Persist configuration secrets as well as repositories and the database;
  an environment name alone does not prove that CI uses the new service.
- Verify database transaction semantics on local SQLite and CI PostgreSQL. Keep
  the normal local run, then explicitly select `TEST_DATABASE_URL` for the
  additional PostgreSQL run. Coordinate suites sharing the same test database
  instead of running competing pytest processes.
- When removing test doubles, update coverage claims. Real transport refusal
  proves connection retry behavior; it cannot prove invented 429/5xx sequences.
  Supported observation hooks may inspect real requests/events but must not
  manufacture outcomes or weaken cause-specific assertions.
- Audit frontend upload tests as well as Python tests. Replacing XMLHttpRequest
  or the upload component can conceal the same failure-path defects. Keep pure
  DOM checks separate and exercise transport through the real Django service.
- Keep full frontend suites and type checking serial on the shared Docker VM
  when GitLab is running; observed resource stalls can cause unrelated test
  timeouts. Diagnose the stall and rerun affected checks without raising their
  correctness thresholds.

## Persistent GitLab deployment

- An uploaded Dockerfile build does not attach a Docker image or GitHub source
  in Railway. When the user wants upstream image updates, connect the official
  image explicitly, configure and read back the update policy, and give the
  service a durable startup command. Keep volume initialization/configuration
  files outside the replaceable image and snapshot them before migration.
- GitLab minor upgrades have required intermediate stops. Configure patch-only
  image updates and document the maintenance window; distinguish an enabled
  policy from observing a future automatic update.
- Check both public and internal listener ports. Omnibus Puma also defaults to
  TCP port 8080; when Railway-facing NGINX uses 8080, set Puma's optional TCP
  listener to 8081 and retain Workhorse's normal Unix-socket connection.
- Persistence changes startup assumptions. Omnibus's runtime cleanup does not
  follow a symlink used to mount `/var/opt/gitlab` on a Railway volume. Clear
  only its bounded PID/socket selection with `find -H` before official startup,
  including after interrupted shutdowns; never clear database or secret files.
- An instance-setting PUT can ignore an unknown key. Use the actual
  `project_create_limit` name and verify the returned value and a fresh GET. Do
  not infer success from HTTP 200 alone.
- To verify a real 429, use an isolated private test group and bot before CI
  traffic begins. Scope `namespace_create_rate_limit` only to that bot user,
  require the first successful creation, and observe actual subsequent 429s and
  attempt counts. Refuse a preexisting explicit flag or competing traffic.
- Settings and feature-flag reads can be cached. Keep a private restoration
  journal, allow cache propagation, and verify cleanup by readback. A completed
  test is not complete infrastructure cleanup; revoke temporary credentials and
  restore settings even when the assertion or first cleanup attempt fails.
- Use separate short-lived administrative and group-scoped CI credentials.
  Verify bootstrap-token revocation by an actual unauthorized response and
  remove the bootstrap Railway variable so restart cannot reprovision it.
- A successful first deployment does not prove restart persistence. Track the
  exact final deployment and reread authenticated identity and an existing Git
  commit afterward. Likewise, a user's reported GitHub secret update does not
  establish which values an actual Actions job used.
- Report observed resource use and capacity separately. A 5 GB volume with 0.603
  GB used and an idle memory sample do not prove capacity under a sustained test
  workload; keep deletion retention and usage monitoring explicit.

## Production transaction and live-service assertions

- Preserve ATOMIC_REQUESTS when replacing test database settings. Query-count
  tests inside TestCase then include SAVEPOINT and RELEASE; update budgets by
  exactly that fixed overhead, without allowing extra application queries.
- Assert the forbidden side effect, such as a creation POST for an existing
  remote. A valid retry can add another GET after a real server failure; an
  exact one-request assertion would reject supported retry behavior.
- Keep host and container mypy caches separate when their Python environments
  differ. Verify failures with an isolated cache before changing source code.
- A diagnostic isolated-cache pass does not verify the user's normal command.
  Repair its cache configuration and rerun that exact command before completion.
- Enabling ATOMIC_REQUESTS affects static views as well as write APIs. Preserve
  database-free endpoint tests with explicit non_atomic_requests on those views;
  do not globally grant database access to tests or undo upload transactions.
- SQLite does not enforce VARCHAR length as PostgreSQL does. Use a real portable
  constraint when testing generic import rollback, and prove both database
  paths.
- Git diagnostics can differ across installed versions. Accept the observed
  equivalent missing-tree messages while asserting the operation, requested SHA,
  exit status, and preserved repository/database state.
- Keep non-secret numeric identifiers in Actions variables. A one-digit secret
  masks that digit throughout CI logs. Publish all consuming workflow changes
  before deleting the old secret to avoid interrupting CI or scheduled cleanup.
- Exercise management commands through the real Makefile/CLI entrypoint.
  `manage.py` defaults to local settings, while a test helper selecting test
  settings can hide protocol/configuration differences. The GitLab hostname
  excludes the scheme; remote cleanup must select HTTPS before sending writes.
- A server-side 202 does not prove the SDK accepted the operation: a preceding
  301 can cause python-gitlab to raise RedirectError afterward. Report safe
  exception types and HTTP status rather than hiding every failure behind one
  generic message, and never dump credentials to diagnose redirects.
- Verify repeated cleanup during GitLab's deletion retention period. A
  successful DELETE marks the project; repeating it can return HTTP 400. Skip
  the explicitly marked state rather than swallowing unrelated API failures.
