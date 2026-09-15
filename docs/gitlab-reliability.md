# GitLab reliability

## Intent and ownership

`GitlabManager.create_or_clone_project()` supplies the local working copy used
by project uploads, history reconstruction, and repository warming. GitLab
owns the remote repository; PostgreSQL's `ProjectCommit` rows are a rebuildable
history cache. A `ProjectFactory` creates only a database row. The initial Git
commit is created when the repository is first initialized, not by the factory.

The preload command calls `project.git_repo`, checks out and pulls the default
branch, and reconstructs database history. It logs per-project failures and
continues processing, then removes each local working copy in `finally`.
Consequently, a failed clone leaves no history to cache. An assertion about
missing commits can be a symptom of an earlier remote failure.

## Creation and retries

Repository acquisition first looks up the configured namespace/project UUID.
An existing remote is cloned without a creation POST. Only an explicit HTTP
404 permits creation; authentication, throttling and other lookup failures
propagate before the local working directory is changed.

The create endpoint's `GitlabCreateError` does not mean the repository already
exists. It can also describe validation, permission, throttling, or server
errors. Treating all such errors as duplicates can trigger repeated attempts
to clone a repository that was never created while hiding the original error.

Creation uses the shared `BoundedGitlabClient` transport policy, with
`DJANGO_GIT_RETRY_ATTEMPTS` total attempts (currently five). The SDK still owns
request serialization and operation-specific exceptions, but its internal
retries are disabled. Application retries sleep 1/2/4/8 seconds, doubling up to
the configured 30-second cap. Server delay headers cannot replace that schedule.
Authentication and permission failures are not retried as transient failures.

A create response with HTTP 400 or 409 can indicate a duplicate path. Before
cloning, the manager performs an uncached lookup of the exact configured
namespace/project UUID with the same transient retry policy:

- A successful lookup confirms that cloning is appropriate.
- HTTP 404 preserves the original create error, including its status and body.
- Other lookup failures propagate instead of falling through to clone.
- Other create failures propagate directly after the client's applicable retries.

This also handles a create request that succeeded remotely but returned a
transient error: a subsequent duplicate response can be resolved by confirming
the repository exists. New repositories retain their initial commit behavior;
existing empty repositories receive their initial commit after cloning.

## Git subprocess retries and working-copy recovery

Clone, fetch, pull, push, and credential-bearing origin configuration share a
five-attempt Git retry policy and 1/2/4/8-second backoff. Before a failure reaches
the retry logger, URL credentials and known
encoded/decoded token values are removed from the command, status, stderr, and
stdout. The final `GitBaseError` includes the sanitized repository URL, Git
exit status, and error details. Raw credential-bearing exception chains are
not attached to the raised exception.

`GitRepo` installs `BoundedGit` through GitPython's command-wrapper extension.
Each finite Git command has a 60-second deadline and a separate process group;
termination includes helpers and hooks, with a five-second bounded reap. This
also covers streamed clone/fetch commands for which the SDK's execution timeout
is insufficient. Commit hooks run through the supervised Git CLI. If HEAD has
already advanced before a hook times out, the failure is surfaced without
creating another commit. Author, committer, and exact message bytes are retained.
Cached `cat-file` readers keep their normal lifetime; filesystem/object database
reads are not subject to a whole-operation deadline.

Initial publication explicitly selects the configured unborn branch and never
pulls from an empty remote. Existing commits or remote refs prohibit initial
publication: an unset remote HEAD does not establish that a repository is empty.
Normal checkout switches to an existing local branch before a fast-forward-only
pull, including when returning from detached historical commits. A missing local
branch is created only from a verified remote-tracking branch after a successful
pruning fetch. Dirty-worktree, missing-branch, and transport failures propagate
instead of creating an arbitrary branch. Historical commits already available
locally need no network request.

Download processors use the same rules: a latest-version download restores and
updates the default branch, while fetching a missing historical commit leaves
the current checkout unchanged. Both use `Project.ensure_git_origin()` before
network access, so a changed GitLab token, host, or group is repaired on downloads
as well as normal checkout. Already-local historical downloads need no repair
or remote access.

The project wrapper repairs an incorrect origin URL in place using the same
canonical URL builder as creation. It never deletes and reclones a working copy
merely because checkout or pull failed; transient outages are not evidence of
local corruption, and deleting files can destroy uncommitted work. History is
rebuilt only after successful checkout/pull. Actual object corruption requires
an explicit recovery decision rather than an automatic destructive fallback.

Local bare-repository regressions cover initialization, detached checkout,
remote updates, missing branches, dirty files, URL repair, and outage preservation.
Retry tests assert credential-safe logs and tracebacks for each remote operation.
Successful existing-branch pulls need no preliminary fetch; only an absent local
branch or commit adds one. Failure backoff gives the remote time to recover but
does not classify authentication or corrupt-object Git stderr as transient.

## Tests and external dependencies

`test_preload_git_history.py` uses temporary Git working directories and real
GitLab remotes. Clone, checkout, pull, commit traversal, and database
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
Their service availability is distinct from the command's history-cache behavior.

### Diagnosing CI stalls

CI runs pytest with `-vvv -s -o faulthandler_timeout=60 --durations=20`. Verbose
output identifies individual tests, and `-s` disables output capture.
Pytest's built-in faulthandler prints all
Python thread stacks when a test takes longer than 60 seconds, including setup
and teardown. This reports where execution is waiting without aborting the
test or changing its retry behavior. The duration summary identifies slow
phases when the run completes. These diagnostics require no extra dependency.

GitHub can delay displaying an unfinished progress line, so the last visible
module is not proof that it owns the blocked operation. Inspect the stack dump
before attributing a stall to database cleanup, Git transport, or REST retries.
The upload tests use real GitLab; a successful local Compose run establishes
local behavior but does not establish the health of CI's remote GitLab service.

## Performance and limits

New creation adds one lookup GET before the POST. An existing repository needs
one lookup GET and no rejected creation POST. Retries add requests and delays
only for failures; the API retry budget is separate from the clone budget.
These are attempt limits, not a total elapsed-time deadline.

Preload and other live integration tests create external repositories. They need
isolated test resources and must not overlap a group-wide cleanup. The retry wrapper
preserves remote status and body in SDK exceptions. Logs record attempt counts
and delays without exposing credentials.

## User-project cleanup

`wipe_test_user_projects` removes a Django project only after the remote delete
succeeds or an explicit GitLab lookup returns HTTP 404. A permission error,
throttled request, server failure, or network exception does not establish that
the remote is absent: the command propagates the failure and preserves the
local record. This prevents a temporary outage from turning cleanup into
unintended local data loss. Lookup and deletion have separate error boundaries;
a failed remote delete also preserves the database record.

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
timeouts are rejected. This is not an end-to-end deadline: pagination and bounded
backoff add elapsed time, and an HTTP read timeout measures inactivity rather
than complete transfer duration.

The SDK raises operation-specific `GitlabGetError` and `GitlabListError`, not
`GitlabHttpError`, at the object-manager boundary. History and branch helpers
return no data only for an explicit 404. Permission, transport, and server
failures propagate; the model must not misrepresent them as an empty history.
Only successful project lookups are cached. Reauthentication clears the cache
so cached objects cannot retain an obsolete client, and history/branch 404s
invalidate cached numeric project IDs so the same path can be rediscovered
after repository recreation. A failed authentication never leaves a partially
initialized client installed on the singleton.

Real-service regressions exercise authentication, history and branch reads,
recovery after a missing project, and token propagation on actual requests.
Reserved non-listening sockets exercise bounded connection retries. These tests
do not manufacture HTTP 429/5xx responses or delay headers. Standalone bootstrap
provisioning uses the same pure-Python client with its existing 15-second request
timeout and explicit transient-write opt-in. `compose/setup` invokes provisioning
as a module so it can import this policy without initializing Django.

## Confirmed September 2026 CI stall

Run `34997387739`, job `104476947867`, dumped its stack at
2026-09-15 16:52:14 UTC inside python-gitlab's `handle_retry_on_status` sleep.
The blocked operation was project creation in the first Compass upload test;
the last visible exploration-lead test and its teardown had completed. The
installed SDK accepts a server-directed delay outside its HTTP timeout, even
when the retry count is finite. The stack confirms that waiting path; it does
not reveal the exact HTTP status or header value. The application now owns
bounded retry sleeps. Earlier synthetic delay-header regressions were removed
when GitLab tests were converted to real services; do not treat connection
refusal coverage as verification of those HTTP-header sequences.

The later project-creation 429 investigation also removed duplicate creation
POSTs and lazy repository provisioning during upload cleanup. Upload failure
tests now require successful real provisioning and assert the intended exception
and persisted transaction outcome. See [real GitLab integration tests](ci-gitlab-testing.md)
for the CI service boundary, authentication evidence, and quota uncertainty.

See [bounded retries](bounded-retries.md) for the broader retry audit and
verification status.
