# Isolate mypy caches from the shared checkout

- [x] Confirm mypy version and the host/container home directories.
- [x] Configure mypy's normal command to use a cache under the user's home.
- [x] Preserve the malformed checkout cache in a unique temporary directory.
- [x] Run host mypy twice, first cold then warm, without cache overrides.
- [x] Run Docker mypy as dev-user twice, first cold then warm, without
      overrides.
- [x] Document the cause, actual command results and verification lesson.

The user explicitly forbids running pre-commit or prek. This task uses direct
mypy commands, makes no commits, and does not use a test database.

## Review

Host cold/warm checks passed 715 files; Docker dev-user cold/warm checks passed
716 files after source discovery increased during concurrent task work. Every
run used the normal configured cache and exited 0. The old checkout cache is
preserved in `/tmp/speleodb-mypy-cache-gu6ey5ly/.mypy_cache`. The final host
warm check also passed all 716 files. No hooks, test database, or commits were
used.
