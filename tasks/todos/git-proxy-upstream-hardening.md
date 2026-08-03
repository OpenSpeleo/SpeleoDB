# Git Proxy Upstream Hardening

## Plan

- [x] Confirm the streaming failure mechanism and choose the response policy.
- [x] Make upstream authentication and forwarded headers explicit and safe.
- [x] Validate upstream status and Git smart-HTTP media types before streaming.
- [x] Stream successful Git payloads byte-for-byte and close upstream responses.
- [x] Replace the commented proxy tests with regression and boundary coverage.
- [x] Document the proxy architecture, failure behavior, and performance
      contract.
- [x] Run focused lint, type, and test checks followed by the backend test
      suite.

## Review

Implemented a strict Git smart-HTTP proxy boundary: client credentials and proxy
headers no longer reach GitLab, upstream authentication no longer appears in the
proxied URL, redirects and invalid responses become sanitized `502` responses,
and valid Git payloads stream byte-for-byte with deterministic connection
cleanup.

Verification results:

- `uv run pytest -q speleodb/git_proxy/tests.py`: 17 passed, 3 subtests passed.
- `uv run ruff check speleodb/git_proxy`: passed.
- `uv run ruff format --check speleodb/git_proxy`: passed.
- `uv run mypy speleodb/git_proxy`: passed.
- `git diff --check`: passed.
- `uv run pytest`: 3,846 passed and 156 skipped. The 16 failures are outside
  `speleodb/git_proxy` and require unavailable local RustFS/GitLab services or
  depend on the current live GitHub release asset URL shape.

An independent review found no blockers. Its credential-safe recovery logging,
receive-pack coverage, generic request failure coverage, and documentation
accuracy findings were incorporated. Production verification remains an operator
step because it requires deployed credentials and runtime access.
