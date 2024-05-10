import random

from django.test import TestCase
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from speleodb.surveys.api.v1.serializers import ProjectSerializer
from speleodb.surveys.models import Permission
from speleodb.surveys.models import Project
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

    def test_get_user_projects(self):
        """
        Ensure POSTing json over token auth with correct
        credentials passes and does not require CSRF
        """
        proj_data = {
            "name": "Mayan Blue",
            "description": "A beautiful Cenote - Oh yeahhh cave",
            "longitude": 37.37635035,
            "latitude": -121.91914907,
        }

        for _ in range(10):
            serializer = ProjectSerializer(data=proj_data, context={"user": self.user})
            if serializer.is_valid():
                proj = serializer.save()
                Permission.objects.create(
                    project=proj,
                    user=self.user,
                    level=random.choice(list(Permission.Level)),
                )

        auth = self.header_prefix + self.key
        response = self.csrf_client.get(
            "/api/v1/projects/",
            HTTP_AUTHORIZATION=auth,
        )
        assert response.status_code == status.HTTP_200_OK

        assert len(response.data["data"]) == 10

        target = {
            "success": True,
            "url": "http://testserver/api/v1/projects/",
        }

        for key, val in target.items():
            assert val == response.data[key]
