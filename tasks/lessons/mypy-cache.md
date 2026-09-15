# Verify the normal type-checking command

The user reported a direct mypy crash after earlier checks used temporary cache
overrides. Passing with an isolated command-line cache diagnosed the failure
boundary but did not fix the command the user runs.

- Inspect the actual exception and effective cache path before changing type
  checks. This incident raised a SQLite database error in mypy's cache code.
- Keep writable tool caches outside a checkout shared by host and container
  runtimes. Configure ownership once in the repository so ordinary commands
  inherit it; do not rely on agents remembering special command-line flags.
- Preserve a problematic cache for diagnosis instead of deleting it silently.
  Distinguish the original reproduced error from later inspection results.
- Verify a cold run and a warm run using the exact normal command in both
  environments, including the container's regular user. A root-only pass can
  miss cache permission or home-directory problems affecting developers.
- Do not claim that an isolated-cache pass fixes the normal workflow until the
  durable configuration is in place and that workflow has passed directly.
- Respect the user's explicit ban on pre-commit/prek. Direct mypy verification
  needs no hooks, test database, or commit.
