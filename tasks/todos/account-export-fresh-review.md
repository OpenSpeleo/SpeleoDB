# Fresh account export review

Review starting commit `41c0f622` against the pre-feature base `547b91c9`. The
user requested a fresh adversarial review, corrective work, full tests,
`prek run -a`, and a commit. Push and deployment remain paused.

## Plan

- [x] Independently review lifecycle/API and archive/storage behavior with
      principal-engineer reviewers; inspect frontend and infrastructure locally.
- [x] Record only confirmed actionable findings with severity, file/lines,
      reproduction scenario, and the smallest corrective plan.
- [x] Review and refine each corrective plan, implement fixes, and add
      meaningful regression coverage.
- [x] Run the complete Python and JavaScript suites, relevant real integrations,
      and `prek run -a` inside Docker.
- [x] Review the final diff and commit all changes.

## Constraints

Use existing Docker containers for checks. Do not restart or recreate Django,
the webserver, or the full Compose graph. Preserve one shared Redis server, one
PostgreSQL server, one worker consuming both queues, and Beat without Railway
cron. Keep ordinary ZIP files and the bucket's existing configuration. Avoid
unrequested product or infrastructure changes.

## Findings and corrective plans

### P1: known Git history is silently replaced by an empty-project marker

`speleodb/background_jobs/archive_sources.py:370`: a cloned remote with no refs
returns an empty success even when the snapshot has recorded commits. Recreating
or clearing a remote can therefore produce a complete-looking backup that has
lost known project history.

Reviewed correction: reject that state with a safe missing-history omission;
preserve the marker for genuinely zero-history projects. Verify both cases with
real Git and a mixed-source archive. Do not broaden the fix into per-commit
database/repository reconciliation.

### P2: polling removes keyboard focus from export controls

`frontend_common/controllers/user-exports.js:138`: rendering replaces every
history card. While any job is active, the five-second refresh destroys a
focused download/retry control and moves keyboard focus back to the document.

Reviewed correction: preserve focus on the same surviving card/control during a
refresh, without scrolling or stealing focus from outside the history. Explicit
email-link focus keeps precedence. Verify this with real DOM focus behavior.

### P2: history cleanup races with an accepted retry

`speleodb/background_jobs/tasks.py:457`: Django's cascade collector first
selects an old failed job, then collects its attempts. A retry inserted between
those steps is deleted with the old history, despite being accepted and queued.

Reviewed correction: lock and recheck each eligible job in a short transaction
before collecting/deleting it. If deletion wins the race, retry/resend should
report an unavailable export instead of an uncaught missing-row exception.
Verify both outcomes with real database operations and PostgreSQL concurrency.

## Verification and results

The three focus regressions failed before the fix; all 41 export-controller
tests and all 1,018 JavaScript tests passed afterward. Archive/Git supervision
passed 39 tests, including three new real Git/GitLab cases. Lifecycle/retention
passed 20 tests on SQLite, with the PostgreSQL-only case skipped, then all five
retention tests passed on isolated PostgreSQL. The concurrency case verified the
actual blocking lock before cleanup committed. Focused lint/type checks passed.

### Full verification

All checks ran inside the existing Docker containers:

- Full Python suite: **4,276 passed, 164 skipped, 108 subtests passed** in
  258.40 seconds. The first run had one 30-second Git-status timeout during
  overlapping verification jobs. The exact saved extraction passed clean status
  and full Git integrity checks in milliseconds, and the isolated test passed.
  Docker showed memory and I/O pressure. The complete sequential rerun passed
  without code or timeout changes.
- Full JavaScript suite: **1,018 passed across 59 files**.
- Real PostgreSQL retention coverage: **5 passed**, including concurrent lock
  verification. The SQLite full suite skips that PostgreSQL-only case.
- Isolated live-worker integration coverage: **5 passed**, including default
  queue consumption, export/download/notification/expiry, duplicate delivery,
  broker refusal/outbox recovery, and worker death/recovery. The temporary test
  broker was removed afterward.
- `prek run -a`: **passed**, including Ruff, mypy, JavaScript lint, security
  checks, configuration checks, and the production Vite build. Its first run
  only reformatted this review document; the repeat passed.
- Django system checks and migration consistency: **passed**.
- The running Django export page returned HTTP 200 and served the production
  manifest's exact assets with one export list. This was an HTTP/asset check;
  keyboard behavior was verified by DOM tests.

The previously recorded 4 GiB storage test was not repeated because this review
does not change storage or ZIP streaming. Its prior evidence remains in the
feature documentation.

### Local runtime and final review

The worker was idle before one worker-only restart. Afterward, one uniquely
named worker consumed both `exports` and `background_control`. Django, the
webserver, Beat, and the Compose graph were not restarted or recreated. No
production deployment or push was performed.

The final diff contains the three focused corrections, their regression tests,
and supporting documentation. The independent reviewers reported no further
actionable findings. All three findings are resolved and verified; the changes
are included in the local review commit.
