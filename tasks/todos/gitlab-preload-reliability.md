# GitLab preload reliability

## Plan

- [x] Trace the failed create/clone path and confirm the command test depends on
      live GitLab.
- [x] Distinguish confirmed existing repositories from failed GitLab creation;
      use bounded transient API retries.
- [x] Preserve useful clone failure details while redacting credentials in retry
      logs and raised exceptions.
- [x] Use isolated local Git remotes for preload command tests and retain
      dedicated live GitLab coverage.
- [x] Add regressions for creation failures, confirmed conflicts, retry
      recovery, and credential redaction.
- [x] Document ownership, failure behavior, and verification; review the diff
      and run relevant checks.
- [x] Commit the completed fix.

## Design

GitLab project creation must not turn every API failure into a clone. Confirm
the remote project exists before accepting a duplicate/conflict response, and
preserve other API failures. Use the client library's bounded transient retry
support, including rate-limit headers. Keep git history reconstruction tests
independent of GitLab availability by cloning and pulling from real temporary
local bare repositories.

## Review

The final diff received independent review with no remaining findings. The
preload tests use real local bare remotes and a temporary working-copy root;
their initial commits have distinct content to avoid cross-project SHA primary
key collisions when created in the same second. GitLab client tests exercise
actual HTTP exception mapping and retry behavior with simulated responses.

Validation used an isolated temporary PostgreSQL container and dummy external
credentials. The combined Git engine, preload command, and ProjectCommit model
suites passed: 38 tests and 17 subtests. Seven existing network/GitLab
integration cases were skipped with the light/offline options. All five preload
cases ran, including the previously flaky no-user-commits case.

Repository hooks passed their code, type, security, JavaScript lint, and Vite
build checks. The Markdown formatter normalized this task file; its final
formatting check is included before committing.
