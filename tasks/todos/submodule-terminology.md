# Monorepo terminology cleanup

## Plan

- [x] Update integration notes to describe repositories and submodules.
- [x] Rename the repository-scope lesson and check for stale links.
- [x] Preserve accurate tree-traversal terminology and historical results.
- [x] Review Markdown changes, whitespace, and repository boundaries.

## Review

Updated integration wording without changing recorded validation results.
Renamed the scope lesson to `repository-scope.md`; no links used the old name.
Remaining tree terminology describes UI rendering, directory scanning, Git tree
traversal, or third-party source code and is still accurate.

Verification: repeated workspace search, reviewed Markdown diffs, and checked
whitespace in the parent, mobile, and web repositories. No application code,
configuration, or dependency files changed, so runtime tests are not applicable.
