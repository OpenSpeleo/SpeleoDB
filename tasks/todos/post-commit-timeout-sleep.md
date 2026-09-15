# Diagnose post-commit timeout retry assertion

## Plan

- [x] Trace the unexpected sleep in the failing test inside Docker.
- [x] Fix its cause while preserving the completed-commit retry guard and real
      subprocess timeout coverage.
- [x] Run the relevant retry tests and scoped checks inside Docker.
- [x] Record the cause, verification, and lesson.

The user reported a single failure after the full suite. Keep this fix scoped to
that failure; preserve unrelated staged changes and avoid service restarts.

## Review

Reproduced the reported failure inside Docker: the mock captured 15 sleeps
starting at 0.001 seconds and capped at 0.05 seconds. Installed Python's
`Popen._wait(timeout)` uses exactly those delays to reap a child. Patching
`helpers.time.sleep` mutates the shared stdlib module, so subprocess cleanup was
counted as application retries and its real waits were suppressed.

The fix replaces only the helper's `time` reference in tests and asserts on that
mock's `sleep`. All 20 instances of this helper patch across four test modules
follow the same isolation rule. The real post-commit timeout test also asserts
exactly one commit invocation. Application retry/deadline code remains
unchanged.

Docker verification passed: all four affected modules (70 tests and 31 subtests,
7.21 seconds), scoped Ruff lint, and mypy on the four changed Python files.
Ruff's formatter corrected two function signatures. Independent review found no
lost assertions or unintended behavior changes. The full suite was not rerun.
See [the test isolation documentation](../../docs/git-retry-testing.md).
