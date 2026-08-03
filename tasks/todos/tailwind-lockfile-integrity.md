# Tailwind Lockfile Integrity Repair

## Plan

- [x] Inspect the failing contract and identify every required package without
      integrity metadata.
- [x] Restore registry resolution and integrity metadata without changing the
      selected dependency graph.
- [x] Document the lockfile-generation invariant and its verification strategy.
- [x] Inspect the final diff and report the test command for the user to run.

## Root Cause

The dependency refresh rewrote the root lockfile from the installed tree. npm's
hidden `node_modules/.package-lock.json` omits registry resolution metadata for
unchanged packages, and that incomplete metadata propagated into
`package-lock.json`. As a result, 159 registry package nodes lost both
`resolved` and `integrity`, including `@tailwindcss/forms` and
`@tailwindcss/typography`, while newly resolved packages retained those fields.

## Review

Restored `resolved` and `integrity` for all 159 affected registry nodes using
the prior committed metadata only when package path and version matched. A
metadata-independent comparison confirmed that the repaired lockfile preserves
the staged 220-node dependency graph exactly. Static contract inspection also
confirmed that manifest dependencies match the lockfile, every registry node has
a `sha512` checksum, and `allowScripts` still exactly matches the lone
install-script package.

The JavaScript tests were intentionally not run at the user's request. User-run
verification:

```bash
npm run test:js -- frontend_private/static/private/js/forms/tailwind_contract.test.js
```
