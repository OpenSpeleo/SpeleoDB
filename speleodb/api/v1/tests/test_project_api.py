from __future__ import annotations

from django.conf import settings
from django.urls import reverse
from parameterized.parameterized import parameterized
from rest_framework import status

from speleodb.api.v1.serializers import ProjectSerializer
from speleodb.api.v1.tests.base_testcase import BaseAPIProjectTestCase
from speleodb.api.v1.tests.base_testcase import BaseAPITestCase
from speleodb.api.v1.tests.utils import is_subset
from speleodb.surveys.models import Mutex
from speleodb.surveys.models import PermissionLevel


class TestProjectInteraction(BaseAPIProjectTestCase):
    @parameterized.expand(
        [
            PermissionLevel.ADMIN,
            PermissionLevel.READ_AND_WRITE,
            PermissionLevel.READ_ONLY,
        ]
    )
    def test_get_user_project(self, level: PermissionLevel) -> None:
        """
        Ensure POSTing json over token auth with correct
        credentials passes and does not require CSRF
        """

        self.set_test_project_permission(level=level)

        auth = self.header_prefix + self.token.key
        response = self.client.get(
            reverse("api:v1:one_project_apiview", kwargs={"id": self.project.id}),
            headers={"authorization": auth},
        )

        assert response.status_code == status.HTTP_200_OK, response.data

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
                    commit_data["committer_email"]
                    == settings.DJANGO_GIT_COMMITTER_EMAIL
                ), commit_data["committer_email"]
                assert (
                    commit_data["committer_name"] == settings.DJANGO_GIT_COMMITTER_NAME
                ), commit_data["committer_name"]
        else:
            # error fetching project from gitlab. TODO
            pass

    @parameterized.expand(
        [
            PermissionLevel.ADMIN,
            PermissionLevel.READ_AND_WRITE,
        ]
    )
    def test_acquire_and_release_user_project(self, level: PermissionLevel) -> None:
        """
        Ensure POSTing json over token auth with correct
        credentials passes and does not require CSRF
        """

        self.set_test_project_permission(level=level)

        # =================== ACQUIRE PROJECT =================== #

        # It is possible to acquire a project multiple time.
        for _ in range(5):
            auth = self.header_prefix + self.token.key
            response = self.client.post(
                reverse("api:v1:acquire_project", kwargs={"id": self.project.id}),
                headers={"authorization": auth},
            )

            assert response.status_code == status.HTTP_200_OK, response.data

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

            assert response.status_code == status.HTTP_200_OK, response.data

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

    @parameterized.expand([PermissionLevel.ADMIN, PermissionLevel.READ_AND_WRITE])
    def test_acquire_and_release_user_project_with_comment(
        self, level: PermissionLevel
    ) -> None:
        """
        Ensure POSTing json over token auth with correct
        credentials passes and does not require CSRF
        """

        self.set_test_project_permission(level=level)

        # =================== ACQUIRE PROJECT =================== #

        auth = self.header_prefix + self.token.key
        response = self.client.post(
            reverse("api:v1:acquire_project", kwargs={"id": self.project.id}),
            headers={"authorization": auth},
        )

        assert response.status_code == status.HTTP_200_OK, response.data

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

        mutex: Mutex | None = self.project.active_mutex
        assert mutex is not None

        test_comment = "hello world"

        auth = self.header_prefix + self.token.key
        response = self.client.post(
            reverse("api:v1:release_project", kwargs={"id": self.project.id}),
            headers={"authorization": auth},
            data={"comment": test_comment},
        )

        assert response.status_code == status.HTTP_200_OK, response.data

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

        assert response.data["data"]["active_mutex"] is None, response.data["data"][
            "active_mutex"
        ]
        assert mutex.closing_comment == test_comment, (mutex, test_comment)
        assert mutex.closing_user == self.user, (mutex, self.user)

    @parameterized.expand(
        [
            PermissionLevel.READ_ONLY,
        ]
    )
    def test_fail_acquire_readonly_project(self, level: PermissionLevel) -> None:
        """
        Ensure POSTing json over token auth with correct
        credentials passes and does not require CSRF
        """

        self.set_test_project_permission(level=level)

        auth = self.header_prefix + self.token.key
        response = self.client.post(
            reverse("api:v1:acquire_project", kwargs={"id": self.project.id}),
            headers={"authorization": auth},
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN, response.data
        assert not response.data["success"], response.data

    @parameterized.expand(
        [
            PermissionLevel.READ_ONLY,
        ]
    )
    def test_fail_release_readonly_project(self, level: PermissionLevel) -> None:
        """
        Ensure POSTing json over token auth with correct
        credentials passes and does not require CSRF
        """

        self.set_test_project_permission(level=level)

        auth = self.header_prefix + self.token.key
        response = self.client.post(
            reverse("api:v1:release_project", kwargs={"id": self.project.id}),
            headers={"authorization": auth},
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN, response.data
        assert not response.data["success"], response.data


class TestProjectCreation(BaseAPITestCase):
    @parameterized.expand([True, False])
    def test_create_project(self, use_lat_long: bool) -> None:
        data = {
            "name": "My Cool Project",
            "description": "A super cool project",
            "country": "US",
        }

        if use_lat_long:
            data.update({"longitude": "100.423897", "latitude": "-100.367573"})

        auth = self.header_prefix + self.token.key
        response = self.client.post(
            reverse("api:v1:project_api"),
            data=data,
            format="json",
            headers={"authorization": auth},
        )

        assert response.status_code == status.HTTP_201_CREATED, response.data

        assert is_subset(data, response.data["data"]), response.data

    @parameterized.expand(["longitude", "latitude"])
    def test_create_project_failure_with_only_one_geo(self, geokey: str) -> None:
        data = {
            "name": "My Cool Project",
            "description": "A super cool project",
            "country": "US",
            geokey: "100.423897",
        }

        auth = self.header_prefix + self.token.key
        response = self.client.post(
            reverse("api:v1:project_api"),
            data=data,
            format="json",
            headers={"authorization": auth},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.data

        assert (
            "`latitude` and `longitude` must be simultaneously specified or empty"
            in response.data["errors"]["non_field_errors"]
        ), response.data

    def test_create_project_failure_with_non_existing_country(self) -> None:
        data = {
            "name": "My Cool Project",
            "description": "A super cool project",
            "country": "YOLO",
        }

        auth = self.header_prefix + self.token.key
        response = self.client.post(
            reverse("api:v1:project_api"),
            data=data,
            format="json",
            headers={"authorization": auth},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.data

        assert '"YOLO" is not a valid choice.' in response.data["errors"]["country"], (
            response.data
        )

    @parameterized.expand(["name", "description", "country"])
    def test_create_project_failure_with_missing_data(
        self, missing_param_key: str
    ) -> None:
        data = {
            "name": "My Cool Project",
            "description": "A super cool project",
            "country": "YOLO",
        }

        del data[missing_param_key]

        auth = self.header_prefix + self.token.key
        response = self.client.post(
            reverse("api:v1:project_api"),
            data=data,
            format="json",
            headers={"authorization": auth},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.data

        assert (
            "This field is required." in response.data["errors"][missing_param_key]
        ), response.data
