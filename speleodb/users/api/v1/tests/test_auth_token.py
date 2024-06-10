from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

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
        assert response.status_code == status.HTTP_200_OK

        target = {
            "success": True,
            "token": self.token.key,
            "url": "http://testserver/api/v1/user/auth-token/",
        }

        for key, val in target.items():
            assert val == response.data[key]

    def test_token_refresh_works(self):
        response = self.csrf_client.patch(
            reverse("api:v1_users:auth_token"),
            {"email": self.user.email, "password": "password"},
        )
        assert response.status_code == status.HTTP_200_OK

        # Token shall be different.
        assert self.token.key != response.data.pop("token")

        target = {
            "success": True,
            "url": "http://testserver/api/v1/user/auth-token/",
        }

        for key, val in target.items():
            assert val == response.data[key]

    def test_missing_password(self):
        response = self.csrf_client.post(
            reverse("api:v1_users:auth_token"),
            {"email": self.user.email},
        )
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        assert "token" not in response.data
        assert not response.data["success"]

        assert "password" in response.data["error"]
        assert "This field is required" in response.data["error"]

    def test_missing_email(self):
        response = self.csrf_client.post(
            reverse("api:v1_users:auth_token"),
            {"password": "password"},
        )
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        assert "token" not in response.data
        assert not response.data["success"]

        assert "email" in response.data["error"]
        assert "This field is required" in response.data["error"]
