# Restore normal local validation

- [x] Reproduce mypy's failure with a traceback; identify corrupted SQLite
      cache.
- [x] Keep mypy cache outside the shared host/container checkout and verify the
      normal mypy command directly in both environments. Never run prek or
      pre-commit: the user explicitly prohibited them.
- [x] Replace PostgreSQL-only import failures with real constraints supported by
      SQLite and PostgreSQL, preserving partial-write and storage rollback
      checks.
- [x] Keep static discovery/redirect endpoints outside request transactions
      while retaining production transaction behavior for application requests.
- [x] Run every reported regression on SQLite and PostgreSQL, lint/type checks,
      and record the verified result and remaining limits.

## Corrections

The prior validation used PostgreSQL and a temporary mypy cache. That missed the
user's normal SQLite path and left the standard cache broken. Five new rollback
cases assumed PostgreSQL's VARCHAR enforcement; 49 static endpoint cases were
affected by enabling ATOMIC_REQUESTS in test settings. Fix the underlying
contracts instead of skipping those tests or accepting arbitrary HTTP 500s.

## Review

All 54 reported failures passed after correction. SQLite verification ran eight
import cases and 52 static endpoint cases; PostgreSQL passed the same 60 cases
in one run. Rollback checks still observe the first successful insert and verify
that the database and storage contain no partial import. Static endpoint tests
still forbid database access; request transactions remain enabled elsewhere.

Changed Python files pass Ruff and formatting. Normal direct mypy commands pass
with environment-owned caches; cold/warm details are recorded in
[the mypy review](mypy-cache.md). Verification used direct commands; no prek or
pre-commit hooks were executed. This validation covers all reported failures and
adjacent controls; it does not claim a new complete full-suite run.
