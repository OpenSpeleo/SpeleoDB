# Git retry test isolation

The Git retry tests combine real local repositories and subprocess deadlines
with mocked remote operations and retry delays. Keeping process cleanup real
is necessary to verify that a hanging hook is terminated and reaped, and that
a commit already created before the timeout is not repeated.

Patch `speleodb.utils.helpers.time`, then assert against `mock_time.sleep`.
Do not patch `speleodb.utils.helpers.time.sleep`: the helper imports the shared
stdlib `time` module, so changing its `sleep` attribute also changes the sleep
used by Python's subprocess implementation.

On POSIX, `Popen.wait(timeout=...)` uses short sleeps while checking whether the
child has exited. A global sleep mock both suppresses those waits and records
them as apparent application retries. Whether this happens depends on when the
operating system reaps the process. Replacing only the helper's module reference
keeps retry assertions separate from subprocess cleanup without modifying
production code or deadlines.

The post-commit hook regression exercises a real hanging hook, checks that HEAD
advanced by exactly one commit, asserts one commit invocation, and verifies no
application retry sleep occurred. Positive retry tests still verify attempt
counts and exponential delay values.

Run the affected tests inside the existing Docker container:

```sh
docker compose -f local.yml exec -T django pytest \
  speleodb/git_engine/tests/test_git_retry.py \
  speleodb/git_engine/tests/test_git_checkout.py \
  speleodb/git_engine/tests/test_gitlab_manager.py \
  speleodb/utils/tests/test_retry.py -q
```

Verification on 2026-09-15: the original timeout test failed with subprocess
polling sleeps recorded by the mock. With isolated mocks, all 70 tests and 31
subtests above passed in 7.21 seconds. The full application suite was not rerun
for this test-only change.
