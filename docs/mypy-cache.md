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

Mypy expands the home directory for the invoking user. The host uses its own
user cache; Docker's `dev-user` uses `/home/dev-user/.cache/speleodb/mypy`. The
application source remains shared at the host checkout and `/app`, but cache
writes stay on separate filesystems. An explicit `MYPY_CACHE_DIR` environment
variable overrides this setting and must not point back into the shared
checkout. See
[mypy cache configuration](https://mypy.readthedocs.io/en/stable/config_file.html#confval-cache_dir).

## Cache isolation

SQLite-backed incremental caches must not be shared by macOS processes and Linux
VM processes through a bind mount. SQLite WAL coordination requires processes on
the same host; separate environment-owned caches avoid that cross-kernel
sharing. See [SQLite WAL constraints](https://www.sqlite.org/wal.html).

## Verification

Run the normal command sequentially to compare initial and incremental checks. A
second invocation reads the first invocation's cache. Use the configured cache
and full project scope; disabling incremental mode or narrowing checked files
does not verify the ordinary developer workflow.

Host:

```sh
.venv/bin/mypy --show-traceback --config-file pyproject.toml .
```

Docker, with the same user as the development shell:

```sh
docker exec --user dev-user -w /app speleodb-monorepo-django \
  mypy --show-traceback --config-file pyproject.toml .
```

## Hook scope

The repository's local `mypy` prek hook invokes regular
`mypy --config-file pyproject.toml .` using the environment's installed project
dependencies. It does not use a daemon. `pass_filenames: false` keeps the same
whole-project scope for manual, changed-file, and all-file invocations;
`require_serial: true` avoids parallel hook batches. The same environment-owned
cache applies to direct and hook commands. A successful check of selected files
is not equivalent to this complete-project contract.

## Performance and limitations

Each environment builds its own cache once and retains normal incremental
checking afterward. This uses more disk than sharing one cache but avoids
cross-environment cache writes and preserves the ordinary developer command.
Type-checking settings and checked files are unchanged. A cold run can still
report genuine type errors; cache isolation must never hide those diagnostics.
