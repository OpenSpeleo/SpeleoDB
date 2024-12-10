import random

from django.test import TestCase
from django.urls import reverse
from parameterized import parameterized
from rest_framework import status
from rest_framework.test import APIClient

from speleodb.api.v1.serializers import ProjectSerializer
from speleodb.api.v1.tests.factories import ProjectFactory
from speleodb.api.v1.tests.factories import SurveyTeamFactory
from speleodb.api.v1.tests.factories import TeamPermissionFactory
from speleodb.api.v1.tests.factories import TokenFactory
from speleodb.api.v1.tests.factories import UserFactory
from speleodb.api.v1.tests.factories import UserPermissionFactory
from speleodb.surveys.models import TeamPermission
from speleodb.surveys.models import UserPermission
from speleodb.users.models import SurveyTeamMembership

AnyPermissionLevel = UserPermission.Level | TeamPermission.Level


class TestProjectInteraction(TestCase):
    """Token authentication"""

    header_prefix = "Token "

    def setUp(self):
        self.client = APIClient(enforce_csrf_checks=False)

        self.user = UserFactory()
        self.token = TokenFactory(user=self.user)
        self.project = ProjectFactory()

    def set_test_permission(self, level: AnyPermissionLevel):
        if isinstance(level, UserPermission.Level):
            _ = UserPermissionFactory(
                target=self.user, level=level, project=self.project
            )

        elif isinstance(level, TeamPermission.Level):
            # Create a team for the user - assign the user to the team
            team = SurveyTeamFactory()
            _ = SurveyTeamMembership.objects.create(
                user=self.user,
                team=team,
                role=random.choice(SurveyTeamMembership.Role.values),
            )

            # Give the newly created permission to the project
            _ = TeamPermissionFactory(
                target=team,
                level=level,
                project=self.project,
            )

        else:
            raise TypeError(f"Received unexpected level type: `{type(level)}`")

    @parameterized.expand(
        [
            UserPermission.Level.ADMIN,
            UserPermission.Level.READ_AND_WRITE,
            UserPermission.Level.READ_ONLY,
            TeamPermission.Level.READ_AND_WRITE,
            TeamPermission.Level.READ_ONLY,
        ]
    )
    def test_get_user_project(self, level: AnyPermissionLevel):
        """
        Ensure POSTing json over token auth with correct
        credentials passes and does not require CSRF
        """

        self.set_test_permission(level=level)

        auth = self.header_prefix + self.token.key
        response = self.client.get(
            reverse("api:v1:one_project_apiview", kwargs={"id": self.project.id}),
            headers={"authorization": auth},
        )

        assert response.status_code == status.HTTP_200_OK, response.status_code

        # Verify data can be de-serialized
        serializer = ProjectSerializer(data=response.data["data"]["project"])
        assert serializer.is_valid(), (serializer.errors, response.data)

        serializer = ProjectSerializer(self.project, context={"user": self.user})

        assert serializer.data == response.data["data"]["project"], {
            "reserialized": serializer.data,
            "response_data": response.data["data"]["project"],
        }

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
                assert (
                    commit_data["committer_email"] == "contact@speleodb.com"
                ), commit_data["committer_email"]
                assert commit_data["committer_name"] == "SpeleoDB", commit_data[
                    "committer_name"
                ]
        else:
            # error fetching project from gitlab. TODO
            pass

    @parameterized.expand(
        [
            UserPermission.Level.ADMIN,
            UserPermission.Level.READ_AND_WRITE,
            TeamPermission.Level.READ_AND_WRITE,
        ]
    )
    def test_acquire_and_release_user_project(self, level: AnyPermissionLevel):
        """
        Ensure POSTing json over token auth with correct
        credentials passes and does not require CSRF
        """

        self.set_test_permission(level=level)

        # =================== ACQUIRE PROJECT =================== #

        # It is possible to acquire a project multiple time.
        for _ in range(5):
            auth = self.header_prefix + self.token.key
            response = self.client.post(
                reverse("api:v1:acquire_project", kwargs={"id": self.project.id}),
                headers={"authorization": auth},
            )

            assert response.status_code == status.HTTP_200_OK, response.status_code

            # refresh mutex data
            self.project.refresh_from_db()

            # Verify data can be de-serialized
            serializer = ProjectSerializer(data=response.data["data"])
            assert serializer.is_valid(), (serializer.errors, response.data)

            project_data = ProjectSerializer(
                self.project, context={"user": self.user}
            ).data

            assert project_data == response.data["data"], {
                "reserialized": project_data,
                "response_data": response.data["data"],
            }
            assert response.data["data"]["active_mutex"]["user"] == self.user.email, (
                response.data,
                self.user.email,
            )

        # =================== RELEASE PROJECT =================== #

        # It is possible to release a project multiple time.
        for _ in range(5):
            auth = self.header_prefix + self.token.key
            response = self.client.post(
                reverse("api:v1:release_project", kwargs={"id": self.project.id}),
                headers={"authorization": auth},
            )

            assert response.status_code == status.HTTP_200_OK, response.status_code

            # refresh mutex data
            self.project.refresh_from_db()

            # Verify data can be de-serialized
            serializer = ProjectSerializer(data=response.data["data"])
            assert serializer.is_valid(), (serializer.errors, response.data)

            project_data = ProjectSerializer(
                self.project, context={"user": self.user}
            ).data

            assert project_data == response.data["data"], {
                "reserialized": project_data,
                "response_data": response.data["data"],
            }
            assert response.data["data"]["active_mutex"] is None, response.data

    @parameterized.expand(
        [
            UserPermission.Level.ADMIN,
            UserPermission.Level.READ_AND_WRITE,
            TeamPermission.Level.READ_AND_WRITE,
        ]
    )
    def test_acquire_and_release_user_project_with_comment(
        self, level: AnyPermissionLevel
    ):
        """
        Ensure POSTing json over token auth with correct
        credentials passes and does not require CSRF
        """

        self.set_test_permission(level=level)

        # =================== ACQUIRE PROJECT =================== #

        auth = self.header_prefix + self.token.key
        response = self.client.post(
            reverse("api:v1:acquire_project", kwargs={"id": self.project.id}),
            headers={"authorization": auth},
        )

        assert response.status_code == status.HTTP_200_OK, response.status_code

        # refresh mutex data
        self.project.refresh_from_db()

        # Verify data can be de-serialized
        serializer = ProjectSerializer(data=response.data["data"])
        assert serializer.is_valid(), (serializer.errors, response.data)

        project_data = ProjectSerializer(self.project, context={"user": self.user}).data

        assert project_data == response.data["data"], {
            "reserialized": project_data,
            "response_data": response.data["data"],
        }
        assert response.data["data"]["active_mutex"]["user"] == self.user.email, (
            response.data,
            self.user.email,
        )

        # =================== RELEASE PROJECT =================== #

        mutex = self.project.active_mutex

        test_comment = "hello world"

        auth = self.header_prefix + self.token.key
        response = self.client.post(
            reverse("api:v1:release_project", kwargs={"id": self.project.id}),
            headers={"authorization": auth},
            data={"comment": test_comment},
        )

        assert response.status_code == status.HTTP_200_OK, response.status_code

        # refresh mutex data
        mutex.refresh_from_db()
        self.project.refresh_from_db()

        # Verify data can be de-serialized
        serializer = ProjectSerializer(data=response.data["data"])
        assert serializer.is_valid(), (serializer.errors, response.data)

        project_data = ProjectSerializer(self.project, context={"user": self.user}).data

        assert project_data == response.data["data"], {
            "reserialized": project_data,
            "response_data": response.data["data"],
        }
        assert response.data["data"]["active_mutex"] is None, response.data
        assert mutex.closing_comment == test_comment, (mutex, test_comment)
        assert mutex.closing_user == self.user, (mutex, self.user)

    @parameterized.expand(
        [
            UserPermission.Level.READ_ONLY,
            TeamPermission.Level.READ_ONLY,
        ]
    )
    def test_fail_acquire_readonly_project(self, level: AnyPermissionLevel):
        """
        Ensure POSTing json over token auth with correct
        credentials passes and does not require CSRF
        """

        self.set_test_permission(level=level)

        auth = self.header_prefix + self.token.key
        response = self.client.post(
            reverse("api:v1:acquire_project", kwargs={"id": self.project.id}),
            headers={"authorization": auth},
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN, response.status_code
        assert not response.data["success"], response.data

    @parameterized.expand(
        [
            UserPermission.Level.READ_ONLY,
            TeamPermission.Level.READ_ONLY,
        ]
    )
    def test_fail_release_readonly_project(self, level: AnyPermissionLevel):
        """
        Ensure POSTing json over token auth with correct
        credentials passes and does not require CSRF
        """

        self.set_test_permission(level=level)

        auth = self.header_prefix + self.token.key
        response = self.client.post(
            reverse("api:v1:release_project", kwargs={"id": self.project.id}),
            headers={"authorization": auth},
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN, response.status_code
        assert not response.data["success"], response.data
