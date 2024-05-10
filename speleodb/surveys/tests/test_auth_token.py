from django.test import TestCase
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from speleodb.users.models import User


class TestTokenAuth(TestCase):
    """Token authentication"""

    header_prefix = "Token "

    def setUp(self):
        self.csrf_client = APIClient(enforce_csrf_checks=True)
        self.username = "john"
        self.email = "lennon@thebeatles.com"
        self.password = "password"
        self.user = User.objects.create_user(self.email, self.password)

        self.key = "abcd1234"
        self.token = Token.objects.create(key=self.key, user=self.user)

    def test_token_retrieval_works(self):
        response = self.csrf_client.post(
            "/api/auth-token/",
            {"email": self.email, "password": self.password},
        )
        assert response.status_code == status.HTTP_200_OK

        target = {
            "success": True,
            "token": self.key,
            "url": "http://testserver/api/auth-token/",
        }

        for key, val in target.items():
            assert val == response.data[key]

    def test_token_refresh_works(self):
        response = self.csrf_client.patch(
            "/api/auth-token/",
            {"email": self.email, "password": self.password},
        )
        assert response.status_code == status.HTTP_200_OK

        # Token shall be different.
        assert self.key != response.data.pop("token")

        target = {
            "success": True,
            "url": "http://testserver/api/auth-token/",
        }

        for key, val in target.items():
            assert val == response.data[key]

    def test_missing_password(self):
        response = self.csrf_client.post(
            "/api/auth-token/",
            {"email": self.email},
        )
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        assert "token" not in response.data
        assert not response.data["success"]

        assert "password" in response.data["error"]
        assert "This field is required" in response.data["error"]

    def test_missing_email(self):
        response = self.csrf_client.post(
            "/api/auth-token/",
            {"password": self.password},
        )
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

        assert "token" not in response.data
        assert not response.data["success"]

        assert "email" in response.data["error"]
        assert "This field is required" in response.data["error"]
