# GitLab hardening by logical commit

## Plan and commit boundaries

1. **Cleanup correctness**
   - [x] Treat only confirmed GitLab 404 responses as absent repositories.
   - [x] Preserve Django projects on authorization, throttling, server, and
         transport failures.
   - [x] Add command regressions and documentation, verify, and commit.
2. **Shared GitLab API policy**
   - [x] Centralize finite timeouts and bounded transient retries for API calls.
   - [x] Apply the policy to authentication, project reads, history, branches,
         and maintenance clients.
   - [x] Handle operation-specific SDK exceptions and distinguish missing data
         from outages.
   - [x] Add regressions, update documentation, verify, and commit.
3. **Git subprocess diagnostics and recovery**
   - [x] Share credential-safe diagnostics across clone, pull, and push retries.
   - [x] Require confirmed branch absence before branch creation; preserve
         upstream failures.
   - [x] Review project-level re-clone recovery so network outages do not imply
         local corruption.
   - [x] Add real local-repository regressions, update documentation, verify,
         and commit.
4. **Proxy discovery retries**
   - [x] Add bounded retries for transient discovery GET failures before
         streaming starts.
   - [x] Honor reasonable rate-limit delays and close failed responses before
         retrying.
   - [x] Keep push POSTs and partially delivered streams out of automatic
         replay.
   - [x] Add protocol regressions, update documentation, verify, and commit.
5. **Download origin repair follow-up**
   - [x] Share origin repair between project checkout and download operations.
   - [x] Cover stale-origin latest and historical downloads, plus offline cache
         hits.
   - [x] Verify and commit independently after the final cross-group review.
6. **Final verification**
   - [ ] Run the complete Python test suite with isolated GitLab, storage, and
         database resources.
   - [x] Run the complete JavaScript test suite and all repository hooks.
   - [ ] Review the commit series, record results, and remove task-owned
         temporary resources.

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
- Shared REST: 29 focused tests passed against isolated PostgreSQL, including
  real SDK retry/error mapping and both cached-client/recreated-project edges.
  Ruff and mypy passed; review findings were fixed and regression-tested.
- Git operations: 55 checkout, retry, manager, preload, and project-history
  tests passed, including live GitLab/storage integrations. A subsequent 25-test
  diagnostics run covered credential-bearing origin creation/repair failures.
  Ruff and mypy passed. Downloads also use safe branch/fetch selection; review
  findings about missing-object exceptions and origin configuration were fixed.
- Proxy: all 45 focused tests passed against isolated PostgreSQL; Ruff and mypy
  passed. Independent review found no required changes. Full-suite preflight
  collected 4,303 tests without duplicate IDs or light/offline flags.
- JavaScript: all 58 files / 977 tests passed. All `prek --all-files` hooks
  passed after the plan's automatic Markdown formatting, including full mypy,
  security scans, JavaScript lint, URL checks, and the Vite production build.
- Initial full macOS run: 4,146 passed, 156 skipped, one environment failure.
  The existing container-ownership test requires Linux `getent`/GNU `stat`. The
  final complete suite will run on Linux, also including the reviewed
  download-origin follow-up.
- Download follow-up: all 21 local checkout/model tests passed, including
  stale-origin latest/historical downloads and network-free cached downloads.
  Full static/type/security/build checks passed. The live recheck encountered
  GitLab HTTP 502 during authentication; service health is being verified before
  the Linux full-suite run.
- The local 502s were traced to Docker VM memory exhaustion killing GitLab's
  Puma/Sidekiq workers during a concurrent container build. GitLab recovered;
  authenticated requests succeeded again. This does not establish the cause of
  the original CI incident.
