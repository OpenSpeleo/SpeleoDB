# OGC review follow-up

## Remaining blocker

- **Severity: Low for OGC merge, blocking for repository-wide `ruff check`.**
  `ruff check` fails on pre-existing issues in `bin/squash_dependencies.py`
  (Bandit subprocess rules, print statements, broad exception handling, path
  API cleanup, and style issues). The OGC-edited Python files pass focused
  `ruff check`; this script is outside the OGC URL/geometry diff. Suggested
  fix: either bring `bin/squash_dependencies.py` under current ruff standards
  in a separate maintenance PR, or exclude the historical script explicitly if
  it is intentionally outside the application lint surface.
