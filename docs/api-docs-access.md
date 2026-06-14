# API Docs Access

## Intent

SpeleoDB exposes API documentation and the generated schema as useful
developer references. Staff and admin users should continue seeing those links,
and selected non-staff users can now be granted the same private-menu visibility
without receiving Django admin access.

## Access Flag

`User.has_api_doc_access` is a Boolean account flag stored on the custom user
model. It defaults to `False` for existing and newly created users.

The flag is managed from Django admin in the user permissions section. It is
also visible in the user changelist and available as a changelist filter.

## Menu Behavior

The private menu shows API Docs and API Schema links when any of the following
is true:

- `user.is_staff`
- `user.is_superuser`
- `user.has_api_doc_access`

This applies to both mobile sidebar links and desktop header links.

## Boundaries

This flag only controls private-menu visibility for API Docs and API Schema.
It does not grant Django admin access, staff status, superuser status, or
additional API permissions. Direct endpoint authorization remains owned by the
existing API docs and schema views.

## Verification

Run the focused users/admin and private dashboard tests after applying the
migration:

```bash
pytest speleodb/users/tests/test_admin.py frontend_private/tests/test_dashboard_views.py
```
