# Protected-branch push failures after normal provisioning

- [x] Inspect the reported failing run without overlapping its pytest process.
- [x] Identify why GitLab rejects pushes after branch protection deletion.
- [x] Fix the owning behavior using existing production paths.
- [x] Verify against the real service and preserve the creation budget.
- [x] Record results and cleanup evidence.

## Evidence

The reported run uses UUID repository 81232618-a48f-402b-9bd4-9cb81e820885.
GitLab accepted its initial push, deleted master protection with HTTP 204, then
rejected later pushes by the same group-owner token. A read-only API query
returned no protected branches. Do not infer a permissions fix from the error
message alone; inspect GitLab's actual authorization path and state.

## Review

Local GitLab 18.7 reported `protected=true`, no protection rules,
`can_push=true`, and `can_push_branch=false`. Refreshing the exact project's
`ProtectedBranches::CacheService` changed the result to `protected=false` and
`can_push_branch=true`. No credentials or stored protection rules were changed.

The local bootstrap now sets unprotected default branches on its dedicated test
group using GitLab's normal group-settings API. This removes the initial
protect/unprotect transition for disposable repositories. Applied the same
setting to the current local test group. Application provisioning remains the
normal manager path; no extra retries or remote allocations were added.

After the user stopped their existing pytest run, container verification passed
**52 tests with four skips** across the pool, upload, GeoJSON upload, and local
bootstrap modules. This includes all three reported failures, fresh repository
creation using the saved group defaults, real pushes, lease history restoration,
and repeated bootstrap through the real API.

Audit `5268dc18399d41879dd982897cd66e3a`: four creations, four POSTs, zero
violations, no unresolved outcomes, and verified deletion marks for all four
repositories. Reviewed the summary and all 20 audit events. No test ran in
parallel with the user's run and no extra remote allocation was introduced.

Ruff and formatting checks pass for both bootstrap Python files. Mypy passes
when checking both bootstrap files together with both previously changed pool
files. The initial bootstrap-only mypy invocation reported unresolved imports in
unchanged Django modules; no suppressions or unrelated source changes were
added. Diff checks pass. The full Python suite was not rerun for this follow-up.
