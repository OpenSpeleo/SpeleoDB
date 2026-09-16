# Pytest concurrency across branches

## Manual cleanup follow-up

- [x] Remove the cron trigger and rename the workflow/job to reflect manual use.
- [x] Update cleanup guidance and record the user's manual-only preference.
- [x] Validate the workflow triggers in the existing container.

Follow-up review: the workflow now runs only through `workflow_dispatch` and
retains its 24-hour age filter. Container YAML assertions and `git diff --check`
passed. Python behavior is unchanged; the prior 11-test result applies.

- [x] Identify the fixed pytest concurrency group and shared cleanup dependency.
- [x] Present the cleanup approach before implementation; proceed with the
      stated stale-only default while the optional preference remains
      unanswered.
- [x] Scope pytest concurrency to the branch while preserving safe cleanup.
- [x] Validate the affected workflow/cleanup behavior in the existing container.
- [x] Update GitLab testing documentation and record the review.

## Plan

Use a branch-specific pytest job group, retaining `cancel-in-progress: false`.
Each invocation already owns fresh repository UUIDs, but nightly group-wide
cleanup currently relies on the same global lock. Resolve that dependency before
enabling cross-branch concurrency: either restrict scheduled cleanup to stale
repositories beyond a bounded CI runtime, or remove the schedule and retain
manual cleanup during idle periods. Keep pytest workers serial within each run.

## Review

Implemented the branch-specific group and retained cancellation settings. Manual
cleanup preserves repositories younger than 24 hours, while pytest jobs are
bounded to 60 minutes. Unknown or invalid creation dates are preserved.
Unrestricted manual cleanup remains an idle-only operation.

Container verification: 11 focused tests passed, including the real GitLab
cleanup lifecycle, plus Ruff, formatting, mypy, workflow YAML/policy checks, and
`git diff --check`. Audit `36e95d4cd9374eebb0c5265b50047fa1` recorded one
creation/POST, no violations or unresolved outcomes, and verified cleanup.
Independent review found no blocking issue. Actual Actions scheduling remains
unverified locally; default-branch cleanup must be updated before parallel CI on
other branches can safely depend on the new policy.
