# Dependency-Agnostic Tailwind Contract

## Plan

- [x] Inventory unit tests for assertions against installed software versions.
- [x] Remove exact dependency and lockfile-format versions from the Tailwind
      contract.
- [x] Run the focused contract test and complete JavaScript verification.

## Review

The revised contract treats `package.json` and `package-lock.json` as the
dependency-version sources of truth. Unit tests only enforce the required
compiler package names, manifest/lockfile alignment, package integrity metadata,
and exact install-script approval coverage. The focused contract passes (12
tests), the full JavaScript suite passes (927 tests), and JavaScript lint
passes.
