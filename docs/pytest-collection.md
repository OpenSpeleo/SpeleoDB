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

`make test` runs `test-py`, `test-frontend`, and `test-browser`. The browser
wrapper lives outside default `testpaths` and is invoked explicitly by
`test-browser`; `make test-py` alone does not run it.

## Diagnosing future slowdowns

Run collection independently of test execution inside the existing container:

```sh
docker exec -w /app speleodb-monorepo-django pytest --collect-only -q
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
request those fixtures. Collection configuration does not alter database setup
behavior.
