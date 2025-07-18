# -*- coding: utf-8 -*-

from __future__ import annotations

from django.contrib.auth import get_user
from django.urls import reverse
from parameterized.parameterized import parameterized
from rest_framework import status

from speleodb.api.v1.tests.base_testcase import BaseAPITestCase
from speleodb.utils.test_utils import named_product

USER_TEST_PASSWORD = "YeeOfLittleFaith"  # noqa: S105


class TestTokenAuth(BaseAPITestCase):
    def test_token_retrieval_works(self) -> None:
        endpoint = reverse("api:v1:auth_token")

        # Reset the user password since the factory sets a random one.
        self.user.set_password(USER_TEST_PASSWORD)
        self.user.save()

        response = self.client.post(
            endpoint,
            {"email": self.user.email, "password": USER_TEST_PASSWORD},
        )
        assert response.status_code == status.HTTP_200_OK, response.data

        target = {
            "success": True,
            "token": self.token.key,
            "url": f"http://testserver{endpoint}",
        }

        for key, val in target.items():
            assert val == response.data[key], response.data

    @parameterized.expand(["Token", "Bearer"])
    def test_token_auth_works(self, token_header: str) -> None:
        endpoint = reverse("api:v1:auth_token")

        auth = f"{token_header} {self.token.key}"
        response = self.client.get(endpoint, headers={"authorization": auth})
        assert response.status_code == status.HTTP_200_OK, response.data

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

        endpoint = reverse("api:v1:auth_token")
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

        token = response.data.pop("token")
        if method.upper() != "POST":
            assert self.token.key != token, (self.token.key, token)
        else:
            assert self.token.key == token, (self.token.key, token)

        target = {
            "success": True,
            "url": f"http://testserver{endpoint}",
        }

        for key, val in target.items():
            assert val == response.data[key], response.data

    def test_wrong_password(self) -> None:
        response = self.client.post(
            reverse("api:v1:auth_token"),
            {"email": self.user.email, "password": "YeeOfLittleFaith"},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.data

        assert "token" not in response.data, response.data
        assert not response.data["success"], response.data

    def test_not_existing_email(self) -> None:
        response = self.client.post(
            reverse("api:v1:auth_token"),
            {"email": "chuck@norris.com", "password": "YeeOfLittleFaith"},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.data

        assert "token" not in response.data, response.data
        assert not response.data["success"], response.data

    def test_missing_password(self) -> None:
        response = self.client.post(
            reverse("api:v1:auth_token"),
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
            reverse("api:v1:auth_token"),
            {"password": "YeeOfLittleFaith"},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.data

        assert "token" not in response.data, response.data
        assert not response.data["success"], response.data

        assert "email" in response.data["errors"], response.data
        assert "This field is required" in str(response.data["errors"]["email"]), (
            response.data
        )
