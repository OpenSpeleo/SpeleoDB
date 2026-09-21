# -*- coding: utf-8 -*-

from __future__ import annotations

import socket
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from allauth.account.models import EmailAddress
from allauth.core.context import request_context
from allauth.headless.account.inputs import SignupInput
from django.core import mail
from django.test import RequestFactory
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from speleodb.common.enums import UserAction
from speleodb.users.adapters import AccountAdapter
from speleodb.users.models import AccountEvent
from speleodb.users.models import User
from speleodb.users.tests.factories import UserFactory

if TYPE_CHECKING:
    from django.test.client import Client


pytestmark = pytest.mark.filterwarnings(
    "error::django.utils.deprecation.RemovedInDjango70Warning"
)


@pytest.mark.django_db
class TestAccountSignup:
    def test_signup_saves_required_profile_before_first_insert(
        self, client: Client
    ) -> None:
        response = client.post(
            reverse("headless:browser:account:signup"),
            data={
                "email": "signup@example.com",
                "name": "Ada Lovelace",
                "country": "US",
                "password": "Sup3r-S3cur3-P@ssw0rd!",
                "password2": "Sup3r-S3cur3-P@ssw0rd!",
            },
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert {"id": "verify_email", "is_pending": True} in response.json()["data"][
            "flows"
        ]
        user: User = User.objects.get(email="signup@example.com")
        assert user.name == "Ada Lovelace"
        assert str(user.country) == "US"
        assert user.check_password("Sup3r-S3cur3-P@ssw0rd!")
        assert EmailAddress.objects.filter(user=user, primary=True).exists()
        assert AccountEvent.objects.filter(user=user, action=UserAction.SIGNUP).exists()
        assert len(mail.outbox) == 1
        assert mail.outbox[0].to == [user.email]

    @pytest.mark.parametrize("name", [None, "", " \t\n ", "\u00a0\u2003"])
    def test_signup_rejects_missing_name(
        self, client: Client, name: str | None
    ) -> None:
        data: dict[str, str] = {
            "email": "unnamed-signup@example.com",
            "country": "US",
            "password": "Sup3r-S3cur3-P@ssw0rd!",
            "password2": "Sup3r-S3cur3-P@ssw0rd!",
        }
        if name is not None:
            data["name"] = name

        response = client.post(
            reverse("headless:browser:account:signup"),
            data=data,
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert any(error["param"] == "name" for error in response.json()["errors"])
        assert not User.objects.filter(email=data["email"]).exists()
        assert not mail.outbox

    def test_adapter_commit_false_populates_without_saving(self) -> None:
        request = RequestFactory().post(reverse("headless:browser:account:signup"))
        form = SignupInput(
            data={
                "email": "deferred-signup@example.com",
                "name": "Deferred User",
                "country": "FR",
                "password": "Sup3r-S3cur3-P@ssw0rd!",
                "password2": "Sup3r-S3cur3-P@ssw0rd!",
            }
        )
        user = User()

        with request_context(request):
            assert form.is_valid(), form.errors
            saved_user = AccountAdapter().save_user(request, user, form, commit=False)

        assert saved_user is user
        assert user.pk is None
        assert user.name == "Deferred User"
        assert str(user.country) == "FR"
        assert user.email == "deferred-signup@example.com"
        assert user.check_password("Sup3r-S3cur3-P@ssw0rd!")
        assert not User.objects.filter(email=user.email).exists()


@pytest.mark.django_db
class TestAccountAdapterSendMail:
    """
    Regression tests for the custom AccountAdapter.send_mail method.

    The custom adapter keeps backend delivery failures non-fatal for account mail.
    A previous bug caused ``KeyError: 'context'`` because
    ``globals()["context"]`` resolved against the adapter module's namespace,
    which did not import ``allauth.core.context``.
    """

    def test_smtp_failure_is_silent_only_for_account_mail(self) -> None:
        user: User = UserFactory.create()
        email_address: EmailAddress = EmailAddress.objects.create(
            user=user, email=user.email, verified=False, primary=True
        )
        request = RequestFactory().get("/")
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as unavailable:
            unavailable.bind(("127.0.0.1", 0))
            with (
                override_settings(
                    MAILERS={
                        "default": {
                            "BACKEND": "django.core.mail.backends.smtp.EmailBackend",
                            "OPTIONS": {
                                "host": "127.0.0.1",
                                "port": unavailable.getsockname()[1],
                                "timeout": 1,
                            },
                        },
                    },
                ),
                request_context(request),
            ):
                email_address.send_confirmation(request, signup=True)
                with pytest.raises(ConnectionRefusedError):
                    mail.send_mail("Delivery probe", "Body", None, [user.email])

        assert not mail.outbox

    def test_unexpected_delivery_error_is_not_silenced(self) -> None:
        request = RequestFactory().get("/")
        with (
            request_context(request),
            patch(
                "django.core.mail.backends.locmem.EmailBackend.send_messages",
                side_effect=RuntimeError("Unexpected delivery error"),
            ),
            pytest.raises(RuntimeError, match="Unexpected delivery error"),
        ):
            AccountAdapter().send_mail(
                "account/email/email_confirmation",
                "recipient@example.com",
                {"activate_url": "https://example.com/confirm/"},
            )

    def test_send_confirmation_email_does_not_raise_key_error(self) -> None:
        """
        Reproduce the exact code path from the production traceback:

            EmailAddress.send_confirmation(request)
            → EmailConfirmation.send(request)
            → get_adapter().send_confirmation_mail(request, confirmation, signup)
            → adapter.send_mail(template_prefix, email, ctx)   # ← KeyError here

        Before the fix this raises:
            KeyError: 'context'
            at speleodb/users/adapters.py in send_mail
        """
        user = UserFactory.create()
        email_address = EmailAddress.objects.create(
            user=user,
            email=user.email,
            verified=False,
            primary=True,
        )

        request = RequestFactory().get("/")
        # allauth stores the current request in a ContextVar; the adapter
        # retrieves it via ``allauth.core.context.request``.
        with request_context(request):
            email_address.send_confirmation(request, signup=True)

        assert len(mail.outbox) == 1, (
            f"Expected 1 verification email, got {len(mail.outbox)}"
        )
        assert mail.outbox[0].to == [user.email]

    def test_user_email_change_sends_verification_email(self) -> None:
        """
        Reproduce the code path triggered by ``PATCH /api/v2/user/``
        when the user changes their email address:

            UserSerializer.update()
            → EmailAddress.objects.add_new_email(request, user, email)
            → send_verification_email_to_address(request, instance)
            → address.send_confirmation(request)
            → adapter.send_mail(...)   # ← KeyError here before fix

        Before the fix this raises:
            KeyError: 'context'
            at speleodb/users/adapters.py in send_mail
        """
        password = "Sup3r-S3cur3-P@ssw0rd!"  # noqa: S105
        user = UserFactory.create(password=password)
        EmailAddress.objects.create(
            user=user,
            email=user.email,
            verified=True,
            primary=True,
        )

        api_client = APIClient()
        api_client.force_authenticate(user=user)

        response = api_client.patch(
            reverse("api:v2:user-detail"),
            data={"email": "new-email@example.com"},
            format="json",
        )

        assert response.status_code != status.HTTP_500_INTERNAL_SERVER_ERROR, (
            f"PATCH /api/v2/user/ crashed: {response.content.decode()}"
        )
        assert response.status_code == status.HTTP_200_OK, (
            f"Unexpected status {response.status_code}: {response.content.decode()}"
        )

        # A verification email should be sent to the *new* address.
        assert len(mail.outbox) == 1, (
            f"Expected 1 verification email, got {len(mail.outbox)}"
        )
        assert mail.outbox[0].to == ["new-email@example.com"]
