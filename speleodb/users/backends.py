# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from speleodb.users.models import User


STAFF_BLOCKED_APPS: frozenset[str] = frozenset(
    {
        "auth",  # Authentication and Authorization (Group, Permission)
        "sites",  # Sites framework
        "django_celery_beat",  # Periodic Tasks (celery-beat schedules)
    }
)


class StaffFullAdminAccessBackend:
    """Grant all Django permissions to active staff users.

    This lets staff see every model in the admin panel without manually
    assigning per-model permissions.  Apps listed in ``STAFF_BLOCKED_APPS``
    are completely hidden from staff.  Additional fine-grained restrictions
    (e.g. read-only User/EmailAddress tables, hidden hijack button,
    superuser-only Tokens) are enforced at the ModelAdmin level.
    """

    def authenticate(self, request: object, **kwargs: object) -> None:
        return None

    def has_perm(self, user_obj: User, perm: str, obj: object = None) -> bool:
        if not (user_obj.is_active and user_obj.is_staff):
            return False
        app_label, _, codename = perm.partition(".")
        if app_label in STAFF_BLOCKED_APPS:
            return False
        return not codename.startswith("delete_")

    def has_module_perms(self, user_obj: User, app_label: str) -> bool:
        if not (user_obj.is_active and user_obj.is_staff):
            return False
        return app_label not in STAFF_BLOCKED_APPS
