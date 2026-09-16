# Mypy cache ownership

## Intent

The normal mypy command must work both on the host and inside the development
container. Its cache is disposable tooling state owned by the environment
running mypy. It must not live in the checkout shared between macOS and Docker.

`pyproject.toml` configures the global setting:

```toml
[tool.mypy]
cache_dir = "~/.cache/speleodb/mypy"
```

Mypy expands the home directory for the invoking user. The verified host path is
`/Users/jonathan/.cache/speleodb/mypy`; Docker's `dev-user` uses
`/home/dev-user/.cache/speleodb/mypy`. The application source remains shared at
the host checkout and `/app`, but cache writes stay on separate filesystems. An
explicit `MYPY_CACHE_DIR` environment variable overrides this setting and must
not point back into the shared checkout. See
[mypy cache configuration](https://mypy.readthedocs.io/en/stable/config_file.html#confval-cache_dir).

## Failure evidence and cause

In the September 2026 investigation, the direct host command
`.venv/bin/mypy --show-traceback --config-file pyproject.toml .` raised
`sqlite3.DatabaseError: database disk image is malformed` in
`mypy/metastore.py`. Both host and Docker used mypy 2.3.1 and the same checkout
`.mypy_cache`; neither configured a cache-directory override.

The installed mypy source enables SQLite caching by default and initializes its
cache shards with SQLite write-ahead logging (WAL). WAL relies on shared-memory
coordination between processes on the same host. A macOS process and a Linux VM
process accessing the same bind-mounted cache run under different kernels.
Keeping their live cache databases separate removes this unsafe sharing. See
[SQLite WAL constraints](https://www.sqlite.org/wal.html).

The old directory was preserved at
`/tmp/speleodb-mypy-cache-gu6ey5ly/.mypy_cache`, rather than discarded. A later
read-only `PRAGMA quick_check` on its moved shards returned `ok`; this did not
independently reproduce persistent on-disk corruption. The evidence establishes
the original mypy database error and the shared cache configuration, not the
precise sequence of writes responsible for that error.

## Verification

Run the normal commands twice in each environment, sequentially. The first
execution starts with no cache at the newly configured path; the second reads
the cache produced by the first. Do not use `--cache-dir`, disable incremental
mode, or substitute a different type-checking scope to establish this fix.

Host:

```sh
.venv/bin/mypy --show-traceback --config-file pyproject.toml .
```

Docker, with the same user as the development shell:

```sh
docker exec --user dev-user speleodb_local_django \
  mypy --show-traceback --config-file pyproject.toml .
```

Verified results on September 15, 2026, all with exit code 0:

| Environment              | Cache state | Result                        |
| ------------------------ | ----------- | ----------------------------- |
| Host                     | Cold        | No issues in 715 source files |
| Host                     | Warm        | No issues in 715 source files |
| Docker `dev-user`        | Cold        | No issues in 716 source files |
| Docker `dev-user`        | Warm        | No issues in 716 source files |
| Host, final source scope | Warm        | No issues in 716 source files |

Source discovery increased to 716 files while other task work continued; it was
not a type-checking exclusion difference. No test database, pre-commit hooks, or
commits were used to validate this configuration change.

## Performance and limitations

Each environment builds its own cache once and retains normal incremental
checking afterward. This uses more disk than sharing one cache but avoids
cross-environment cache writes and preserves the ordinary developer command.
Type-checking settings and checked files are unchanged. A cold run can still
report genuine type errors; cache isolation must never hide those diagnostics.
