# CI Compose test environment

## Plan

- [x] Compare the failing fixtures with CI configuration and review applicable
      repository rules and lessons.
- [x] Reproduce both failures with a clean CI-style environment and identify the
      reloader subprocess's underlying error.
- [x] Supply the explicit PostgreSQL administrator configuration required by the
      integration tests and make the reloader probe's settings self-contained.
- [x] Run the affected tests against real PostgreSQL, then related Compose tests
      and applicable lint/type checks.
- [x] Document the environment contract, verification results, and review.

## Design and scope

Keep the provisioner's explicit administrator credentials and its isolated
database/role tests. CI should supply the same connection contract as Compose.
The reloader test must exercise local Django settings without relying on private
developer environment files. Existing behavioral tests provide regression
coverage; reproduce the CI environment to ensure it cannot hide missing inputs.

## Review

CI now exports the five PostgreSQL administrator variables used by the Kanchi
integration tests. The reloader probe supplies a test-only Django secret,
disables private dotenv loading, and reports captured stderr on failure. No
provisioning or application runtime behavior changed.

Verification ran inside the existing Django Docker container, using a disposable
tracked checkout without private dotenv files and an environment built from the
CI pytest job. GitLab/Mapbox secrets were replaced with dummy values. For
database execution, only the PostgreSQL connection was translated to the
existing local service; the original CI administrator values were separately
checked against `DATABASE_URL`, the service password, and the published port.

- Before the fix: reproduced 1 failure and 11 setup errors.
- After the fix: all 12 previously failing cases passed against real PostgreSQL.
- Related Compose and local debug-toolbar settings tests: 51 passed, 1 skipped
  (the ownership migration case requires root).
- Ruff lint and formatting checks passed for the changed Python test.
- Full mypy check passed for 691 source files.
- Workflow YAML validation and `git diff --check` passed.
- Independent review found no defects in the workflow, test, or documentation.

The full Python suite and hosted GitHub Actions job were not rerun.
