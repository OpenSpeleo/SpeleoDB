from __future__ import annotations

from io import StringIO

import pytest
from allauth.account.models import EmailAddress
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings

from speleodb.users.models import User

LOCAL_SUPERUSER_EMAIL = "contact@speleodb.org"
LOCAL_SUPERUSER_PASSWORD = "contact"  # noqa: S105
LOCAL_SUPERUSER_COUNTRY_CODE = "US"


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_ensure_local_superuser_is_verified_and_idempotent() -> None:
    output = StringIO()

    call_command("ensure_local_superuser", stdout=output)
    call_command("ensure_local_superuser", stdout=output)

    user = User.objects.get(email=LOCAL_SUPERUSER_EMAIL)
    assert user.name == "SpeleoDB Administrator"
    assert str(user.country) == LOCAL_SUPERUSER_COUNTRY_CODE
    assert user.is_active is True
    assert user.is_staff is True
    assert user.is_superuser is True
    assert user.check_password(LOCAL_SUPERUSER_PASSWORD)
    assert User.objects.filter(email=LOCAL_SUPERUSER_EMAIL).count() == 1

    email_address = EmailAddress.objects.get(email=LOCAL_SUPERUSER_EMAIL)
    assert email_address.user == user
    assert email_address.verified is True
    assert email_address.primary is True
    assert EmailAddress.objects.filter(email=LOCAL_SUPERUSER_EMAIL).count() == 1
    assert "email verified" in output.getvalue()


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_ensure_local_superuser_repairs_existing_account() -> None:
    user = User.objects.create_user(
        email=LOCAL_SUPERUSER_EMAIL,
        password="different-password",  # noqa: S106
        name="Existing Administrator",
        country="FR",
        is_active=False,
    )
    EmailAddress.objects.create(
        user=user,
        email=LOCAL_SUPERUSER_EMAIL,
        verified=False,
        primary=False,
    )

    call_command("ensure_local_superuser")

    user.refresh_from_db()
    email_address = EmailAddress.objects.get(email=LOCAL_SUPERUSER_EMAIL)
    assert user.name == "Existing Administrator"
    assert str(user.country) == LOCAL_SUPERUSER_COUNTRY_CODE
    assert user.is_active is True
    assert user.is_staff is True
    assert user.is_superuser is True
    assert user.check_password(LOCAL_SUPERUSER_PASSWORD)
    assert email_address.verified is True
    assert email_address.primary is True


@pytest.mark.django_db
@override_settings(DEBUG=False)
def test_ensure_local_superuser_refuses_non_debug_settings() -> None:
    with pytest.raises(CommandError, match="restricted to DEBUG mode"):
        call_command("ensure_local_superuser")
