# Default-off Django Debug Toolbar Panels

## Plan

- [x] Keep Django Debug Toolbar installed and visible in the local runtime.
- [x] Disable every canonical default panel through `DISABLE_PANELS`.
- [x] Disable expensive panel sub-options by default.
- [x] Prove the application, middleware, route, callback, and panel list remain
      configured while all panels start disabled.
- [x] Document panel activation and the performance rationale.
- [x] Verify focused tests, Ruff, mypy, Markdown formatting, and middleware
      rendering behavior.

## Review

The toolbar integration is always present in local settings. Its canonical
default panel list comes from the installed package and the same full set is
assigned to `DISABLE_PANELS`, so new package-default panels also begin disabled.
Developers can enable only the panel they need from the toolbar UI without an
environment change or restart.

Verification completed on 2026-07-19:

- the focused regression test passed and proves the toolbar shell is rendered;
- Ruff formatting and lint checks passed for the changed Python files;
- direct mypy passed for the changed settings and regression test;
- Django's system check passed under isolated local settings;
- Prettier confirmed all changed Markdown files use the expected style.
