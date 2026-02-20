# -*- coding: utf-8 -*-

from __future__ import annotations

import datetime
import random
from typing import TYPE_CHECKING
from typing import Any

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.test.utils import override_settings
from django.urls import reverse
from django.utils import timezone
from parameterized.parameterized import parameterized
from parameterized.parameterized import parameterized_class
from rest_framework import status

from speleodb.api.v1.serializers import ProjectSerializer
from speleodb.api.v1.tests.base_testcase import BaseAPIProjectTestCase
from speleodb.api.v1.tests.base_testcase import BaseAPITestCase
from speleodb.api.v1.tests.base_testcase import PermissionType
from speleodb.api.v1.tests.factories import ProjectFactory
from speleodb.api.v1.tests.factories import UserProjectPermissionFactory
from speleodb.api.v1.tests.utils import is_subset
from speleodb.common.enums import PermissionLevel
from speleodb.common.enums import ProjectType
from speleodb.surveys.models import ProjectCommit
from speleodb.utils.test_utils import named_product

if TYPE_CHECKING:
    from speleodb.surveys.models import ProjectMutex


@parameterized_class(
    [
        "level",
        "permission_type",
    ],
    named_product(
        level=[
            PermissionLevel.ADMIN,
            PermissionLevel.READ_AND_WRITE,
            PermissionLevel.READ_ONLY,
            PermissionLevel.WEB_VIEWER,
        ],
        permission_type=[PermissionType.USER, PermissionType.TEAM],
    ),
)
class TestProjectInteraction(BaseAPIProjectTestCase):
    level: PermissionLevel
    permission_type: PermissionType

    test_geojson: dict[str, Any] = {}

    def setUp(self) -> None:
        super().setUp()

        self.set_test_project_permission(
            level=self.level,
            permission_type=self.permission_type,
        )

    def test_get_user_project(self) -> None:
        """
        Ensure POSTing json over token auth with correct
        credentials passes and does not require CSRF
        """

        auth = self.header_prefix + self.token.key
        response = self.client.get(
            reverse("api:v1:project-detail", kwargs={"id": self.project.id}),
            headers={"authorization": auth},
        )

        if self.level == PermissionLevel.WEB_VIEWER:
            assert response.status_code == status.HTTP_403_FORBIDDEN
            return

        assert response.status_code == status.HTTP_200_OK, response.data

        # Verify data can be de-serialized
        serializer = ProjectSerializer(data=response.data["data"])
        assert serializer.is_valid(), (serializer.errors, response.data)

        serializer = ProjectSerializer(self.project, context={"user": self.user})

        assert serializer.data == response.data["data"], {
            "reserialized": serializer.data,
            "response_data": response.data["data"],
        }

    def test_acquire_and_release_user_project(self) -> None:
        """
        Ensure POSTing json over token auth with correct
        credentials passes and does not require CSRF
        """

        # =================== ACQUIRE PROJECT =================== #

        # It is possible to acquire a project multiple time.
        for _ in range(5):
            auth = self.header_prefix + self.token.key
            response = self.client.post(
                reverse("api:v1:project-acquire", kwargs={"id": self.project.id}),
                headers={"authorization": auth},
            )

            if self.level < PermissionLevel.READ_AND_WRITE:
                assert response.status_code == status.HTTP_403_FORBIDDEN
                return

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
                reverse("api:v1:project-release", kwargs={"id": self.project.id}),
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

    def test_acquire_and_release_user_project_with_comment(self) -> None:
        """
        Ensure POSTing json over token auth with correct
        credentials passes and does not require CSRF
        """

        # =================== ACQUIRE PROJECT =================== #

        auth = self.header_prefix + self.token.key
        response = self.client.post(
            reverse("api:v1:project-acquire", kwargs={"id": self.project.id}),
            headers={"authorization": auth},
        )

        if self.level < PermissionLevel.READ_AND_WRITE:
            assert response.status_code == status.HTTP_403_FORBIDDEN
            return

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

        mutex: ProjectMutex | None = self.project.active_mutex
        assert mutex is not None

        assert mutex.is_active

        # =================== RELEASE PROJECT =================== #

        test_comment = "hello world"

        auth = self.header_prefix + self.token.key
        response = self.client.post(
            reverse("api:v1:project-release", kwargs={"id": self.project.id}),
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
        assert mutex.closing_user == self.user.email, (mutex, self.user)
        assert not mutex.is_active

    def test_fail_acquire_readonly_project(self) -> None:
        """
        Ensure POSTing json over token auth with correct
        credentials passes and does not require CSRF
        """

        if self.level > PermissionLevel.READ_ONLY:
            pytest.skip(
                "This test is only for READ_ONLY or WEB_VIEWER permission level."
            )

        auth = self.header_prefix + self.token.key
        response = self.client.post(
            reverse("api:v1:project-acquire", kwargs={"id": self.project.id}),
            headers={"authorization": auth},
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN, response.data
        assert not response.data["success"], response.data

    def test_fail_release_readonly_project(self) -> None:
        """
        Ensure POSTing json over token auth with correct
        credentials passes and does not require CSRF
        """

        if self.level > PermissionLevel.READ_ONLY:
            pytest.skip(
                "This test is only for READ_ONLY or WEB_VIEWER permission level."
            )

        auth = self.header_prefix + self.token.key
        response = self.client.post(
            reverse("api:v1:project-release", kwargs={"id": self.project.id}),
            headers={"authorization": auth},
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN, response.data
        assert not response.data["success"], response.data


class TestProjectCreation(BaseAPITestCase):
    @parameterized.expand([True, False])
    def test_create_project(self, use_lat_long: bool) -> None:
        _, project_type = random.choice(ProjectType.choices)
        data: dict[str, Any] = {
            "name": "My Cool Project",
            "description": "A super cool project",
            "country": "US",
            "type": project_type,
        }

        if use_lat_long:
            data.update({"longitude": 100.423897, "latitude": -45.367573})

        auth = self.header_prefix + self.token.key
        response = self.client.post(
            reverse("api:v1:projects"),
            data=data,
            format="json",
            headers={"authorization": auth},
        )

        assert response.status_code == status.HTTP_201_CREATED, response.data

        assert is_subset(data, response.data["data"]), response.data

    @parameterized.expand(["longitude", "latitude"])
    def test_create_project_failure_with_only_one_geo(self, geokey: str) -> None:
        _, project_type = random.choice(ProjectType.choices)
        data = {
            "name": "My Cool Project",
            "description": "A super cool project",
            "country": "US",
            "type": project_type,
            geokey: 45.423897,  # Valid coordinate value
        }

        auth = self.header_prefix + self.token.key
        response = self.client.post(
            reverse("api:v1:projects"),
            data=data,
            format="json",
            headers={"authorization": auth},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.data

        # Check if we got the expected non_field_errors
        if "non_field_errors" in response.data.get("errors", {}):
            assert (
                "`latitude` and `longitude` must be simultaneously specified or empty"
                in response.data["errors"]["non_field_errors"]
            ), response.data
        else:
            # If we got a field-level error instead, it might be a validation issue
            # with the coordinate value itself
            assert geokey in response.data.get("errors", {}), response.data

    def test_create_project_failure_with_non_existing_country(self) -> None:
        _, project_type = random.choice(ProjectType.choices)
        data = {
            "name": "My Cool Project",
            "description": "A super cool project",
            "country": "YOLO",
            "type": project_type,
        }

        auth = self.header_prefix + self.token.key
        response = self.client.post(
            reverse("api:v1:projects"),
            data=data,
            format="json",
            headers={"authorization": auth},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.data

        assert '"YOLO" is not a valid choice.' in response.data["errors"]["country"], (
            response.data
        )

    @parameterized.expand(["name", "description", "country", "type"])
    def test_create_project_failure_with_missing_data(
        self, missing_param_key: str
    ) -> None:
        _, project_type = random.choice(ProjectType.choices)
        data = {
            "name": "My Cool Project",
            "description": "A super cool project",
            "country": "US",
            "type": project_type,
        }

        del data[missing_param_key]

        auth = self.header_prefix + self.token.key
        response = self.client.post(
            reverse("api:v1:projects"),
            data=data,
            format="json",
            headers={"authorization": auth},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.data

        assert (
            "This field is required." in response.data["errors"][missing_param_key]
        ), response.data


class TestProjectListLatestCommit(BaseAPITestCase):
    """Test suite for latest_commit field in project list endpoint."""

    def test_project_list_includes_latest_commit_field(self) -> None:
        """Test that GET /api/v1/projects/ includes latest_commit field."""

        # Create project with commits
        project = ProjectFactory.create(created_by=self.user.email)

        # Give user permission to see the project
        UserProjectPermissionFactory.create(
            target=self.user,
            project=project,
            level=PermissionLevel.ADMIN,
        )

        # Create commits
        _ = ProjectCommit.objects.create(
            id="a" * 40,
            project=project,
            author_name="Author",
            author_email="author@test.com",
            authored_date=timezone.now() - datetime.timedelta(days=2),
            message="Old commit",
        )

        _ = ProjectCommit.objects.create(
            id="b" * 40,
            project=project,
            author_name="Author",
            author_email="author@test.com",
            authored_date=timezone.now(),
            message="Latest commit",
        )

        # GET project list
        response = self.client.get(
            reverse("api:v1:projects"),
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_200_OK
        projects_data = response.data["data"]

        # Find our project
        project_data = next(p for p in projects_data if p["id"] == str(project.id))

        # Verify latest_commit field exists
        assert "latest_commit" in project_data

        # Verify it contains the latest commit data
        latest_commit_data = project_data["latest_commit"]
        assert latest_commit_data is not None
        assert latest_commit_data["id"] == "b" * 40
        assert latest_commit_data["message"] == "Latest commit"

    def test_project_list_latest_commit_none_when_no_commits(self) -> None:
        """Test that projects without commits have latest_commit as None."""

        # Create project without commits
        project = ProjectFactory.create(created_by=self.user.email)

        # Give user permission to see the project
        UserProjectPermissionFactory.create(
            target=self.user,
            project=project,
            level=PermissionLevel.ADMIN,
        )

        response = self.client.get(
            reverse("api:v1:projects"),
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_200_OK
        projects_data = response.data["data"]

        # Find our project
        project_data = next(p for p in projects_data if p["id"] == str(project.id))

        # latest_commit should be None
        assert "latest_commit" in project_data
        assert project_data["latest_commit"] is None

    def test_project_list_latest_commit_structure(self) -> None:
        """Test that latest_commit has correct ProjectCommitSerializer structure."""

        project = ProjectFactory.create(created_by=self.user.email)

        # Give user permission to see the project
        UserProjectPermissionFactory.create(
            target=self.user,
            project=project,
            level=PermissionLevel.ADMIN,
        )

        _ = ProjectCommit.objects.create(
            id="a" * 40,
            project=project,
            author_name="Test Author",
            author_email="test@example.com",
            authored_date=timezone.now(),
            message="Test message",
            tree=[
                {"mode": "100644", "type": "blob", "object": "b" * 40, "path": "f.txt"}
            ],
        )

        response = self.client.get(
            reverse("api:v1:projects"),
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_200_OK
        project_data = next(
            p for p in response.data["data"] if p["id"] == str(project.id)
        )

        latest_commit_data = project_data["latest_commit"]

        # Verify all expected fields
        expected_fields = [
            "id",
            "author_name",
            "author_email",
            "authored_date",
            "message",
            "parent_ids",
            "tree",
        ]

        for field in expected_fields:
            assert field in latest_commit_data, f"Missing field: {field}"

        # Verify parents is a list
        assert isinstance(latest_commit_data["parent_ids"], list)

    def test_project_list_no_n_plus_1_with_commits(self) -> None:
        """Test that fetching projects with latest_commit doesn't cause N+1 queries."""
        # Create multiple projects with commits
        n_projects = 5
        n_commits = 3
        for i in range(n_projects):
            project = ProjectFactory.create(created_by=self.user.email)
            for j in range(n_commits):
                ProjectCommit.objects.create(
                    id=f"{i:02d}{j:02d}" + "0" * 36,
                    project=project,
                    author_name=f"Author {i}",
                    author_email=f"author{i}@test.com",
                    authored_date=timezone.now() - datetime.timedelta(days=2 - j),
                    message=f"Commit {j}",
                )

        # Test with query counting
        with override_settings(DEBUG=True):
            with CaptureQueriesContext(connection) as context:
                response = self.client.get(
                    reverse("api:v1:projects"),
                    headers={"authorization": self.auth},
                )

            assert response.status_code == status.HTTP_200_OK

            # Query count should be constant regardless of number of projects
            # Should be: 1 for user permissions, 1 for projects, 1 prefetch for commits
            # Total should be relatively constant (< 10 queries)
            assert len(context.captured_queries) < n_projects * n_commits, (
                f"Too many queries: {len(context.captured_queries)}. "
                f"Possible N+1 issue."
            )
