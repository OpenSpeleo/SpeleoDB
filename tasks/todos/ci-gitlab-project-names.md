# GitLab canonical project name collisions

- [x] Inspect the supplied CI job and its creation audit.
- [x] Verify the plan against fixture and budget contracts.
- [x] Remove custom provisioning and use the usual UUID-based manager flow.
- [x] Extend regression coverage without adding remote allocations.
- [x] Run relevant tests and checks in the existing application container.
- [x] Document results and audit cleanup.

## Evidence and plan

Job 104671352307 in run 35057744235 rejected canonical admin and write project
creation with HTTP 400: both `project_namespace.name` and `name` were already
taken. Paths were fresh UUIDs but names were fixed across runs. The audit
reports five successful creations, eight POSTs, 80 violations, and no unresolved
outcomes; the violations follow attempts to reuse terminally rejected slots.

Use `GitlabManager.create_or_clone_project()` for remote creation and initial
commits. Remove the pool's separate naming payload, Git initialization, and
custom commit authorship. Keep only allocation and lease lifecycle bookkeeping.
The user's correction explicitly requires reusing production behavior instead of
adding a naming convention. Initial empty commits need not have distinct SHAs;
validate the standard commit and each slot's baseline instead.

## Review

The pool no longer creates remotes or publishes initial commits itself. It calls
the production manager and records the returned baseline and branch, then
applies lease isolation settings. The existing real-service regression validates
UUID names/paths and the application's normal initial author, message, and empty
tree.

Focused container verification: 19 pool/manager tests passed. Audit
`7efd0d91a8084eecaf391221de823230` reports four creations, five POSTs (including
the intentional invalid namespace), zero violations or unresolved outcomes, and
all four repositories verified marked for deletion. Ruff, formatting, and
focused mypy pass.

Full verification: `docker exec -w /app speleodb_local_django make test-py`
passed **4,568 tests**, with **178 skips**, in 865.95 seconds using the normal
local SQLite configuration. Audit `3532906882cf4361bca08c06844d02ca` reports
nine creations and ten POSTs, zero violations, no unresolved outcomes, and all
nine created repositories verified marked for deletion. Reviewed both
`summary.json` and `events.jsonl`. No budget, guard, retry policy, or SDK
response was bypassed.

The full run used the local configured service; the remote GitHub Actions job
has not been rerun. Changes are not committed or pushed.
