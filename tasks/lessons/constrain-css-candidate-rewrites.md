# Constrain CSS candidate rewrites to scanner-owned sources

Bulk Tailwind candidate rewrites must operate only on class-bearing files in the
public/private source contract. A broad repository rewrite can silently touch
vendor assets, backend strings, fixtures, or documentation that the compiler
never scans.

Before a mechanical rewrite, derive the file list from the entrypoints'
`@source` directives. Afterward, inspect `git diff --name-only`, run a contract
scan for the old candidates, and restore any file outside that ownership set.
Generated CSS and vendored files are never rewrite inputs.
