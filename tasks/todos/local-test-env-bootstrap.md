# Local test environment bootstrap

## Plan

- [x] Extend the local GitLab provisioner to initialize and manage the ignored
      `.envs/test.env` alongside the development `.env`.
- [x] Provision separate development and test GitLab groups/tokens and write
      each credential set only to its corresponding private environment.
- [x] Manage separate development and test RustFS bucket names/custom domains
      while retaining the shared local RustFS service.
- [x] Preserve developer-owned values and keep repeated setup runs idempotent.
- [x] Add focused unit coverage for both managed environment files.
- [x] Allow Git operations in dynamically generated per-test repositories under
      the bind-mounted local work root with the Git version shipped by the
      image.
- [x] Update local-environment documentation and run focused Python, shell, and
      Compose validation.

## Review

The one-shot Compose setup now creates both private environment files from their
tracked templates when absent. It independently provisions or reuses the local
`speleodb` development group and `speleodb-test` test group, each with its own
non-expiring access token. Development credentials and the development RustFS
bucket are written only to `.env`; test credentials and the test bucket are
written only to `.envs/test.env`. Unrelated developer overrides remain intact,
both files retain mode `0600`, and an immediate second invocation makes no token
or file changes.

Enabling the real GitLab-backed tests exposed Docker Desktop's transient
ownership reporting for newly initialized repositories under the bind-mounted
`.workdir`. The image's Git 2.39 does not support a recursive `safe.directory`
pattern, so the private test env enables Git's wildcard trust mode. Normal
development processes retain the devcontainer's explicit `/workspace` trust.

Verification:

- focused setup and resource-isolation tests: 11 passed;
- Ruff and mypy passed for the provisioner and its tests;
- setup shell syntax and merged Compose rendering passed;
- a disposable live setup reused development GitLab group ID 2, created isolated
  test group ID 36 and its token, and synchronized the separate development and
  test RustFS bucket settings;
- an immediate second live setup reused both groups/tokens and reported both
  private env files already current;
- both previously failing upload modules passed in the devcontainer: 24 passed,
  4 skipped;
- root monorepo tool tests passed: 16 passed;
- `git diff --check` passed.

The broader `compose/tests` run had one unrelated macOS-host failure because the
Linux-only `prepare_node_modules` ownership script exited 127; the remaining 13
tests passed and one root-only case skipped.
