# Node Tooling

## Intent

The repository uses one root Node workspace for Tailwind, esbuild, linting, and
JavaScript tests. Local development and Docker should use Node 22.13.0 or newer
on the Node 22 line so toolchain engine requirements stay aligned.

## Version Boundaries

- `concurrently` 10.x is allowed because Docker and `.node-version` target Node
  22.
- `esbuild` and `fsevents` are approved in `allowScripts` because npm 11
  reports packages with install scripts that have not been reviewed. Approvals
  are pinned to the reviewed installed versions.

## Update Guidance

When updating JavaScript tooling:

- Run installs from the repository root.
- Keep `package.json` and `package-lock.json` as the canonical manifests.
- Check `npm approve-scripts --allow-scripts-pending` after dependency changes.
- Keep `.node-version`, Docker NodeSource setup, and package engine
  requirements aligned when changing major Node versions.

## Verification

Use these root commands after tooling changes:

- `npm install`
- `npm approve-scripts --allow-scripts-pending`
- `npm run build`
