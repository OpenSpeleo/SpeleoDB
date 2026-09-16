# CI template contract failures

- [x] Compare the eight failures with current templates and repository rules.
- [x] Verify the plan: preserve the current utility styling and valid HTML;
      update assertions to check element structure and attributes.
- [x] Repair dashboard avatar and chart container assertions.
- [x] Repair dark document assertions while preserving metadata order checks.
- [x] Run both affected Python modules, JavaScript tests, and focused lint/type
      checks in the existing application container.
- [x] Record verification and review results.

## Scope and approach

The dashboard now uses Tailwind classes instead of inline styles, and formatted
HTML uses self-closing meta tags. Existing assertions depend on the previous
serialization. Keep production templates intact and check the same UI contracts
without relying on the obsolete inline declarations or void-tag spelling.

## Review

Production templates and runtime behavior are unchanged. Dashboard assertions
check three square, fully rounded skeleton placeholders and each canvas's direct
parent positioning and height. Dark document assertions use Django's HTML parser
to check metadata attributes, placement in the head before stylesheet links,
root classes, and stylesheet counts independent of formatting.

Verification inside `speleodb_local_django` at `/app`:

- Both affected Python modules: **84 passed**, including all eight reported
  failures.
- `npm run test:js`: **1,040 passed** across 64 files.
- `npm run lint:js`: passed.
- Ruff check, Ruff format check, and mypy on both changed Python files: passed.
- `git diff --check`: passed.

GitLab audit `90a690d628564c1ebd105784e317ae0b` reports zero creations, zero
creation POSTs, zero violations, and no unresolved outcomes or allocations;
there were no repositories requiring cleanup. The full Python suite was not
rerun for these test-only changes.
