# Node Tooling

## Intent

The repository uses one root Node workspace for Tailwind, esbuild, linting, and
JavaScript tests. Local development and Docker should use Node 22.13.0 or newer
on the Node 22 line so toolchain engine requirements stay aligned.

## Version Boundaries

- `concurrently` 10.x is allowed because Docker and `.node-version` target Node
  22.
- Tailwind is split across exact `tailwindcss@4.3.1` and
  `@tailwindcss/cli@4.3.1` dependencies. The compiler package no longer owns
  the CLI binary.
- The migration contract pins the forms and typography plugins to `0.5.11`
  and `0.5.20`.
- `@parcel/watcher`, `esbuild`, and `fsevents` are the version-specific entries
  currently allowlisted in `allowScripts`. The list is an executable policy,
  not proof that a new lockfile is safe: audit the resolved package nodes and
  rerun npm's pending-script check whenever the lockfile changes.

## Tailwind Builds

The public and private stylesheets remain separate products. Their CSS
entrypoints own source discovery, config loading, and variants; JavaScript
configs only own theme extensions and plugins. Do not add `content` arrays or
CLI `-c` flags. See `tailwind-v4.md` for the complete contract.

Production verification must start from `npm run build` (which begins with
`build:clean`) or an equivalent explicit clean followed by the affected build.
Do not use output from a running Tailwind watcher as final evidence: incremental
watch state can retain a class that was removed from source. Generated outputs
are ignored, so browser checks must also record or otherwise verify the exact
fresh asset served by the application.

## Update Guidance

When updating JavaScript tooling:

- Run installs from the repository root.
- Keep `package.json` and `package-lock.json` as the canonical manifests.
- Check `npm approve-scripts --allow-scripts-pending` after dependency changes.
- Keep `.node-version`, Docker NodeSource setup, and package engine
  requirements aligned when changing major Node versions.
- Re-run clean installs on every supported Node line before recording lockfile,
  install-script, build, lint, or test results.

## Verification

Use these root commands after tooling changes:

- `npm install`
- `npm approve-scripts --allow-scripts-pending`
- `npm run build`
- `npm run lint:js`
- `npm run test:js`
