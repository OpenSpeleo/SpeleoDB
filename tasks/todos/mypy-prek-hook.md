# Replace dmypy in the prek hook

- [x] Replace the daemon-backed type-checking hook with `mypy`.
- [x] Remove the root launcher's daemon-specific skip policy.
- [x] Update launcher tests, CI, and monorepo documentation.
- [x] Run focused and full monorepo verification.
- [x] Make every hook invocation check the complete project deterministically.

## Review

The prek hook now invokes regular `mypy` and passes across all selected web
Python files. The launcher keeps web virtual-environment discovery, fails
explicitly when `mypy` is unavailable, and no longer manages daemon state. The
hook disables prek filename passing and checks `.` so manual, all-files, and
changed-file invocations cover the same complete project.

Verification:

- `node --test tools/precommit-launcher.test.mjs`
- `bash scripts/run-precommit.sh apps/web:mypy --all-files`
- `node --test tools/*.test.mjs`
- `npm run test:monorepo`
- `make test-monorepo`
