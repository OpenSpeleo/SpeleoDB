from __future__ import annotations

from typing import Any

from allauth.account.models import EmailAddress
from django.conf import settings
from django.core.management.base import BaseCommand
from django.core.management.base import CommandError
from django.db import transaction

from speleodb.users.models import User

LOCAL_SUPERUSER_EMAIL = "contact@speleodb.org"
LOCAL_SUPERUSER_NAME = "SpeleoDB Administrator"
LOCAL_SUPERUSER_PASSWORD = "contact"  # noqa: S105
LOCAL_SUPERUSER_COUNTRY_CODE = "US"


class Command(BaseCommand):
    help = "Create or repair the fixed development-only local superuser."

    @transaction.atomic
    def handle(self, *args: Any, **options: Any) -> None:
        if not settings.DEBUG:
            raise CommandError("ensure_local_superuser is restricted to DEBUG mode.")

        user, created = User.objects.get_or_create(
            email=LOCAL_SUPERUSER_EMAIL,
            defaults={
                "name": LOCAL_SUPERUSER_NAME,
                "country": LOCAL_SUPERUSER_COUNTRY_CODE,
                "is_active": True,
                "is_staff": True,
                "is_superuser": True,
            },
        )

        changed_fields: list[str] = []
        for field, value in (
            ("is_active", True),
            ("is_staff", True),
            ("is_superuser", True),
        ):
            if getattr(user, field) != value:
                setattr(user, field, value)
                changed_fields.append(field)

        if not user.name:
            user.name = LOCAL_SUPERUSER_NAME
            changed_fields.append("name")

        if str(user.country) != LOCAL_SUPERUSER_COUNTRY_CODE:
            user.country = LOCAL_SUPERUSER_COUNTRY_CODE
            changed_fields.append("country")

        # set_password hashes directly and intentionally does not invoke Django's
        # password validators. These credentials are for the local DEBUG stack only.
        if not user.check_password(LOCAL_SUPERUSER_PASSWORD):
            user.set_password(LOCAL_SUPERUSER_PASSWORD)
            changed_fields.append("password")

        if changed_fields:
            user.save(update_fields=changed_fields)

        EmailAddress.objects.filter(user=user, primary=True).exclude(
            email=LOCAL_SUPERUSER_EMAIL
        ).update(primary=False)
        EmailAddress.objects.update_or_create(
            email=LOCAL_SUPERUSER_EMAIL,
            defaults={
                "user": user,
                "verified": True,
                "primary": True,
            },
        )

        action = "created" if created else "already present and repaired"
        self.stdout.write(
            self.style.SUCCESS(
                f"Local superuser {LOCAL_SUPERUSER_EMAIL} {action}; email verified."
            )
        )
