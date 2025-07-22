# -*- coding: utf-8 -*-

from __future__ import annotations

from django.http import HttpResponse
from django.http import HttpResponseRedirect
from django.test import TestCase
from django.urls import reverse
from parameterized.parameterized import parameterized
from rest_framework import status

from speleodb.users.tests.factories import UserFactory


class ViewFunctionalityTest(TestCase):
    @parameterized.expand(
        [
            # General routes
            ("home", None),
            ("about", None),
            ("people", None),
            ("roadmap", None),
            ("changelog", None),
            ("terms_and_conditions", None),
            ("privacy_policy", None),
            # Webviews
            ("webview_ariane", None),
            # User Auth Management
            ("account_login", None),
            ("account_signup", None),
            ("account_confirm_email", {"key": "abc123-def456:ghi789"}),
            ("account_reset_password", None),
            (
                "account_reset_password_from_key",
                {"uidb36": "test@speleodb.org", "key": "abc123-def456"},
            ),
        ]
    )
    def test_view_unauthenticated(
        self, name: str, kwargs: dict[str, str] | None
    ) -> None:
        self.execute_test(name=name, kwargs=kwargs)

    def test_view_logout(self) -> None:
        user = UserFactory.create()
        self.client.force_login(user)

        self.execute_test(
            name="account_logout", kwargs=None, expected_status=status.HTTP_302_FOUND
        )

    def execute_test(
        self,
        name: str,
        kwargs: dict[str, str] | None,
        expected_status: int = status.HTTP_200_OK,
    ) -> None:
        url = reverse(name, kwargs=kwargs)

        response = self.client.get(url)

        if expected_status != status.HTTP_302_FOUND:
            assert isinstance(response, HttpResponse), type(response)
        else:
            assert isinstance(response, HttpResponseRedirect), type(response)

        assert response.status_code == expected_status

        assert response["Content-Type"].startswith("text/html"), response[
            "Content-Type"
        ]
