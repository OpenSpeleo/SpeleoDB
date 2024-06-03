import pytest
from django.test import TestCase
from parameterized import parameterized
from rest_framework import status
from rest_framework.test import APIClient

from speleodb.api.v1.serializers import ProjectSerializer
from speleodb.api.v1.tests.factories import PermissionFactory
from speleodb.api.v1.tests.factories import ProjectFactory
from speleodb.api.v1.tests.factories import TokenFactory
from speleodb.api.v1.tests.factories import UserFactory
from speleodb.surveys.models import Permission


@pytest.mark.parametrize(
    "level",
    [
        Permission.Level.OWNER,
        Permission.Level.READ_AND_WRITE,
        Permission.Level.READ_ONLY,
    ],
)
class TestProjectInteraction(TestCase):
    """Token authentication"""

    header_prefix = "Token "

    def setUp(self):
        self.csrf_client = APIClient(enforce_csrf_checks=True)

        self.user = UserFactory()
        self.token = TokenFactory(user=self.user)
        self.project = ProjectFactory()

    @parameterized.expand(
        [
            Permission.Level.OWNER,
            Permission.Level.READ_AND_WRITE,
            Permission.Level.READ_ONLY,
        ]
    )
    def test_get_user_project(self, level):
        """
        Ensure POSTing json over token auth with correct
        credentials passes and does not require CSRF
        """

        _ = PermissionFactory(user=self.user, project=self.project, level=level)

        auth = self.header_prefix + self.token.key
        response = self.csrf_client.get(
            f"/api/v1/project/{self.project.id}/",
            HTTP_AUTHORIZATION=auth,
        )

        assert response.status_code == status.HTTP_200_OK

        assert ProjectSerializer(data=response.data["data"]["project"]).is_valid()
        proj_data = ProjectSerializer(self.project, context={"user": self.user}).data

        assert proj_data == response.data["data"]["project"]

        if isinstance(response.data["data"]["history"], (tuple, list)):
            commit_keys = [
                "author_email",
                "author_name",
                "authored_date",
                "committed_date",
                "committer_email",
                "committer_name",
                "created_at",
                "extended_trailers",
                "id",
                "message",
                "parent_ids",
                "short_id",
                "title",
                "trailers",
            ]
            for commit_data in response.data["data"]["history"]:
                assert all(key in commit_data for key in commit_keys), commit_data
                assert commit_data["committer_email"] == "contact@speleodb.com"
                assert commit_data["committer_name"] == "SpeleoDB"
        else:
            # error fetching project from gitlab. TODO
            pass

    @parameterized.expand(
        [
            Permission.Level.OWNER,
            Permission.Level.READ_AND_WRITE,
        ]
    )
    def test_acquire_and_release_user_project(self, level):
        """
        Ensure POSTing json over token auth with correct
        credentials passes and does not require CSRF
        """

        _ = PermissionFactory(user=self.user, project=self.project, level=level)

        # =================== ACQUIRE PROJECT =================== #

        # It is possible to acquire a project multiple time.
        for _ in range(5):
            auth = self.header_prefix + self.token.key
            response = self.csrf_client.post(
                f"/api/v1/project/{self.project.id}/acquire/",
                HTTP_AUTHORIZATION=auth,
            )

            assert response.status_code == status.HTTP_200_OK

            # refresh mutex data
            self.project.refresh_from_db()

            assert ProjectSerializer(data=response.data["data"]).is_valid()
            proj_data = ProjectSerializer(
                self.project, context={"user": self.user}
            ).data

            assert proj_data == response.data["data"]
            assert response.data["data"]["mutex_owner"] == self.user.email

        # =================== RELEASE PROJECT =================== #

        # It is possible to release a project multiple time.
        for _ in range(5):
            auth = self.header_prefix + self.token.key
            response = self.csrf_client.post(
                f"/api/v1/project/{self.project.id}/release/",
                HTTP_AUTHORIZATION=auth,
            )

            assert response.status_code == status.HTTP_200_OK

            # refresh mutex data
            self.project.refresh_from_db()

            assert ProjectSerializer(data=response.data["data"]).is_valid()
            proj_data = ProjectSerializer(
                self.project, context={"user": self.user}
            ).data

            assert proj_data == response.data["data"]
            assert response.data["data"]["mutex_owner"] is None

    def test_fail_acquire_readonly_project(self):
        """
        Ensure POSTing json over token auth with correct
        credentials passes and does not require CSRF
        """

        _ = PermissionFactory(
            user=self.user, project=self.project, level=Permission.Level.READ_ONLY
        )

        auth = self.header_prefix + self.token.key
        response = self.csrf_client.post(
            f"/api/v1/project/{self.project.id}/acquire/",
            HTTP_AUTHORIZATION=auth,
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert not response.data["success"]

    def test_fail_release_readonly_project(self):
        _ = PermissionFactory(
            user=self.user, project=self.project, level=Permission.Level.READ_ONLY
        )

        auth = self.header_prefix + self.token.key
        response = self.csrf_client.post(
            f"/api/v1/project/{self.project.id}/release/",
            HTTP_AUTHORIZATION=auth,
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert not response.data["success"]
