# GitLab reliability

## Intent and ownership

`GitlabManager.create_or_clone_project()` supplies the local working copy used
by project uploads, history reconstruction, and repository warming. GitLab owns
the remote repository; PostgreSQL's `ProjectCommit` rows are a rebuildable
history cache. A `ProjectFactory` creates only a database row. The initial Git
commit is created when the repository is first initialized, not by the factory.

The preload command calls `project.git_repo`, resets the default branch to its
remote revision, and reconstructs database history. It logs per-project failures
and continues processing, then removes each local working copy in `finally`.
Consequently, a failed clone leaves no history to cache. An assertion about
missing commits can be a symptom of an earlier remote failure.

## Creation and retries

Repository acquisition first looks up the configured namespace/project UUID. An
existing remote is cloned without a creation POST. HTTP 404 permits creation
after the existing bounded lookup retry policy is exhausted. Authentication,
throttling and other lookup failures propagate before the local working
directory is changed.

The create endpoint's `GitlabCreateError` does not mean the repository already
exists. It can also describe validation, permission, throttling, or server
errors. Treating all such errors as duplicates can trigger repeated attempts to
clone a repository that was never created while hiding the original error.

Creation uses the shared `BoundedGitlabClient` transport policy, with
`DJANGO_GIT_RETRY_ATTEMPTS` total attempts (currently five). The SDK still owns
request serialization and operation-specific exceptions, but its internal
retries are disabled. Application retries sleep 1/2/4/8 seconds, doubling up to
the configured 30-second cap. Server delay headers cannot replace that schedule.
Authentication and permission failures are not retried as transient failures.

A create response with HTTP 400 or 409 can indicate a duplicate path. Before
cloning, the manager performs an uncached lookup of the exact configured
namespace/project UUID:

- A successful lookup confirms that cloning is appropriate.
- HTTP 404 preserves the original create error after bounded confirmation
  retries, including its status and body.
- Other lookup failures propagate instead of falling through to clone.
- Other create failures propagate directly after the client's applicable
  retries.

Both acquisition lookups opt into `retry_not_found=True` so temporary missing
responses can resolve within the transport's bounded retry policy. Transient
server errors and connection failures retain their existing bounded retry
policy. The conflict lookup never restarts creation, and preserves the original
create error if the repository remains absent.

This also handles a create request that succeeded remotely but returned a
transient error: a subsequent duplicate response can be resolved by confirming
the repository exists. New repositories retain their initial commit behavior;
existing empty repositories receive their initial commit after cloning.

## Local API redirects

Local GitLab advertises `http://localhost:9080` for browser access, while
bridged Compose clients reach it at `http://gitlab:9080`. After a project is
renamed (including GitLab's delayed-deletion rename), looking up its old path
returns an absolute redirect to its numeric API ID using the advertised host.
Following that URL unchanged would connect to the application container's own
loopback.

Local callers already opt into `keep_base_url=True`. The shared
`BoundedGitlabClient` extends the SDK's pagination policy to HTTP redirects via
a Requests session that resolves API GET/HEAD redirect targets against the
configured origin. It preserves the target path, query and fragment, including
GitLab installation subpaths. Relative redirects, non-API destinations, write
redirects, and clients without the option keep Requests' existing behavior.
Original response headers remain available for diagnostics; Requests still owns
redirect limits and the SDK still handles responses and errors. This adds no
requests or retries and leaves browser URLs and container configuration intact.

Pure redirect-policy tests cover origin preservation and its boundaries. The
real write-check and manager deletion lifecycles verify cleanup through the old
project path using their existing repository allocations. Cleanup must still
prove a real 404 or a deletion mark; a connection failure is never success.

## Git subprocess retries and working-copy recovery

Clone, fetch, push, and credential-bearing origin configuration share a
five-attempt Git retry policy and 1/2/4/8-second backoff. Before a failure
reaches the retry logger, URL credentials and known encoded/decoded token values
are removed from the command, status, stderr, and stdout. The final
`GitBaseError` includes the sanitized repository URL, Git exit status, and error
details. Raw credential-bearing exception chains are not attached to the raised
exception.

`GitRepo` installs `BoundedGit` through GitPython's command-wrapper extension.
Each finite Git command has a 60-second deadline and a separate process group;
termination includes helpers and hooks, with a five-second bounded reap. This
also covers streamed clone/fetch commands for which the SDK's execution timeout
is insufficient. Commit hooks run through the supervised Git CLI. If HEAD has
already advanced before a hook times out, the failure is surfaced without
creating another commit. Author, committer, and exact message bytes are
retained. Cached `cat-file` readers keep their normal lifetime;
filesystem/object database reads are not subject to a whole-operation deadline.

The CLI validates identities more strictly than GitPython's former direct
serialization. At the commit boundary, missing/whitespace-only author names and
names made entirely of Git-disallowed characters use `NO NAME`; author email,
configured committer, and usable names are preserved. This includes period-only
names rejected by the deployed Git 2.39.5. Account validation, database repair,
and a nonblank-name constraint prevent new unnamed rows; the fallback also
protects stale in-memory users. See [user identity](user-identity.md) for the
signup lifecycle, migration, and regression coverage. Historical commits are not
rewritten, and the fallback adds no SQL or network calls.

Initial publication explicitly selects the configured unborn branch and never
pulls from an empty remote. Existing commits or remote refs prohibit initial
publication: an unset remote HEAD does not establish that a repository is empty.
GitLab is authoritative for the application checkout. Every default-branch sync
first performs a forced, pruning fetch and verifies the configured remote
branch. `GitRepo.reset_default_branch_to_remote()` then force-creates the local
branch at that fetched commit and resets the index and tracked files, including
when HEAD was detached. This has hard-reset semantics: local-only commits,
divergent history and uncommitted tracked changes are discarded from the active
checkout. The branch setting in `config/settings/base.py` selects `master`.
There is no merge or fast-forward requirement. Unrelated untracked files remain;
untracked paths obstructing tracked remote files are replaced by Git. No blanket
clean is performed. A failed fetch or absent remote branch leaves HEAD and files
unchanged instead of resetting to a stale cached ref.

`Project.checkout_commit_or_reset_default_branch()` owns synchronization
followed by database-history reconstruction. After a successful default-branch
reset and complete history traversal, it reconciles cached commits to the
reachable upstream history in one database transaction. Rewritten or removed
revisions stop contributing to commit counts, latest-commit metadata and map
artifact selection. Their artifact rows are retired through the normal cascade;
stored objects remain until the existing explicit project purge. Explicit
historical checkouts only populate history and never remove newer cached
revisions. The default sync adds one local history traversal; it does not add
network calls or purge project storage. Upload preparation, the Git explorer,
blob lookup fallback, latest downloads, preload and clone recovery share the
same default-branch policy. Explicit historical checkouts still select the
requested commit, and historical commits already available locally need no
network request.

Download processors use the same rules: a latest-version download resets the
default branch to its fetched remote revision, while fetching a missing
historical commit leaves the current checkout unchanged. Both use
`Project.ensure_git_origin()` before network access, so a changed GitLab token,
host, or group is repaired on downloads as well as normal checkout.
Already-local historical downloads need no repair or remote access.

The project wrapper repairs an incorrect origin URL in place using the same
canonical URL builder as creation. It never deletes and reclones a working copy
merely because checkout or fetch failed; transient outages are not evidence of
local corruption. History is rebuilt only after successful checkout/reset.
Actual object corruption requires an explicit recovery decision rather than an
automatic destructive fallback.

Local bare-repository regressions cover initialization, detached checkout,
remote updates, local-ahead and divergent branches, rewritten remote history,
dirty tracked files, untracked-path collisions, missing branches and failure
before reset. The explorer API regression verifies that divergent local history
cannot prevent reading a requested revision. Every default sync needs one fetch;
historical reads fetch only missing objects. Credential-redaction tests protect
remote error reporting. Failure backoff gives the remote time to recover but
does not classify authentication or corrupt-object Git stderr as transient.

## Tests and external dependencies

`test_preload_git_history.py` uses temporary Git working directories and real
GitLab remotes. Clone, checkout, reset, commit traversal, and database
reconstruction execute normally. The tests verify reconstruction after the
command removes its working copies, then clone the remote again to prove that
cleanup preserved its history. They require the live-service test mode.

`test_gitlab_manager.py` exercises the actual python-gitlab client against the
configured GitLab service. Coverage includes initial publication, existing and
empty remote repositories, real invalid-namespace and authentication responses,
and the absence of a duplicate POST when cloning an existing remote.
`test_git_retry.py` uses actual Git commands to verify retries and sanitized
diagnostics in both retry logs and final tracebacks.

Existing GitLab integration coverage remains in separate test modules, including
`speleodb/git_engine/tests/test_tree_to_json.py` and
`speleodb/surveys/tests/test_project_git_history.py`. Those tests retain their
`skip_if_lighttest` marker and require provisioned GitLab and storage services.
Their service availability is distinct from the command's history-cache
behavior.

### Diagnosing CI stalls

CI invokes `make test-py`, which runs one plain `pytest` command for the entire
suite. Shared settings in `pyproject.toml` retain normal output capture, set
`faulthandler_timeout = 240`, and enable `--durations=20`. Pytest's built-in
faulthandler prints all Python thread stacks when a test takes longer than 240
seconds, including setup and teardown. This reports where execution is waiting
without aborting the test or changing its retry behavior. The duration summary
identifies slow phases when the run completes. These diagnostics require no
extra dependency.

Tests must not hold a competing scheduler lock solely to exhaust its backoff
budget. The former full-budget standby test has been removed; the diagnostic
threshold is a hang guard, not a target test duration.

GitHub can delay displaying an unfinished progress line, so the last visible
module is not proof that it owns the blocked operation. Inspect the stack dump
before attributing a stall to database cleanup, Git transport, or REST retries.
The upload tests use real GitLab; a successful local Compose run establishes
local behavior but does not establish the health of CI's remote GitLab service.

### Git explorer error reporting

`ProjectGitExplorerApiView` catches Git and GitLab failures, logs a traceback,
calls `sentry_sdk.capture_exception`, and returns a JSON HTTP 500 response.
Django also logs returned 5xx responses, so an additional request error log does
not imply the exception escaped its handler. The checkout error wording covers
the preceding default-branch fetch/reset too; inspect the underlying sanitized
Git failure to identify which operation failed.

The `git-view` controller currently logs failed explorer requests to the browser
console without rendering an error notice. Treat missing UI feedback separately
from backend exception capture. Production Sentry initialization depends on
`SENTRY_DSN`; a capture call or local test proves neither remote delivery nor
that a missing-repository message means deletion rather than
access/configuration failure. Confirm service configuration and received events
when investigating an operational report. Existing explorer regressions verify
the response and capture boundary without assuming that the external observer
received an event.

## Performance and limits

New creation follows the bounded existence lookup before the POST, including
missing-project backoff after HTTP 404. An existing repository needs one
successful lookup GET and no rejected creation POST. Retries add requests and
delays for missing responses and transient failures; the API retry budget is
separate from the clone budget. These are attempt limits, not a total
elapsed-time deadline.

Preload and other live integration tests create external repositories. They need
isolated test resources and must not overlap a group-wide cleanup. The retry
wrapper preserves remote status and body in SDK exceptions. Logs record attempt
counts and delays without exposing credentials.

## User-project cleanup

`wipe_test_user_projects` removes a Django project only after the remote delete
succeeds or an explicit GitLab lookup returns HTTP 404. A permission error,
throttled request, server failure, or network exception does not establish that
the remote is absent: the command propagates the failure and preserves the local
record. This prevents a temporary outage from turning cleanup into unintended
local data loss. Lookup and deletion have separate error boundaries; a failed
remote delete also preserves the database record.

Command tests use real GitLab repositories and a real test database to check
successful deletion, confirmed absence, and authentication/transport failures.
Group-wide cleanup tests create their own disposable subgroup and use real stdin
pipes to verify confirmation, cancellation, and dry-run behavior. They never
target the suite's entire shared group.

## Shared REST policy

`GitlabClient` owns the REST request policy for the application manager and the
test-group maintenance command. Every request has a 30-second connect/read
timeout and at most `DJANGO_GIT_RETRY_ATTEMPTS` attempts by default, including
authentication and each pagination request. Transient retries are enabled for
GET/HEAD reads. Writes must explicitly opt in; project creation retains its
existing retry-and-confirm-conflict contract. Rate-limit responses are retried
for all methods unless explicitly disabled. The shared wrapper owns all retry
sleeps; SDK retries are disabled. Caller overrides can reduce attempts/timeouts
but cannot raise configured limits, and negative retry counts or nonfinite
timeouts are rejected. This is not an end-to-end deadline: pagination and
bounded backoff add elapsed time, and an HTTP read timeout measures inactivity
rather than complete transfer duration.

The SDK raises operation-specific `GitlabGetError` and `GitlabListError`, not
`GitlabHttpError`, at the object-manager boundary. History and branch helpers
return no data only for an explicit 404. Permission, transport, and server
failures propagate; the model must not misrepresent them as an empty history.
Only successful project lookups are cached. Reauthentication clears the cache so
cached objects cannot retain an obsolete client, and history/branch 404s
invalidate cached numeric project IDs so the same path can be rediscovered after
repository recreation. A failed authentication never leaves a partially
initialized client installed on the singleton.

Real-service regressions exercise authentication, history and branch reads,
recovery after a missing project, token propagation on actual requests, and
immediate HTTP 404 error propagation. Do not manufacture outages solely to force
backoff or script SDK exceptions and canned failure-then-success outcomes.
Reserved non-listening sockets exercise single-attempt failure propagation when
retries are disabled, without disrupting the configured GitLab service. The
live-service and connection-refusal tests do not manufacture HTTP 429/5xx
responses or delay headers. Standalone bootstrap provisioning uses the same
pure-Python client with its existing 15-second request timeout and explicit
transient-write opt-in. `compose/setup` invokes provisioning as a module so it
can import this policy without initializing Django.

## Confirmed September 2026 CI stall

Run `34997387739`, job `104476947867`, dumped its stack at 2026-09-15 16:52:14
UTC inside python-gitlab's `handle_retry_on_status` sleep. The blocked operation
was project creation in the first Compass upload test; the last visible
exploration-lead test and its teardown had completed. The installed SDK accepts
a server-directed delay outside its HTTP timeout, even when the retry count is
finite. The stack confirms that waiting path; it does not reveal the exact HTTP
status or header value. The application now owns bounded retry sleeps. Earlier
synthetic delay-header regressions were removed when GitLab tests were converted
to real services; do not treat connection refusal coverage as verification of
those HTTP-header sequences.

The later project-creation 429 investigation also removed duplicate creation
POSTs and lazy repository provisioning during upload cleanup. Upload failure
tests now require successful real provisioning and assert the intended exception
and persisted transaction outcome. See
[real GitLab integration tests](ci-gitlab-testing.md) for the CI service
boundary, authentication evidence, and quota uncertainty.

See [bounded retries](bounded-retries.md) for the broader retry audit and
verification status.
