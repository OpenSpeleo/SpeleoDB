from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from parameterized import parameterized

from speleodb.api.v1.tests.factories import TokenFactory
from speleodb.api.v1.tests.factories import UserFactory


class TestTokenAuth(TestCase):
    """Token authentication"""

    header_prefix = "Token "

    def setUp(self):
        self.csrf_client = APIClient(enforce_csrf_checks=True)
        self.user = UserFactory()
        self.token = TokenFactory(user=self.user)

    def test_token_retrieval_works(self):
        response = self.csrf_client.post(
            reverse("api:v1_users:auth_token"),
            {"email": self.user.email, "password": UserFactory.DEFAULT_PASSWORD},
        )
        assert response.status_code == status.HTTP_200_OK, response.status_code

        target = {
            "success": True,
            "token": self.token.key,
            "url": "http://testserver/api/v1/user/auth-token/",
        }

        for key, val in target.items():
            assert val == response.data[key], response.data

    @parameterized.expand(["POST", "PUT", "PATCH"])
    def test_token_refresh_works(self, method):
        if method not in ["POST", "PUT", "PATCH"]:
            raise ValueError(f"Method `{method}` is not allowed.")

        method_fn = getattr(self.csrf_client, method.lower())
        response = method_fn(
            reverse("api:v1_users:auth_token"),
            {"email": self.user.email, "password": "password"},
        )
        expected_status = (
            status.HTTP_200_OK
            if method.upper() == "POST" else
            status.HTTP_201_CREATED 
        )
        assert response.status_code == expected_status , (
            response.status_code, expected_status, method
        )

        token = response.data.pop("token")
        if method.upper() != "POST":
            assert self.token.key != token, (self.token.key, token)
        else:
            assert self.token.key == token, (self.token.key, token)

        target = {
            "success": True,
            "url": "http://testserver/api/v1/user/auth-token/",
        }

        for key, val in target.items():
            assert val == response.data[key], response.data

    def test_missing_password(self):
        response = self.csrf_client.post(
            reverse("api:v1_users:auth_token"),
            {"email": self.user.email},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.status_code

        assert "token" not in response.data, response.data
        assert not response.data["success"], response.data

        assert "password" in response.data["errors"], response.data
        assert "This field is required" in str(response.data["errors"]["password"]), response.data

    def test_missing_email(self):
        response = self.csrf_client.post(
            reverse("api:v1_users:auth_token"),
            {"password": "password"},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.status_code

        assert "token" not in response.data, response.data
        assert not response.data["success"], response.data

        assert "email" in response.data["errors"], response.data
        assert "This field is required" in str(response.data["errors"]["email"]), response.data
