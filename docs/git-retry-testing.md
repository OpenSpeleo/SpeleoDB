# Git retry testing

Retry tests exercise actual failed operations, real waiting and the real clock.
Never script exceptions or canned error responses to manufacture retries. Do not
replace `time`, `sleep`, Django's clock, or subprocess timing. Do not
manufacture outages or lock contention solely to force backoff or measure its
delays. Retry-helper tests cover immediate success, single-attempt error
propagation and invalid configuration without running artificial backoff
sequences.

Git tests use small local repositories and real subprocess deadlines. This is
necessary to prove that a hanging hook is terminated and reaped, and that a
commit created before a timeout is not repeated. Native Git hooks and actual
connection refusal provide failures without replacing Git commands.

Live GitLab pool provisioning and lifecycle tests use the manager's actual
lookup, bounded retries, elapsed waiting, creation and cleanup. Retry coverage
must use an actual failed call, such as connection refusal or an unavailable
local repository. Do not fabricate SDK outcomes or replace fake timers with long
waits around scripted failures.

`BoundedGit.execute()` retains GitPython's positional and keyword parameter
contract. It normalizes both forms into the existing deadline handling so
positional input streams, output options, and process timeouts cannot bypass
that policy. Regression tests compare positional synchronous execution with
GitPython and verify that positional streamed execution still enforces its
deadline. Normalization adds only a fixed-size option mapping per command.

Run the affected tests inside the existing application container:

```sh
docker exec -w /app speleodb-monorepo-django pytest \
  speleodb/git_engine/tests/test_git_retry.py \
  speleodb/git_engine/tests/test_git_checkout.py \
  speleodb/git_engine/tests/test_gitlab_manager.py \
  speleodb/utils/tests/test_retry.py -q
```
