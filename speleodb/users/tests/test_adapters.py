# -*- coding: utf-8 -*-

from __future__ import annotations

import pytest
from allauth.account.models import EmailAddress
from allauth.core.context import request_context
from django.core import mail
from django.test import RequestFactory
from rest_framework import status
from rest_framework.test import APIClient

from speleodb.users.tests.factories import UserFactory


@pytest.mark.django_db
class TestAccountAdapterSendMail:
    """
    Regression tests for the custom AccountAdapter.send_mail method.

    The custom adapter overrides send_mail to pass ``fail_silently=True``.
    A previous bug caused ``KeyError: 'context'`` because
    ``globals()["context"]`` resolved against the adapter module's namespace,
    which did not import ``allauth.core.context``.
    """

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
        Reproduce the code path triggered by ``PATCH /api/v1/user/``
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
            "/api/v1/user/",
            data={"email": "new-email@example.com"},
            format="json",
        )

        assert response.status_code != status.HTTP_500_INTERNAL_SERVER_ERROR, (
            f"PATCH /api/v1/user/ crashed: {response.content.decode()}"
        )
        assert response.status_code == status.HTTP_200_OK, (
            f"Unexpected status {response.status_code}: {response.content.decode()}"
        )

        # A verification email should be sent to the *new* address.
        assert len(mail.outbox) == 1, (
            f"Expected 1 verification email, got {len(mail.outbox)}"
        )
        assert mail.outbox[0].to == ["new-email@example.com"]
