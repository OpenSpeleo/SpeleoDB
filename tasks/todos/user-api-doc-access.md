# User API Docs Access

## Plan

- [x] Confirm current user model, admin, and private menu gates.
- [x] Add `has_api_doc_access` to the custom user model with a default of `False`.
- [x] Add the users migration for the new field.
- [x] Expose the field in Django admin permissions, list display, and filters.
- [x] Update private menu API Docs/API Schema visibility to include staff, admin, or explicit API docs access.
- [x] Add regression tests for admin exposure and private menu visibility.
- [x] Document the feature intent and boundaries under `docs/`.
- [x] Record verification commands and results.

## Review

Implemented:

- Added `User.has_api_doc_access` with `default=False`.
- Added users migration `0008_user_has_api_doc_access`.
- Added `db_default=False` to the model and migration after the GIS landmark
  rollback migration test exposed historical-model inserts that omit newer user
  columns.
- Exposed the field in user admin permissions, list display, and filters.
- Updated private mobile and desktop API Docs/API Schema menu visibility to
  include staff, superuser, or explicit API docs access.
- Added regression coverage for default value, admin exposure, flagged user
  visibility, staff/superuser visibility, and non-admin panel visibility for
  flagged regular users.
- Added `docs/api-docs-access.md` and linked it from `docs/README.md`.
- Added `tasks/lessons/non-null-user-fields-need-db-defaults.md`.

Not run by request:

```bash
python manage.py migrate
pytest speleodb/users/tests/test_admin.py frontend_private/tests/test_dashboard_views.py
pytest speleodb/users/tests/test_swagger.py
ruff check speleodb/users frontend_private/tests
mypy speleodb/users frontend_private
```

Run:

```bash
git diff --check
```

Result: passed.
