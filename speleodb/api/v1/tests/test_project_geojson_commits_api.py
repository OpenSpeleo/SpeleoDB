# -*- coding: utf-8 -*-

from __future__ import annotations

import uuid
from hashlib import sha1

import orjson
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone
from parameterized.parameterized import parameterized_class
from rest_framework import status

from speleodb.api.v1.tests.base_testcase import BaseAPIProjectTestCase
from speleodb.api.v1.tests.base_testcase import PermissionType
from speleodb.api.v1.tests.factories import TokenFactory
from speleodb.common.enums import PermissionLevel
from speleodb.gis.models import ProjectGeoJSON
from speleodb.utils.test_utils import named_product


def temp_geojson_file() -> SimpleUploadedFile:
    """Fixture to create a temporary GeoJSON file."""
    return SimpleUploadedFile(
        "test.geojson",
        orjson.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "geometry": {
                            "type": "Point",
                            "coordinates": [-87.501234, 20.196710],
                        },
                        "properties": {"name": "Test Cave Entrance"},
                    }
                ],
            }
        ),
        content_type="application/geo+json",
    )


def sha1_hash() -> str:
    """Generate a random SHA1 hash for testing."""
    import random
    import string

    rand_str = "".join([random.choice(string.ascii_lowercase) for _ in range(32)])
    return sha1(rand_str.encode("utf-8"), usedforsecurity=False).hexdigest()


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
        ],
        permission_type=[PermissionType.USER, PermissionType.TEAM],
    ),
)
class TestProjectGeoJsonCommitsApiView(BaseAPIProjectTestCase):
    """Test suite for the ProjectGeoJsonCommitsApiView endpoint."""

    level: PermissionLevel
    permission_type: PermissionType

    def setUp(self) -> None:
        super().setUp()

        self.set_test_project_permission(
            level=self.level,
            permission_type=self.permission_type,
        )

    def test_list_geojson_commits_success(self) -> None:
        """Test successfully listing GeoJSON commits."""
        # Create multiple GeoJSON entries
        commits = []
        for i in range(3):
            commit_sha = sha1_hash()
            geojson = ProjectGeoJSON.objects.create(
                project=self.project,
                commit_sha=commit_sha,
                commit_date=timezone.now(),
                commit_author_name=f"Author {i}",
                commit_author_email=f"author{i}@example.com",
                commit_message=f"Commit message {i}",
                file=temp_geojson_file(),
            )
            commits.append(geojson)

        response = self.client.get(
            reverse(
                "api:v1:project-geojson-commits",
                kwargs={"id": self.project.id},
            ),
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_200_OK
        response_data = orjson.loads(response.content)
        assert response_data["success"] is True
        assert "data" in response_data
        assert isinstance(response_data["data"], list)
        assert len(response_data["data"]) == 3

        # Verify each commit has required fields
        for commit in response_data["data"]:
            assert "commit_sha" in commit
            assert "commit_date" in commit
            assert "commit_author_name" in commit
            assert "commit_author_email" in commit
            assert "commit_message" in commit
            assert len(commit["commit_sha"]) == 40  # Full SHA
            # Should NOT have signed URL
            assert "url" not in commit

    def test_commits_ordered_by_date_descending(self) -> None:
        """Test that commits are returned in descending date order."""
        import time

        # Create commits with different dates
        old_date = timezone.now() - timezone.timedelta(days=2)
        mid_date = timezone.now() - timezone.timedelta(days=1)
        new_date = timezone.now()

        sha_old = sha1_hash()
        sha_mid = sha1_hash()
        sha_new = sha1_hash()

        ProjectGeoJSON.objects.create(
            project=self.project,
            commit_sha=sha_mid,
            commit_date=mid_date,
            commit_author_name="Author",
            commit_author_email="author@example.com",
            commit_message="Middle commit",
            file=temp_geojson_file(),
        )

        time.sleep(0.1)  # Ensure different creation times

        ProjectGeoJSON.objects.create(
            project=self.project,
            commit_sha=sha_new,
            commit_date=new_date,
            commit_author_name="Author",
            commit_author_email="author@example.com",
            commit_message="Newest commit",
            file=temp_geojson_file(),
        )

        time.sleep(0.1)

        ProjectGeoJSON.objects.create(
            project=self.project,
            commit_sha=sha_old,
            commit_date=old_date,
            commit_author_name="Author",
            commit_author_email="author@example.com",
            commit_message="Oldest commit",
            file=temp_geojson_file(),
        )

        response = self.client.get(
            reverse(
                "api:v1:project-geojson-commits",
                kwargs={"id": self.project.id},
            ),
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()["data"]

        # Should be ordered newest first
        assert data[0]["commit_sha"] == sha_new
        assert data[1]["commit_sha"] == sha_mid
        assert data[2]["commit_sha"] == sha_old

    def test_empty_list_when_no_geojson(self) -> None:
        """Test that endpoint returns empty list when project has no GeoJSON."""
        response = self.client.get(
            reverse(
                "api:v1:project-geojson-commits",
                kwargs={"id": self.project.id},
            ),
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert isinstance(data["data"], list)
        assert len(data["data"]) == 0

    def test_returns_all_commits_no_limit(self) -> None:
        """Test that endpoint returns all commits (no limit like geojson endpoint)."""
        # Create many GeoJSON entries
        for i in range(25):
            commit_sha = sha1_hash()
            ProjectGeoJSON.objects.create(
                project=self.project,
                commit_sha=commit_sha,
                commit_date=timezone.now(),
                commit_author_name=f"Author {i}",
                commit_author_email=f"author{i}@example.com",
                commit_message=f"Commit {i}",
                file=temp_geojson_file(),
            )

        response = self.client.get(
            reverse(
                "api:v1:project-geojson-commits",
                kwargs={"id": self.project.id},
            ),
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        # Should return all 25 commits (no limit)
        assert len(data["data"]) == 25


class TestProjectGeoJsonCommitsPermissions(BaseAPIProjectTestCase):
    """Test permission requirements for ProjectGeoJsonCommitsApiView."""

    def setUp(self) -> None:
        super().setUp()

    def test_web_viewer_access_denied(self) -> None:
        """Test that WEB_VIEWER users cannot access commits endpoint."""
        # Set user as WEB_VIEWER
        self.set_test_project_permission(
            level=PermissionLevel.WEB_VIEWER,
            permission_type=PermissionType.USER,
        )

        # Create a GeoJSON
        commit_sha = sha1_hash()
        ProjectGeoJSON.objects.create(
            project=self.project,
            commit_sha=commit_sha,
            commit_date=timezone.now(),
            commit_author_name="Author",
            commit_author_email="author@example.com",
            commit_message="Test commit",
            file=temp_geojson_file(),
        )

        response = self.client.get(
            reverse(
                "api:v1:project-geojson-commits",
                kwargs={"id": self.project.id},
            ),
            headers={"authorization": self.auth},
        )

        # WEB_VIEWER should NOT have access
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_read_only_access_allowed(self) -> None:
        """Test that READ_ONLY users can access commits endpoint."""
        # Set user as READ_ONLY
        self.set_test_project_permission(
            level=PermissionLevel.READ_ONLY,
            permission_type=PermissionType.USER,
        )

        # Create a GeoJSON
        commit_sha = sha1_hash()
        ProjectGeoJSON.objects.create(
            project=self.project,
            commit_sha=commit_sha,
            commit_date=timezone.now(),
            commit_author_name="Author",
            commit_author_email="author@example.com",
            commit_message="Test commit",
            file=temp_geojson_file(),
        )

        response = self.client.get(
            reverse(
                "api:v1:project-geojson-commits",
                kwargs={"id": self.project.id},
            ),
            headers={"authorization": self.auth},
        )

        # READ_ONLY should have access
        assert response.status_code == status.HTTP_200_OK

    def test_unauthenticated_access_denied(self) -> None:
        """Test that unauthenticated users cannot access commits."""
        response = self.client.get(
            reverse(
                "api:v1:project-geojson-commits",
                kwargs={"id": self.project.id},
            ),
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_no_permission_access_denied(self) -> None:
        """Test that users without project permissions cannot access."""
        # Create a different user with no permissions
        token = TokenFactory.create()
        auth = self.header_prefix + token.key

        response = self.client.get(
            reverse(
                "api:v1:project-geojson-commits",
                kwargs={"id": self.project.id},
            ),
            headers={"authorization": auth},
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_nonexistent_project_returns_404(self) -> None:
        """Test that requesting commits for non-existent project returns 404."""
        fake_id = uuid.uuid4()

        response = self.client.get(
            reverse(
                "api:v1:project-geojson-commits",
                kwargs={"id": fake_id},
            ),
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

