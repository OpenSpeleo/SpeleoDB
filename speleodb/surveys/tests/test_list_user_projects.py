import random

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from speleodb.surveys.models import Permission
from speleodb.surveys.tests.factories import PermissionFactory
from speleodb.surveys.tests.factories import TokenFactory
from speleodb.surveys.tests.factories import UserFactory


class TestProjectInteraction(TestCase):
    """Token authentication"""

    header_prefix = "Token "
    PROJECT_COUNT = 10

    def setUp(self):
        self.csrf_client = APIClient(enforce_csrf_checks=True)

        self.user = UserFactory()
        self.token = TokenFactory(user=self.user)

    def test_get_user_projects(self):
        """
        Ensure POSTing json over token auth with correct
        credentials passes and does not require CSRF
        """

        for _ in range(self.PROJECT_COUNT):
            # automatically creates projects associated
            _ = PermissionFactory(
                user=self.user,
                level=random.choice(list(Permission.Level)),
            )

        auth = self.header_prefix + self.token.key
        response = self.csrf_client.get(
            "/api/v1/projects/",
            HTTP_AUTHORIZATION=auth,
        )

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["data"]) == self.PROJECT_COUNT

        attributes = [
            "creation_date",
            "description",
            "fork_from",
            "id",
            "latitude",
            "longitude",
            "modified_date",
            "mutex_dt",
            "mutex_owner",
            "name",
            "permission",
        ]

        for project in response.data["data"]:
            assert all(attr in project for attr in attributes)

        target = {
            "success": True,
            "url": "http://testserver/api/v1/projects/",
        }

        for key, val in target.items():
            assert val == response.data[key]
