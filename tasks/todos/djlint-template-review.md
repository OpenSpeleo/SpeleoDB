# djLint template review

- [x] Inspect working tree, formatter configuration, coding rules, and lessons.
- [x] Verify scope: preserve existing changes, fix pending template lint, review
      each file before staging.
- [x] Review and fix public/error/admin templates one file at a time.
- [x] Review and fix project/team/shared settings templates one file at a time.
- [x] Review and fix fleet/experiment/surface-network templates one file at a
      time.
- [x] Review and fix private shell/map/landmark/tools/user/snippet templates one
      file at a time.
- [x] Run container djLint, template compilation, JavaScript tests/lint, and
      clean production build.
- [x] Review staged changes and document results in tasks/todo.md and docs/.

## Approach

Review formatter diffs against HEAD, preserve Django branches and runtime hooks,
repair real HTML nesting errors, and give buttons their intended types. Move
static inline declarations to existing owning stylesheets or equivalent utility
classes; preserve model-driven styles with narrowly documented lint exceptions
where needed. Do not disable lint rules globally. Stage each file only after its
review and individual formatter/lint checks. Parallel reviewers own disjoint
template groups.

## Review

Reviewed and staged all 108 changed HTML files individually. All 112 tracked
HTML files pass djLint; both actual pre-commit djLint hooks pass. Django
compiled all 112 templates. The container JavaScript suite passed 1,032 tests
across 62 files; ESLint passed. Nineteen database-free Django render tests
passed, with Ruff and mypy passing for the new Python tests. GitLab audit
recorded zero creation requests, creations, violations, or unresolved
allocations; no remote cleanup was needed. A clean production Vite build passed.
All 83 registered entries resolve to built files; the Django homepage renders
`assets/style-app-BJAvUyDT.css` from that manifest.

Regression coverage includes permission-branch nesting, native map toggles,
modal visibility, cloned Git/revision rows, and preserved layout declarations. A
second cascade review repaired lost style-only attributes and preserved runtime
map sizing against mobile CSS. Rules were not disabled globally; server-driven
colors retain narrowly documented H021 exceptions.

Unrelated concurrent logo work remains outside this task's staging.
