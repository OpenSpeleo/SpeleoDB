# Required user names and resilient Git authorship

Approved plan: reject future missing/blank names; repair existing unnamed users
with `NO NAME`; retain a defensive Git-only fallback. Do not rewrite history.

- [x] Trace admin, manager, signup, serializer, and Git failure paths.
- [x] Add shared typed name validation, model/manager safeguards, and migration.
- [x] Require names in admin/CLI and assign signup fields before initial save.
- [x] Validate profile names after sanitization.
- [x] Guard Git author names at the supervised commit boundary.
- [x] Add model/database/migration, account interface, and real Git/upload
      tests.
- [x] Update existing nameless fixtures and the pytest admin fixture.
- [x] Document identity policy, migration/rollout, and regression lessons.
- [x] Run container-only focused/full tests, lint/type checks, migration checks;
      record GitLab audit counts and cleanup.

## Adversarial review follow-up

- [x] Principal-engineer review of complete diff and new files; correct
      actionable findings using a reviewed corrective plan.
- [x] Run final full tests in the existing container.
- [x] Run final `prek run -a` in the existing container.
- [x] Record final evidence for the reviewed commit.

Adversarial review found no actionable findings across the tracked diff and all
new files. It checked correctness, security/data handling, races, error
handling, compatibility, test coverage, and complexity. The reviewed corrective
plan has no application code changes. Hook checks required only an explicit raw
regex literal in a test assertion and automatic Python/Markdown formatting.

Final container `make test`: **4,796 Python tests passed, 178 skipped**, in
514.42 seconds; **1,040 JavaScript tests passed** across 64 files. Audit
`e700865baf7244e0b70904d56635980b` again reports **9 creations / 10 POSTs, zero
violations and unresolved outcomes**. Summary and event records confirm all nine
repositories were marked for deletion. Final `prek run -a` passed all hooks; no
test behavior changed.

## Review

Implementation and verification complete in the existing application container
started by the user. No development/production database migration has been
explicitly applied by this task; follow the documented rollout procedure.

- PostgreSQL users/profile suite: 348 passed, including every Unicode whitespace
  character, database bypass protection, and migration rollback/reapply.
- SQLite CLI and real Ariane upload regression: 24 passed. Audit
  `82f1636ca8bf4374b0f455a61ece0270`: 1 creation / 1 POST, zero violations or
  unresolved outcomes; canonical-write cleanup verified marked-for-deletion.
- SQLite users/profile/Git suite initially had 372 passes plus 20 passing
  subtests and five CLI assertion failures. The command correctly rejected
  whitespace using Django's built-in blank error; corrected assertions passed in
  the CLI rerun. Earlier route/error-envelope test assumptions and Git 2.39's
  period-only identity rejection were corrected before these runs.
- Application Ruff, changed-code formatting, full mypy (731 source files),
  Django system checks, and migration drift check passed. Broad `ruff check .`
  additionally reports 44 existing issues in untouched
  `bin/squash_dependencies.py`; no unrelated cleanup was made.
- Read-only GitLab preflight passed. Full container `make test-py`: **4,796
  passed, 178 skipped**, in 500.38 seconds. This includes the complete SQLite
  regression set after the test-assertion corrections.
- Full audit `5dcfcdd518384da69ef7275cd06fc42e`: **9 creations / 10 creation
  POSTs, zero violations, zero unresolved outcomes**. Inspected summary and
  event records: all nine created allocations have verified deletion marks; the
  tenth POST was the intentional invalid-namespace rejection. GitLab may retain
  marked repositories until its delayed-deletion period ends.
- Final `git diff --check` passed. No production deployment or history rewrite
  performed. Independent account-flow and Git-boundary reviews found no
  remaining correctness issues within this task's scope.
