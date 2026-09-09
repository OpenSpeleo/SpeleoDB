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

The create endpoint's `GitlabCreateError` does not mean the repository already
exists. It can also describe validation, permission, throttling, or server
errors. Treating all such errors as duplicates can trigger repeated attempts
to clone a repository that was never created while hiding the original error.

Creation now uses python-gitlab's request-scoped transient retry support. The
retry count is `DJANGO_GIT_RETRY_ATTEMPTS - 1`, giving five total attempts with
the current setting. This uses the library's status classification and
exponential backoff, and honors GitLab's rate-limit headers. Authentication and
permission failures are not retried as transient failures. See the client's
[retry documentation](https://python-gitlab.readthedocs.io/en/stable/api-usage-advanced.html#transient-errors).

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

`test_preload_git_history.py` uses a temporary Git working directory and local
bare remotes. Only the GitLab repository acquisition boundary is substituted;
clone, checkout, pull, commit traversal, and database reconstruction execute
normally. These tests run in light/offline mode and verify reconstruction after
the command removes its working copies.

`test_gitlab_manager.py` exercises the actual python-gitlab client against
simulated HTTP responses. Coverage includes transient recovery and exhaustion,
rate-limit delay headers, authorization failures, confirmed conflicts, missing
repositories, lookup failures, and an ambiguous create followed by a duplicate.
`test_git_retry.py` verifies clone recovery and sanitized diagnostics in both
DEBUG retry logs and final tracebacks.

Existing GitLab integration coverage remains in separate test modules, including
`speleodb/git_engine/tests/test_tree_to_json.py` and
`speleodb/surveys/tests/test_project_git_history.py`. Those tests retain their
`skip_if_lighttest` marker and require provisioned GitLab and storage services.
Their service availability is distinct from the command's history-cache behavior.

## Performance and limits

Successful creation adds no requests. The existing-repository path adds one
confirmation GET after the rejected create. Retries add requests and delays
only for failures; the API retry budget is separate from the clone budget.
These are attempt limits, not a total elapsed-time deadline.

The preload tests no longer create external repositories or depend on concurrent
CI jobs sharing a GitLab group. Other live integration tests still need isolated
test resources and must not overlap a group-wide cleanup. The fix does not
establish which remote status caused the original CI failure because the old
exception handling discarded it.

## User-project cleanup

`wipe_test_user_projects` removes a Django project only after the remote delete
succeeds or an explicit GitLab lookup returns HTTP 404. A permission error,
throttled request, server failure, or network exception does not establish that
the remote is absent: the command propagates the failure and preserves the
local record. This prevents a temporary outage from turning cleanup into
unintended local data loss. Lookup and deletion have separate error boundaries;
a failed remote delete also preserves the database record.

Command tests simulate the remote outcomes against a real test database,
including successful deletion, confirmed absence, permission/transport errors,
and failed remote deletion. They never invoke live cleanup.

## Shared REST policy

`GitlabClient` owns the REST request policy for the application manager and the
test-group maintenance command. Every request has a 30-second connect/read
timeout and at most `DJANGO_GIT_RETRY_ATTEMPTS` attempts by default, including
authentication and each pagination request. Transient retries are enabled for
GET/HEAD reads. Writes must explicitly opt in; project creation retains its
existing retry-and-confirm-conflict contract. The SDK's bounded rate-limit
handling remains enabled for all methods. This is not an end-to-end deadline:
pagination, backoff, and server-directed rate-limit delays add elapsed time.

The SDK raises operation-specific `GitlabGetError` and `GitlabListError`, not
`GitlabHttpError`, at the object-manager boundary. History and branch helpers
return no data only for an explicit 404. Permission, transport, and server
failures propagate; the model must not misrepresent them as an empty history.
Only successful project lookups are cached. Reauthentication clears the cache
so cached objects cannot retain an obsolete client, and history/branch 404s
invalidate cached numeric project IDs so the same path can be rediscovered
after repository recreation. A failed authentication never leaves a partially
initialized client installed on the singleton.

Simulated HTTP regressions exercise the real SDK for request timeouts, bounded
retries, authentication, history and branch reads, and recovery after a missing
project. Successful calls add no extra requests. Bootstrap provisioning keeps
its separate policy because its token creation/revocation lifecycle differs
from normal application reads.
