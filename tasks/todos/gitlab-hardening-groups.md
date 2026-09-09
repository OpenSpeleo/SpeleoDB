# GitLab hardening by logical commit

## Plan and commit boundaries

1. **Cleanup correctness**
   - [x] Treat only confirmed GitLab 404 responses as absent repositories.
   - [x] Preserve Django projects on authorization, throttling, server, and transport failures.
   - [x] Add command regressions and documentation, verify, and commit.
2. **Shared GitLab API policy**
   - [ ] Centralize finite timeouts and bounded transient retries for API calls.
   - [ ] Apply the policy to authentication, project reads, history, branches, and maintenance clients.
   - [ ] Handle operation-specific SDK exceptions and distinguish missing data from outages.
   - [ ] Add regressions, update documentation, verify, and commit.
3. **Git subprocess diagnostics and recovery**
   - [ ] Share credential-safe diagnostics across clone, pull, and push retries.
   - [ ] Require confirmed branch absence before branch creation; preserve upstream failures.
   - [ ] Review project-level re-clone recovery so network outages do not imply local corruption.
   - [ ] Add real local-repository regressions, update documentation, verify, and commit.
4. **Proxy discovery retries**
   - [ ] Add bounded retries for transient discovery GET failures before streaming starts.
   - [ ] Honor reasonable rate-limit delays and close failed responses before retrying.
   - [ ] Keep push POSTs and partially delivered streams out of automatic replay.
   - [ ] Add protocol regressions, update documentation, verify, and commit.
5. **Final verification**
   - [ ] Run the complete Python test suite with isolated GitLab, storage, and database resources.
   - [ ] Run the complete JavaScript test suite and all repository hooks.
   - [ ] Review the commit series, record results, and remove task-owned temporary resources.

## Design decisions

Retries address transient availability failures; they do not establish that a
repository or branch is missing. Recovery decisions must use explicit evidence
of absence. A shared API client policy and Git-operation error wrapper should
keep retry limits, timeouts, and token redaction consistent without duplicated
per-caller logic. Destructive cleanup and non-idempotent protocol operations
retain operation-specific behavior.

Implement the groups sequentially. Each group includes its tests and relevant
documentation and is committed independently after focused validation. Reserve
the full integration run for the completed series. Do not push the commits.

## Review and verification

- Cleanup: five database-backed regression tests passed; targeted Ruff and mypy
  passed. Independent review found no required changes. Full-suite and hook
  verification will run after the complete series.
