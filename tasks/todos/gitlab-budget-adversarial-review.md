# Adversarial review of the Django GitLab repository budget

Continue the approved four-project reuse and nine-creation contract. Keep
workflow-level `cancel-in-progress: false`, as explicitly directed by the user.
All verification runs inside the already-running `speleodb_local_django`
container.

- [x] Complete adversarial review and review the corrective plan.
- [x] Fix actionable accounting, cleanup, and isolation findings with
      regressions.
- [x] Run focused regressions and inspect the GitLab audit.
- [x] Run the full test suite and `prek run -a` in the existing container.
- [x] Document final evidence, review the complete diff, and commit the changes.

## Review scope

Correctness and behavioral regressions, security and data handling, races and
failure handling, compatibility, test coverage, and unnecessary complexity.

## Corrective plan

1. **P2 — Lost creation responses can leak lifecycle repositories.**
   `test_archive.py` starts cleanup after creating `empty-archive`, and
   `test_check_gitlab.py` has no recovery finalizer for `write-check`. If GitLab
   creates the remote and the response is lost, no model is assigned for
   cleanup. Add an exact namespace/path cleanup context before creation,
   resolving and verifying only that allocated identity in its finalizer.
2. **P2 — Failed reset can leak dirty state into following tests.**
   `GitlabPool.release()` stops on its first error and clears every lease.
   Restore all borrowed roles, retain failed-reset state, and require a
   successful reset before that role can be borrowed again. Healthy repeated
   `prepare()` calls within one test must preserve the active scenario.
3. Add focused regressions using existing allocations and pure pool-state tests;
   do not add remote allocations or replace real GitLab responses. Update design
   documentation and lessons with the recovery contracts.
4. Run focused tests, the full suite, and all pre-commit hooks inside the
   existing container; inspect audit counts and verified cleanup; record results
   and commit.

The parent reviewed and approved this narrowed plan. The review agent
implemented and re-reviewed both fixes, with no additional actionable findings.
No group-wide cleanup sweep or replacement repository was introduced. The user's
final cancellation instruction is authoritative: retain
`cancel-in-progress: false`.

## Verification

The nine focused checks passed in the existing container in 15.21 seconds. Audit
`e6c24911caee43c1a40873806a791817` recorded two repositories, two POSTs, zero
violations, zero unresolved outcomes, and verified deletion marks for both
created IDs. This includes cleanup after a local exception using only the known
remote path, a real missing-remote readback, and all failed-reset state
transitions.

The full Python run passed **4,526 tests**, with **178 configured skips**, in
645.67 seconds. Audit `9604d309053145aaa16dab5b0fc277d8` recorded **nine
repositories**, **ten creation POSTs**, **zero violations**, and **zero
unresolved outcomes**. All nine IDs have verified deletion marks. The extra POST
was the intentional invalid-namespace HTTP 400.

The subsequent JavaScript run encountered seven 5-second timeouts across six
unchanged test files while the shared container was under concurrent load. No
assertions or timeout thresholds were changed. The complete suite passed **1,010
tests across 58 files** in 35.52 seconds with one file worker.

The first hook run found two lint errors in the cleanup regression: the sentinel
exception lacked an `Error` suffix and its `pytest.raises()` enclosed multiple
operations. Renaming the exception and extracting one lifecycle call resolved
both without suppressions. The affected real lifecycle passed again in 11.34
seconds: audit `b609e829a16c429a918e6123222ca750` recorded one creation, one
POST, zero violations, and verified cleanup. The review agent rechecked the
final structure and found no actionable issues.

All applicable `prek run -a` hooks passed, including Ruff, formatting, mypy,
dependency/security checks, URL consistency, JavaScript lint, and the Vite
build. Hooks run against an isolated checkout inside the same running
application container to preserve concurrent edits.

Separate upload-reporting work was committed independently as `5769d748`. Its
committed changes were included in the final hook verification checkout; its
remaining task-report edit stays outside this commit.
