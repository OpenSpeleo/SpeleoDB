# -*- coding: utf-8 -*-

from __future__ import annotations

from django.contrib.auth import get_user
from django.urls import reverse
from parameterized.parameterized import parameterized
from rest_framework import status

from speleodb.api.v1.tests.base_testcase import BaseAPITestCase
from speleodb.common.enums import UserAction
from speleodb.common.enums import UserApplication
from speleodb.users.models import AccountEvent
from speleodb.users.tests.factories import UserFactory
from speleodb.utils.test_utils import named_product

USER_TEST_PASSWORD = "YeeOfLittleFaith"  # noqa: S105


class TestTokenAuth(BaseAPITestCase):
    def test_token_retrieval_unverified_email(self) -> None:
        endpoint = reverse("api:v1:user-auth-token")

        user = UserFactory.create()

        # Reset the user password since the factory sets a random one.
        user.set_password(USER_TEST_PASSWORD)
        user.save()

        response = self.client.post(
            endpoint,
            {"email": user.email, "password": USER_TEST_PASSWORD},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert (
            "Email address has not been verified"
            in response.data["errors"]["non_field_errors"][0]
        )

    def test_token_retrieval_works(self) -> None:
        endpoint = reverse("api:v1:user-auth-token")

        # Reset the user password since the factory sets a random one.
        self.user.set_password(USER_TEST_PASSWORD)
        self.user.save()

        response = self.client.post(
            endpoint,
            {"email": self.user.email, "password": USER_TEST_PASSWORD},
        )
        assert response.status_code == status.HTTP_200_OK, response.data

        target = {
            "token": self.token.key,
            "user": self.user.email,
        }

        assert response.data == target

    @parameterized.expand(["Token", "Bearer"])
    def test_token_auth_works(self, token_header: str) -> None:
        endpoint = reverse("api:v1:user-auth-token")

        auth = f"{token_header} {self.token.key}"
        response = self.client.get(endpoint, headers={"authorization": auth})
        assert response.status_code == status.HTTP_200_OK, response.data

    def test_get_creates_login_event(self) -> None:
        endpoint = reverse("api:v1:user-auth-token")
        auth = self.header_prefix + self.token.key

        response = self.client.get(
            endpoint,
            headers={
                "authorization": auth,
                "user-agent": "Compass/2.3.1 (Android)",
                "x-forwarded-for": "203.0.113.45, 10.0.0.7",
            },
            REMOTE_ADDR="10.0.0.7",
        )

        assert response.status_code == status.HTTP_200_OK, response.data

        event = AccountEvent.objects.get()
        assert event.user == self.user
        assert event.action == UserAction.LOGIN
        assert event.application == UserApplication.COMPASS_APP
        assert event.ip_addr == "203.0.113.45"

    def test_post_creates_login_event(self) -> None:
        endpoint = reverse("api:v1:user-auth-token")

        # Reset the user password since the factory sets a random one.
        self.user.set_password(USER_TEST_PASSWORD)
        self.user.save()

        response = self.client.post(
            endpoint,
            {"email": self.user.email, "password": USER_TEST_PASSWORD},
            headers={"user-agent": "Ariane/7.0.0 (iPhone)"},
            REMOTE_ADDR="198.51.100.11",
        )

        assert response.status_code == status.HTTP_200_OK, response.data

        event = AccountEvent.objects.get()
        assert event.user == self.user
        assert event.action == UserAction.LOGIN
        assert event.application == UserApplication.ARIANE_APP
        assert event.ip_addr == "198.51.100.11"

    @parameterized.expand(["PUT", "PATCH"])
    def test_put_patch_do_not_create_login_event(self, method: str) -> None:
        endpoint = reverse("api:v1:user-auth-token")

        # Reset the user password since the factory sets a random one.
        self.user.set_password(USER_TEST_PASSWORD)
        self.user.save()

        method_fn = getattr(self.client, method.lower())
        response = method_fn(
            endpoint,
            {"email": self.user.email, "password": USER_TEST_PASSWORD},
            HTTP_USER_AGENT="Compass/2.3.1 (Android)",
            REMOTE_ADDR="198.51.100.12",
        )

        assert response.status_code == status.HTTP_201_CREATED, response.data
        assert AccountEvent.objects.filter(action=UserAction.LOGIN).count() == 0
        assert AccountEvent.objects.filter(action=UserAction.TOKEN_REFRESH).count() == 1

    def test_failed_post_does_not_create_login_event(self) -> None:
        endpoint = reverse("api:v1:user-auth-token")

        response = self.client.post(
            endpoint,
            {"email": self.user.email, "password": "incorrect-password"},
            headers={"user-agent": "Ariane/7.0.0 (iPhone)"},
            REMOTE_ADDR="198.51.100.12",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.data
        assert AccountEvent.objects.count() == 0

    def test_failed_get_does_not_create_login_event(self) -> None:
        endpoint = reverse("api:v1:user-auth-token")

        response = self.client.get(endpoint)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED, response.data
        assert AccountEvent.objects.count() == 0

    @parameterized.expand(
        named_product(method=["POST", "PUT", "PATCH"], is_authenticated=[True, False])
    )
    def test_token_refresh_works(self, method: str, is_authenticated: bool) -> None:
        if method not in ["POST", "PUT", "PATCH"]:
            raise ValueError(f"Method `{method}` is not allowed.")

        # Reset the user password since the factory sets a random one.
        self.user.set_password(USER_TEST_PASSWORD)
        self.user.save()

        if is_authenticated:
            self.client.force_login(self.user)
            assert get_user(self.client).is_authenticated

        method_fn = getattr(self.client, method.lower())

        endpoint = reverse("api:v1:user-auth-token")
        response = method_fn(
            endpoint,
            {"email": self.user.email, "password": USER_TEST_PASSWORD}
            if not is_authenticated
            else None,
        )

        expected_status = (
            status.HTTP_200_OK if method.upper() == "POST" else status.HTTP_201_CREATED
        )
        assert response.status_code == expected_status, (
            response.data,
            expected_status,
            method,
        )

        data = response.data

        assert data["user"] == self.user.email

        token = response.data["token"]
        if method.upper() != "POST":
            assert self.token.key != token, (self.token.key, token)
        else:
            assert self.token.key == token, (self.token.key, token)

    @parameterized.expand(["POST", "PUT", "PATCH"])
    def test_token_refresh_unverified_email(self, method: str) -> None:
        if method not in ["POST", "PUT", "PATCH"]:
            raise ValueError(f"Method `{method}` is not allowed.")

        user = UserFactory.create()

        # Reset the user password since the factory sets a random one.
        user.set_password(USER_TEST_PASSWORD)
        user.save()

        method_fn = getattr(self.client, method.lower())

        endpoint = reverse("api:v1:user-auth-token")
        response = method_fn(
            endpoint, {"email": user.email, "password": USER_TEST_PASSWORD}
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert (
            "Email address has not been verified"
            in response.data["errors"]["non_field_errors"][0]
        )

    def test_wrong_password(self) -> None:
        response = self.client.post(
            reverse("api:v1:user-auth-token"),
            {"email": self.user.email, "password": "YeeOfLittleFaith"},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.data

        assert "token" not in response.data, response.data
        assert not response.data["success"], response.data

    def test_not_existing_email(self) -> None:
        response = self.client.post(
            reverse("api:v1:user-auth-token"),
            {"email": "chuck@norris.com", "password": "YeeOfLittleFaith"},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.data

        assert "token" not in response.data, response.data
        assert not response.data["success"], response.data

    def test_missing_password(self) -> None:
        response = self.client.post(
            reverse("api:v1:user-auth-token"),
            {"email": self.user.email},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.data

        assert "token" not in response.data, response.data
        assert not response.data["success"], response.data

        assert "password" in response.data["errors"], response.data
        assert "This field is required" in str(response.data["errors"]["password"]), (
            response.data
        )

    def test_missing_email(self) -> None:
        response = self.client.post(
            reverse("api:v1:user-auth-token"),
            {"password": "YeeOfLittleFaith"},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.data

        assert "token" not in response.data, response.data
        assert not response.data["success"], response.data

        assert "email" in response.data["errors"], response.data
        assert "This field is required" in str(response.data["errors"]["email"]), (
            response.data
        )
