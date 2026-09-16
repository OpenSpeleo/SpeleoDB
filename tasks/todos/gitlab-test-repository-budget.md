# Django test GitLab repository budget

Approved plan: four fresh canonical repositories per run, reused by ordinary
integration tests, and at most five explicitly allocated lifecycle repositories.
Additional database-only projects are permitted. All verification runs in the
existing Docker containers; real GitLab integrations remain real.

- [x] Add a process-safe creation audit and pre-transport budget guard.
- [x] Add the four-project registry, isolated database fixtures and Git leases.
- [x] Migrate ordinary test setup and indirect factory consumers.
- [x] Consolidate creation/deletion coverage into five lifecycle allocations.
- [x] Make CI preflight read-only and retain write-check coverage.
- [x] Publish audit artifacts and coordinate CI with scheduled cleanup.
- [x] Document the contract in AGENTS.md, docs and lessons.
- [x] Run focused regressions, full `make test-py`, Ruff and mypy in Docker.
- [x] Record verified counts, cleanup and remaining limitations.

## Analysis

Collection before implementation: 4,664 tests. Static analysis found 168
ProjectFactory call sites in 37 files, plus child factories. Database creation
does not provision GitLab: `Project.git_repo` lazily invokes the manager after a
missing local checkout. A guarded upload probe confirmed this path and blocked
its one creation POST; no creation requests were forwarded during planning.

| Source of remote creation                                                      | Implementation                                                                                              |
| ------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------- |
| Parameterized upload, processor, history, checkout, proxy and command fixtures | Reuse canonical IDs and explicitly prepare a remote lease only when Git is exercised                        |
| Indirect project creation through six child factories                          | Default to `CanonicalProjectFactory`; preserve distinct explicit projects and database-free `build()`       |
| Archive and initial-commit tests                                               | Reuse READ_ONLY for history exports; combine genuine empty/disabled/initial-commit cases in `empty-archive` |
| Manager creation and cache recovery                                            | One `manager-new` lifecycle, including user cleanup                                                         |
| Existing empty remote initialization and group cleanup                         | One `manager-empty` lifecycle in an isolated subgroup                                                       |
| Proxy provisioning and actual Make cleanup entrypoint                          | One `proxy-new` lifecycle in an isolated subgroup                                                           |
| Authenticated command write check                                              | One `write-check` allocation; CI preflight uses the read-only mode                                          |

## Implementation and verification plan

1. Place accounting below both the manager and direct SDK calls, at Requests'
   real transport. Persist fixed allocation identities, attempts, real outcomes,
   initiating test/phase/stack, and cleanup evidence outside the Django
   database. Block an unallocated call before transmission and retain violations
   even if application code catches the exception. Share the ledger with
   subprocesses.
2. Keep only four UUIDs, clients, and Git baseline metadata for the session.
   Reconstruct database rows per transaction. Keep permission grants explicit,
   including team-only and no-access cases; expose the complete A/B matrix as a
   separate helper. Permit additional database-only identities for cardinality.
3. Give each test a fresh checkout directory and reset leased remote history,
   refs, and settings after use. Verify every baseline is distinct and unchanged
   across consecutive leases. Delete only owned repositories at session end and
   verify absence or GitLab's real delayed-deletion marker.
4. Consolidate compatible creation/deletion scenarios within five self-contained
   lifecycles. Preserve real authentication, SQL rollback, Git failure and SDK
   response assertions. Do not make tests depend on collection order.
5. Publish CI audit artifacts on failure as well as success and serialize the
   GitLab suite with scheduled cleanup. Document the fixed budget, fixture APIs,
   maintenance rules, and container-only commands in AGENTS.md and design docs.
6. Validate targeted regressions, rejected uploads with creation forbidden,
   reordered live consumers, PostgreSQL rollback/live-worker behavior, and a
   normal full `make test-py`. Inspect cumulative counts and per-repository
   cleanup, then run Ruff, formatting, and mypy inside the running container.

## Review

### Acceptance result

The final normal command,
`docker exec -w /app speleodb_local_django make test-py`, passed **4,522
tests**, with **178 configured skips**, in **510.95 seconds**. It collected
4,700 cases. All verification ran inside the existing application container
against the existing services; no replacement GitLab responses were introduced.

Run `d06a71ab84304171ae3e6995478d1bf3` created **nine repositories** with **ten
creation POSTs**, **zero violations**, and **zero unresolved outcomes**. Each
successful creation returned HTTP 201. The extra request deliberately targeted
namespace `-1`, returned HTTP 400, and created nothing. All nine created IDs
were read back with GitLab's delayed-deletion marker; this verifies scheduled
removal, not physical deletion from GitLab storage.

The complete machine-readable evidence is in
[summary.json](../../.artifacts/gitlab/d06a71ab84304171ae3e6995478d1bf3/summary.json)
and
[events.jsonl](../../.artifacts/gitlab/d06a71ab84304171ae3e6995478d1bf3/events.jsonl).
The event stream contains every initiating test ID, phase, application stack,
allocation identity, response status, and cleanup readback. CI uploads the same
artifact directory even on test failure.

| Allocation          | GitLab ID | First creating scenario                           | Cleanup readback        |
| ------------------- | --------- | ------------------------------------------------- | ----------------------- |
| `canonical-admin`   | 5115      | Compass upload bundle                             | Marked for deletion     |
| `canonical-read`    | 5116      | Complete archive history fixture                  | Marked for deletion     |
| `canonical-write`   | 5118      | Build eligible project GeoJSONs                   | Marked for deletion     |
| `canonical-view`    | 5123      | Four-role baseline contract                       | Marked for deletion     |
| `empty-archive`     | 5117      | Empty archive and initial-commit lifecycle        | Marked for deletion     |
| `write-check`       | 5119      | Authenticated command write check                 | Marked for deletion     |
| `manager-new`       | 5120      | New repository, cache recovery, user cleanup      | Marked for deletion     |
| `manager-empty`     | 5121      | Empty repository initialization, subgroup cleanup | Marked for deletion     |
| `proxy-new`         | 5122      | First-404 proxy provisioning, Make cleanup        | Marked for deletion     |
| `invalid-namespace` | None      | Invalid namespace initialization                  | HTTP 400; remote absent |

### Additional verification

| Check                                                | Result                       | Creations / POSTs |
| ---------------------------------------------------- | ---------------------------- | ----------------- |
| Archive, audit, pool and factory regressions         | 85 passed                    | 5 / 5             |
| Rejected uploads with `--gitlab-audit-deny-create`   | 10 passed, 2 expected skips  | 0 / 0             |
| Reordered pool, Git history and valid uploads        | 13 passed, 2 expected skips  | 4 / 4             |
| PostgreSQL rollback/error reporting and pool checks  | 32 passed                    | 4 / 4             |
| PostgreSQL live-worker suite                         | 5 passed                     | 0 / 0             |
| JavaScript suite                                     | 1,010 passed across 58 files | None              |
| Mypy, normal repository command                      | 725 source files passed      | None              |
| Ruff and formatting, all changed Python files        | Passed                       | None              |
| Ruff, repository with CI's existing `bin/` exclusion | Passed                       | None              |
| Changed workflow YAML parsing and `git diff --check` | Passed                       | None              |

All targeted audit reports had zero violations and unresolved outcomes, with
verified cleanup for every created ID. The reordered run was
`5145ff6fb4034a3a8efc4ac40509e2d3`; the final live-worker run was
`82a8acba40714cc0a67632baa970584f`.

One earlier combined PostgreSQL run passed 36 cases and timed out in the
optional duplicate-delivery worker test after constructing its export ZIP. The
isolated case then passed, followed by all five worker tests passing together.
No worker or production behavior was changed to hide that timeout. An
unrestricted `ruff check .` also reports 44 pre-existing errors in
`bin/squash_dependencies.py`, which the repository's pre-commit configuration
already excludes.

### Findings resolved during implementation

The first integrated run exposed GitLab's stale REST branch cache during pool
reset. Both the expected force-push SHA and extra-ref inventory now come from
`git ls-remote`; API readback verifies the restored state afterward. A
regression test creates and removes an additional branch, tag, and file and then
clones again to prove isolation. Inspecting the actual GitLab repository
confirmed the failure was a missed public branch, not a hidden retained ref.

The archive fixture now explicitly creates its history branch on the leased
remote. The invalid-namespace regression checks HTTP 400, a nonempty real error,
and local/remote absence without relying on version-specific GitLab wording.
Child factory `build()` stays database-free, canonical identities cannot be
overridden, and nested pytest joins the parent's ledger rather than receiving a
fresh budget.

The guard covers the application's Requests/python-gitlab transports and
inherited Python test settings. It is test infrastructure, not an
operating-system network sandbox. Parallel pytest workers are rejected because
remote leases are serial.
