# Compass Sidecar Browser Download URL

## Plan

- [x] Reproduce the failing live release response and identify the URL-shape
      change.
- [x] Resolve recognized GitHub release-asset API URLs to browser download URLs.
- [x] Validate direct and resolved MSI URLs against the Compass Sidecar
      repository.
- [x] Add deterministic tests for direct URLs, API resolution, and unsafe
      failures.
- [x] Document the release metadata and caching contract.
- [x] Run focused tests, Ruff, mypy, formatting, and relevant live verification.

## Review

The release fetcher now accepts legacy direct Sidecar MSI links and resolves the
asset API URLs emitted by `tauri-action` through GitHub's JSON metadata. Only
stable, repository-scoped HTTPS browser download URLs are cached or exposed to
the public template. Stale API URLs and unsafe cached values trigger a fresh
lookup, while all lookup and validation failures retain the existing cached
releases-page fallback.

Verification results:

- Compass Sidecar release tests: 28 passed, including the live GitHub contract.
- Full `frontend_public/tests/test_views.py`: 80 passed.
- Ruff lint and format checks: passed.
- Focused mypy: passed.
- Focused `git diff --check`: passed.

An independent review found no blocking correctness issues. Its URL
normalization hardening recommendation was incorporated by rejecting decoded dot
segments, backslashes, and ASCII control characters with regression tests.
