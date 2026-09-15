# Bound operational retries and waits

## Confirmed failure

CI run `34997387739`, job `104476947867`, dumped its stack at 2026-09-15
16:52:14 UTC. The first Compass upload test was blocked in
`gitlab/utils.py:138`, sleeping in `handle_retry_on_status`, during the GitLab
project-create POST. The request timeout and retry count did not bound the
server-directed sleep. Exploration-lead tests and their teardown completed.

## Plan

- [x] Obtain the actual CI stack and distinguish the blocked call from the last
      displayed completed test.
- [x] Audit operational retry/poll loops and SDK retry configuration.
- [x] Enforce finite GitLab REST attempts, bounded requests, and capped
      exponential backoff in normal application and standalone provisioning
      paths.
- [x] Bound individual Git subprocess attempts and harden shared retry helpers.
- [x] Fix other operational retry loops that can repeat forever or use
      unbounded/non-exponential failure delays.
- [x] Add regressions for exhaustion, large retry headers, and hung operations.
- [x] Review changes and document the retry contracts and remaining limits.

The user explicitly requested finite retries and exponential sleep. Tests and
pre-commit execution stay paused. The later typing/lint failure reports were
verified with direct mypy/Ruff commands inside Docker. Git uses the host shell.
Preserve concurrent export-storage changes and running services.

## Review

Implemented shared GitLab attempt/backoff policy, Git process supervision,
durable export publication/notification/cleanup budgets, browser refresh
deadlines, startup/lock budgets, cache contention backoff, and FFmpeg deadlines.
Source reviews found and corrected shutdown supervision, inherited Git stdout
diagnostics, server resource-lock classification, and stale ownership paths. The
broker/scheduler source review also closed direct streamed Git calls that
bypassed the default deadline and replaced native linear broker connection
delays through supported Celery extension points.

Corrected the user's typing/lint reports, including optional Git process
handling, command-sequence typing, FFmpeg's untyped constructor, nullable
attempt IDs, scheduler stub gaps, and test/property mocks. Direct mypy passed
all 705 source files inside Docker. Direct Ruff passed `speleodb`, `config`, and
`compose`, including all newly added files. A broader Ruff scan also found
unrelated diagnostics in the existing `bin/squash_dependencies.py`; that file
was not changed. No tests or full pre-commit hook run was performed by the
assistant.

A bounded retry failure exposes a persistent remote error; it does not repair
the remote service or guarantee integration tests pass when GitLab is
unavailable.
