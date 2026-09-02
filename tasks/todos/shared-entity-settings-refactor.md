# Shared Entity Settings Refactor

## Goal

Move compatible entity settings pages onto the existing shared templates while
preserving each model's routes, permissions, fields, shell, and responsive UI.

## Implementation

- [x] Inventory Details, User Access, and Danger Zone templates by model.
- [x] Make the shared templates accept an existing model-specific base shell.
- [x] Reuse shared Details for Surface Network without introducing a color
      field.
- [x] Reuse shared User Access for Surface Network, Experiment, Cylinder Fleet,
      Sensor Fleet, and Landmark Collection.
- [x] Reuse shared Danger Zone for Surface Network, Experiment, Cylinder Fleet,
      Sensor Fleet, Landmark Collection, GIS View, and Team.
- [x] Preserve the purpose-built Project Danger Zone and its staged user edits.
- [x] Remove obsolete model-specific permission snippets and styles.
- [x] Keep responsive card/table visibility inside the shared template.
- [x] Keep Danger Zone warning copy entirely inside the shared template.
- [x] Extend shared-template, field, permission-ordering, and responsive-markup
      coverage.
- [x] Document the shared template contract and ownership boundaries.

## Verification

- [x] Focused Django view/render suite.
- [x] Focused JavaScript asset/controller suite.
- [x] Ruff and mypy on affected Python modules.
- [x] Production Vite build.
- [x] Authenticated 390px browser checks for GIS Layer, GPS Track, and Surface
      Network User Access pages.
- [x] Full Django and JavaScript suites.
- [x] JavaScript lint, Django system check, final Ruff/mypy, and final Vite
      build.
- [x] Adversarial principal-engineer review and corrective pass.
- [x] Full standalone web `prek run -a` validation.
- [x] Whitespace, staged-state, and subtree-boundary review.

## Review / Results

The compatible settings pages now share one implementation while retaining their
existing route names, authorization behavior, model-specific base shells, and
supported fields. Project's purpose-built Danger Zone was intentionally left
untouched. The User Access responsive visibility rules now live directly on the
shared card/table markup, preventing mobile and desktop variants from rendering
together when a route-specific stylesheet is absent.

Verification completed:

- Focused Django: 184 passed, 5 subtests passed.
- Full Django: 4,060 passed, 155 skipped, 43 subtests passed.
- Full JavaScript: 977 passed across 58 files.
- ESLint, Ruff, mypy, Django system checks, and production Vite build passed.
- Every standalone web prek hook passed, including security and dependency
  checks, full-project mypy, URL stability, JavaScript lint, and Vite build.
- Authenticated 390px checks on GIS Layer, GPS Track, and Surface Network User
  Access pages showed cards only with no horizontal overflow.

The adversarial review found one low-severity contract issue: GIS Layer and GPS
Track views exposed an unused plural-label context value. The corrective pass
removed both dead keys and reran focused Django, JavaScript, Ruff, and mypy
checks. No actionable correctness, security, authorization, responsive,
backward-compatibility, or data-handling issues remained.
