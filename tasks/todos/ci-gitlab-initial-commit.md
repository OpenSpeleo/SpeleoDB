# CI GitLab initial commit

## Plan

- [x] Verify the failed hosted CI run and trace the first repository write.
- [x] Add a bounded retry for HTTP 404 when seeding a newly created test
      project. Preserve immediate failure for other statuses and transport
      errors.
- [x] Test recovery, exhaustion, and non-retryable failures with the real
      python-gitlab response handling, then run the live archive fixture.
- [x] Run applicable lint/type checks and document the result and limits.

## Scope

The CI fixture successfully creates a GitLab project, but its immediately
following initial commit receives `404 Project Not Found`. Keep any readiness
handling local to that first write on the newly created disposable project. Do
not change application retry policy, later commits, cleanup, or CI scheduling.

## Review

The initial GitLab commit now retries only an explicit HTTP 404, for at most
five attempts with 1/2/4/8-second backoff. Other errors propagate and a
persistent 404 preserves the original exception. The successful path adds no
requests or delay. The existing fixture cleanup still encloses the entire
operation.

Evidence from hosted CI:

- [Failed run](https://github.com/OpenSpeleo/SpeleoDB/actions/runs/34980353417):
  project creation succeeded, the first commit returned HTTP 404, and the run
  finished with 4,277 passed, 162 skipped, and this one fixture error.
- [Passing run of the same revision](https://github.com/OpenSpeleo/SpeleoDB/actions/runs/34980334120):
  4,278 passed and 162 skipped.

The logs establish an intermittent failure after creation; they do not establish
which GitLab subsystem caused the 404. The fixture now handles that specific
response with a finite budget.

Verification inside the existing Django Docker container:

- Real HTTP/SDK retry regressions: 10 passed, including recovery, exhaustion,
  unchanged request payloads, other HTTP statuses, and a lost response.
- Full live archive test module: 35 passed using local GitLab, PostgreSQL, and
  the isolated test storage bucket.
- Ruff lint and formatting checks passed for both changed Python files.
- Full mypy passed for 692 source files.
- Independent review found no blocking issues.

The full Python suite and hosted CI were not rerun with this change.
