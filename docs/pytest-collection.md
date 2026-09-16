# Pytest collection

## Discovery scope

`make test-py` invokes `pytest`. The `testpaths` setting in `pyproject.toml`
limits default discovery from the repository root to the six source roots:
`compose`, `frontend_errors`, `frontend_private`, `frontend_public`, `speleodb`,
and `well_known`. Keep these roots broad enough to include both test directories
and standalone `tests.py` modules, such as `speleodb/git_proxy/tests.py`. Add a
root here when introducing tests in a new top-level package.

Leave `norecursedirs` unset so pytest maintains its default exclusions for
hidden directories, `node_modules`, and build output. Assigning this option
replaces the defaults; it does not extend them. Discovery should depend on
source code, not the volume of local repositories, media, or dependencies.

Explicit command-line paths override `testpaths`. Run plain `pytest` from the
repository root for the default scope; a command targeting another directory
intentionally chooses a different scope. File patterns remain `tests.py` and
`test_*.py`. Permission matrices and parameterized cases remain intact.

## Measured result (2026-09-15)

Collection-only runs inside the existing Django Docker container measured:

| Measurement                          |  Before |  After |
| ------------------------------------ | ------: | -----: |
| Startup through pytest configuration |  2.70 s | 1.74 s |
| Collection                           | 36.80 s | 1.83 s |
| Complete profiled invocation         | 39.87 s | 3.73 s |
| Directory collectors                 |  59,776 |    149 |
| Collected tests                      |   4,619 |  4,619 |

The old configuration started at `/app` without `testpaths` and replaced
`norecursedirs` with `.uv/*`. It visited 58,800 directories inside `.workdir`,
costing 31.64 seconds. It also visited `node_modules` and `.git`. The revised
configuration visits none of those trees.

A temporary pytest plugin timed `pytest_make_collect_report`, grouped directory
collectors by their top-level root, and recorded session node IDs. The before
and after lists match in order and identity, with only the five existing
`test_random_hashes_with_hashlib` parameter labels normalized because their
inputs come from `os.urandom` during import. Their multiplicity remains five. An
intermediate CLI-override run also collected the same tests in 1.96 seconds.

Measurements were sequential after the competing test run stopped. These are
local samples, not cold-cache guarantees; timings vary with Docker memory
pressure and filesystem caching. No test bodies ran during this verification.

## Diagnosing future slowdowns

Run collection independently of test execution inside the existing container:

```sh
docker compose -f local.yml exec -T django pytest --collect-only -q
```

For a function-level profile, run these commands inside that container:

```sh
timeout --signal=INT --kill-after=10s 180s python -m cProfile \
  -o /tmp/pytest-collection.pstats -m pytest --collect-only -q
python -c 'import pstats; pstats.Stats("/tmp/pytest-collection.pstats").strip_dirs().sort_stats("cumulative").print_stats(30)'
```

Profiling adds overhead. Stop competing test runs first and compare identical
node lists when changing discovery. Do not leave profiling enabled in normal
test runs. Pytest's `--durations` reports test setup/call/teardown timing; use
collection-only profiling to investigate the wait before collection completes.

Once `collected ... items` is printed, fixture and test execution are separate
costs. In particular, the existing `--create-db` option recreates the test
database when database fixtures are requested; collection-only runs do not
request those fixtures. This change does not alter database setup behavior.
