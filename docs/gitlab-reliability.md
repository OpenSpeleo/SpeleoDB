# GitLab repository creation and history preload

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

## Clone diagnostics

Clone retains its existing five-attempt Git retry policy and 1/2/4/8-second
backoff. Before a failure reaches the retry logger, URL credentials and known
encoded/decoded token values are removed from the command, status, stderr, and
stdout. The final `GitBaseError` includes the sanitized repository URL, Git
exit status, and error details. Raw credential-bearing exception chains are
not attached to the raised exception.

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
