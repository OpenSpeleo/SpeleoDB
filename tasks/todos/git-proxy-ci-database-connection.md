# Git Proxy CI Database Connection

## Plan

- [x] Reproduce and trace the PostgreSQL-only connection closure through the Git
      proxy streaming disconnect test.
- [x] Replace the test's full Django response shutdown with a targeted stream
      disconnect that exercises upstream cleanup without emitting a global
      request-finished lifecycle signal.
- [x] Add an explicit regression assertion that the Django database connection
      remains usable after the simulated client disconnect.
- [x] Document the test-boundary rationale and CI/local database difference.
- [x] Run the focused Git proxy tests, Python lint/type checks, and diff checks.

## Review

The CI failure came from the partial-stream disconnect test calling Django's
`response.close()` directly. That bypassed the test client's streaming wrapper
and emitted `request_finished` while PostgreSQL was inside the enclosing
`TestCase` transaction. PostgreSQL closed that connection; the local in-memory
SQLite backend ignored the same close and masked the bug.

The test now closes Django's test-client stream wrapper after consuming one
chunk. This retains the production-relevant upstream cleanup assertion while
using Django's own `request_finished` isolation. It also refreshes the project
from the database afterward so PostgreSQL CI explicitly proves the transaction
connection remains usable. Production proxy behavior was not changed.

Verification results:

- `uv run pytest -q speleodb/git_proxy/tests.py`: 17 passed, 3 subtests passed.
- Disconnect test followed by the previously affected receive-pack test: 2
  passed.
- `uv run ruff check speleodb/git_proxy/tests.py`: passed.
- `uv run ruff format --check speleodb/git_proxy/tests.py`: passed.
- `uv run mypy speleodb/git_proxy`: passed.
- `git diff --check`: passed.
- The full local suite was attempted and stopped after 322 passes and 30
  failures because the configured RustFS endpoint at `localhost:9000` was not
  running; the failures were unrelated media-storage integration tests.
