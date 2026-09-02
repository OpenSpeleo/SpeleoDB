# GIS Layer and GPS Track Settings Workflows

## Goal

Align GIS Layers and GPS Tracks with the established entity workflow used by
Projects and Surface Networks: a listing opens a dedicated Details page, which
provides User Access Control and an administrator-only Danger Zone.

## Implementation

- [x] Add Details and Danger Zone routes while preserving permission URLs.
- [x] Add shared settings-shell, details, permissions, and danger-zone
      templates.
- [x] Enforce reader, writer, and administrator presentation in frontend views.
- [x] Keep source download and GPX export on listings and Details pages.
- [x] Remove inline listing edit/delete modals while preserving upload/import.
- [x] Reuse the shared list loader, entity form, permission modal, and danger
      flow.
- [x] Keep private sidebar highlighting aligned with the new routes.
- [x] Update GIS Layer and GPS Track documentation.
- [x] Add focused route, view, JavaScript, and shared-helper coverage.

## Verification

- [x] Run focused Django and JavaScript tests.
- [x] Run full Django and JavaScript suites.
- [x] Run JavaScript lint, targeted Ruff/mypy, Django checks, and Vite build.
- [x] Verify desktop and mobile workflows in the authenticated local
      application.
- [x] Review the final diff, whitespace, staged state, and subtree boundaries.

## Review / Results

Implemented both entity workflows with the exact listing right-arrow asset and
the existing Surface Network responsive settings navigation. The shared Details,
User Access, and Danger Zone templates replace four entity-specific permission
templates/snippets and both sets of inline listing mutation modals.

Verification completed:

- Focused Django: 58 passed.
- Focused JavaScript: 11 passed.
- Full Django: 4,052 passed, 155 skipped, 38 subtests passed.
- Full JavaScript: 977 passed across 58 files.
- ESLint, Ruff, mypy, Django system checks, and production Vite build passed.
- Authenticated desktop/mobile checks covered both listings and all Details,
  User Access, and Danger Zone routes without performing mutations.
