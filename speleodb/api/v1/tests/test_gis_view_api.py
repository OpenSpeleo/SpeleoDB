# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

import orjson
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.authtoken.models import Token

from speleodb.api.v1.serializers.gis_view import GISViewDataSerializer
from speleodb.api.v1.serializers.gis_view import PublicGISProjectViewSerializer
from speleodb.api.v1.serializers.gis_view import PublicGISViewSerializer
from speleodb.api.v1.tests.base_testcase import BaseAPITestCase
from speleodb.api.v1.tests.factories import ProjectFactory
from speleodb.api.v1.tests.factories import UserProjectPermissionFactory
from speleodb.common.enums import PermissionLevel
from speleodb.gis.models import GISProjectView
from speleodb.gis.models import GISView
from speleodb.gis.models import ProjectGeoJSON
from speleodb.surveys.models import Project
from speleodb.surveys.models import ProjectCommit

if TYPE_CHECKING:
    from datetime import datetime


def temp_geojson_file() -> SimpleUploadedFile:
    """Create a temporary GeoJSON file."""
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
                            "coordinates": [-87.5, 20.2],
                        },
                        "properties": {"name": "Test"},
                    }
                ],
            }
        ),
        content_type="application/geo+json",
    )


def create_project_geojson(
    project: Project,
    commit_sha: str,
    commit_date: datetime,
    author_name: str,
    author_email: str,
    message: str,
    file: SimpleUploadedFile,
) -> ProjectGeoJSON:
    """Helper to create a ProjectGeoJSON with its required ProjectCommit."""
    commit = ProjectCommit.objects.create(
        id=commit_sha,
        project=project,
        author_name=author_name,
        author_email=author_email,
        authored_date=commit_date,
        message=message,
    )
    return ProjectGeoJSON.objects.create(
        commit=commit,
        project=project,
        file=file,
    )


@pytest.mark.django_db
class TestGISViewDataSerializer(BaseAPITestCase):
    """Test GISViewDataSerializer."""

    def test_serializer_structure(self) -> None:
        """Test that serializer produces correct structure."""

        gis_view = GISView.objects.create(
            name="Test View",
            description="Test description",
            allow_precise_zoom=True,
            owner=self.user,
        )

        serializer = GISViewDataSerializer(gis_view, context={"expires_in": 3600})
        data = serializer.data

        assert "view_id" in data
        assert "view_name" in data
        assert "description" in data
        assert "allow_precise_zoom" in data
        assert "geojson_files" in data
        assert data["view_name"] == "Test View"
        assert data["description"] == "Test description"
        assert data["allow_precise_zoom"] is True
        assert isinstance(data["geojson_files"], list)

    def test_serializer_with_geojson_files(self) -> None:
        """Test serializer includes GeoJSON file data."""

        project = ProjectFactory.create()
        gis_view = GISView.objects.create(
            name="Test View",
            owner=self.user,
            allow_precise_zoom=False,
        )

        commit_sha = "a" * 40
        create_project_geojson(
            project=project,
            commit_sha=commit_sha,
            commit_date=timezone.now(),
            author_name="Author",
            author_email="author@example.com",
            message="Test commit",
            file=temp_geojson_file(),
        )

        GISProjectView.objects.create(
            gis_view=gis_view,
            project=project,
            commit_sha=commit_sha,
        )

        serializer = GISViewDataSerializer(gis_view, context={"expires_in": 3600})
        data = serializer.data

        assert len(data["geojson_files"]) == 1
        geojson_file = data["geojson_files"][0]
        assert geojson_file["project_id"] == str(project.id)
        assert geojson_file["project_name"] == project.name
        assert geojson_file["commit_sha"] == commit_sha
        assert "url" in geojson_file
        assert geojson_file["use_latest"] is False

    def test_serializer_respects_expires_in_context(self) -> None:
        """Test that serializer uses expires_in from context."""

        project = ProjectFactory.create()
        gis_view = GISView.objects.create(
            name="Test View",
            owner=self.user,
            allow_precise_zoom=False,
        )

        commit_sha = "a" * 40
        create_project_geojson(
            project=project,
            commit_sha=commit_sha,
            commit_date=timezone.now(),
            author_name="Author",
            author_email="author@example.com",
            message="Test",
            file=temp_geojson_file(),
        )

        GISProjectView.objects.create(
            gis_view=gis_view,
            project=project,
            commit_sha=commit_sha,
        )

        # Serialize with different expires_in values
        serializer1 = GISViewDataSerializer(gis_view, context={"expires_in": 3600})
        serializer2 = GISViewDataSerializer(gis_view, context={"expires_in": 7200})

        data1 = serializer1.data
        data2 = serializer2.data

        # Both should return URLs (different expiration times)
        assert len(data1["geojson_files"]) == 1
        assert len(data2["geojson_files"]) == 1
        assert "url" in data1["geojson_files"][0]
        assert "url" in data2["geojson_files"][0]


@pytest.mark.django_db
class TestGISViewPublicDataAPI(BaseAPITestCase):
    """Test public data endpoint (token-based access)."""

    def test_public_access_with_valid_token(self) -> None:
        """Test accessing view data with valid token."""
        project = ProjectFactory.create()
        gis_view = GISView.objects.create(
            name="Test View",
            owner=self.user,
            allow_precise_zoom=False,
        )

        # Create GeoJSON
        commit_sha = "a" * 40
        create_project_geojson(
            project=project,
            commit_sha=commit_sha,
            commit_date=timezone.now(),
            author_name="John Doe",
            author_email="john.doe@example.com",
            message="Initial commit",
            file=temp_geojson_file(),
        )

        # Add to view
        GISProjectView.objects.create(
            gis_view=gis_view,
            project=project,
            commit_sha=commit_sha,
        )

        # Access without authentication
        client = self.client_class()
        response = client.get(
            reverse(
                "api:v1:gis-ogc:view-data", kwargs={"gis_token": gis_view.gis_token}
            )
        )

        assert response.status_code == status.HTTP_200_OK

        data = response.json()

        assert len(data.get("links", [])) == 3  # noqa: PLR2004
        assert len(data.get("collections", [])) == 1

    def test_public_access_with_invalid_token(self) -> None:
        """Test that invalid token returns 404."""
        client = self.client_class()
        fake_token = "0" * 40

        response = client.get(
            reverse("api:v1:gis-ogc:view-data", kwargs={"gis_token": fake_token}),
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_public_access_respects_expiration_param(self) -> None:
        """Test that expires_in parameter is respected."""
        project = ProjectFactory.create()
        gis_view = GISView.objects.create(
            name="Test View",
            owner=self.user,
            allow_precise_zoom=False,
        )

        commit_sha = "a" * 40
        create_project_geojson(
            project=project,
            commit_sha=commit_sha,
            commit_date=timezone.now(),
            author_name="John Doe",
            author_email="john.doe@example.com",
            message="Initial commit",
            file=temp_geojson_file(),
        )

        GISProjectView.objects.create(
            gis_view=gis_view,
            project=project,
            commit_sha=commit_sha,
        )

        client = self.client_class()
        response = client.get(
            reverse("api:v1:gis-view-data", kwargs={"id": gis_view.id})
            + "?expires_in=7200",
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_200_OK
        # URL should be generated successfully

    def test_public_access_with_latest_commit(self) -> None:
        """Test that use_latest flag works correctly."""
        project = ProjectFactory.create()
        gis_view = GISView.objects.create(
            name="Test View",
            owner=self.user,
            allow_precise_zoom=False,
        )

        # Create multiple GeoJSONs
        old_sha = "a" * 40
        new_sha = "b" * 40

        create_project_geojson(
            project=project,
            commit_sha=old_sha,
            commit_date=timezone.now(),
            author_name="John Doe",
            author_email="john.doe@example.com",
            message="Initial commit",
            file=temp_geojson_file(),
        )

        latest = create_project_geojson(
            project=project,
            commit_sha=new_sha,
            commit_date=timezone.now(),
            author_name="John Doe",
            author_email="john.doe@example.com",
            message="Initial commit",
            file=temp_geojson_file(),
        )

        GISProjectView.objects.create(
            gis_view=gis_view,
            project=project,
            use_latest=True,
        )

        client = self.client_class()
        response = client.get(
            reverse("api:v1:gis-view-data", kwargs={"id": gis_view.id}),
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["data"]["geojson_files"][0]["commit_sha"] == latest.commit_sha
        assert data["data"]["geojson_files"][0]["use_latest"] is True

    def test_multiple_projects_returned(self) -> None:
        """Test that multiple projects are returned correctly."""
        project1 = ProjectFactory.create()
        project2 = ProjectFactory.create()
        gis_view = GISView.objects.create(
            name="Test View",
            owner=self.user,
            allow_precise_zoom=False,
        )

        sha1 = "a" * 40
        sha2 = "b" * 40

        create_project_geojson(
            project=project1,
            commit_sha=sha1,
            commit_date=timezone.now(),
            author_name="John Doe",
            author_email="john.doe@example.com",
            message="Initial commit",
            file=temp_geojson_file(),
        )

        create_project_geojson(
            project=project2,
            commit_sha=sha2,
            commit_date=timezone.now(),
            author_name="John Doe",
            author_email="john.doe@example.com",
            message="Initial commit",
            file=temp_geojson_file(),
        )

        GISProjectView.objects.create(
            gis_view=gis_view,
            project=project1,
            commit_sha=sha1,
        )

        GISProjectView.objects.create(
            gis_view=gis_view,
            project=project2,
            use_latest=True,
        )

        client = self.client_class()
        response = client.get(
            reverse("api:v1:gis-view-data", kwargs={"id": gis_view.id}),
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["data"]["geojson_files"]) == 2  # noqa: PLR2004

    def test_empty_view_returns_empty_list(self) -> None:
        """Test that a view with no projects returns empty geojson_files list."""
        gis_view = GISView.objects.create(
            name="Empty View",
            owner=self.user,
            allow_precise_zoom=False,
        )

        client = self.client_class()
        response = client.get(
            reverse("api:v1:gis-view-data", kwargs={"id": gis_view.id}),
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["data"]["geojson_files"] == []

    def test_view_with_missing_geojson_returns_partial(self) -> None:
        """Test that views with some missing GeoJSONs return available ones."""
        project1 = ProjectFactory.create()
        project2 = ProjectFactory.create()
        gis_view = GISView.objects.create(
            name="Test View",
            owner=self.user,
            allow_precise_zoom=False,
        )

        sha1 = "a" * 40

        # Only create GeoJSON for project1
        create_project_geojson(
            project=project1,
            commit_sha=sha1,
            commit_date=timezone.now(),
            author_name="John Doe",
            author_email="john.doe@example.com",
            message="Initial commit",
            file=temp_geojson_file(),
        )

        # Add both projects, but project2 has no GeoJSON
        GISProjectView.objects.create(
            gis_view=gis_view,
            project=project1,
            commit_sha=sha1,
        )

        GISProjectView.objects.create(
            gis_view=gis_view,
            project=project2,
            commit_sha="b" * 40,  # Doesn't exist
        )

        client = self.client_class()
        response = client.get(
            reverse("api:v1:gis-view-data", kwargs={"id": gis_view.id}),
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        # Should only return project1's GeoJSON
        assert len(data["data"]["geojson_files"]) == 1
        assert data["data"]["geojson_files"][0]["project_id"] == str(project1.id)

    def test_response_structure_with_serializer(self) -> None:
        """Test that response structure matches the serializer specification."""
        project = ProjectFactory.create()
        gis_view = GISView.objects.create(
            name="Test View",
            description="Test description",
            allow_precise_zoom=True,
            owner=self.user,
        )

        commit_sha = "a" * 40
        create_project_geojson(
            project=project,
            commit_sha=commit_sha,
            commit_date=timezone.now(),
            author_name="Author",
            author_email="author@example.com",
            message="Test",
            file=temp_geojson_file(),
        )

        GISProjectView.objects.create(
            gis_view=gis_view,
            project=project,
            commit_sha=commit_sha,
        )

        client = self.client_class()
        response = client.get(
            reverse("api:v1:gis-view-data", kwargs={"id": gis_view.id}),
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Verify top-level structure
        assert data["success"] is True
        assert "data" in data

        # Verify nested structure from serializer
        response_data = data["data"]
        assert "view_id" in response_data
        assert "view_name" in response_data
        assert "description" in response_data
        assert "allow_precise_zoom" in response_data
        assert "geojson_files" in response_data

        # Verify values
        assert response_data["view_name"] == "Test View"
        assert response_data["description"] == "Test description"
        assert response_data["allow_precise_zoom"] is True

        # Verify types
        assert isinstance(response_data["view_id"], str)
        assert isinstance(response_data["view_name"], str)
        assert isinstance(response_data["description"], str)
        assert isinstance(response_data["allow_precise_zoom"], bool)
        assert isinstance(response_data["geojson_files"], list)

        # Verify geojson_file structure
        geojson_file = response_data["geojson_files"][0]
        assert "project_id" in geojson_file
        assert "project_name" in geojson_file
        assert "commit_sha" in geojson_file
        assert "commit_date" in geojson_file
        assert "url" in geojson_file
        assert "use_latest" in geojson_file

    def test_expiration_parameter_clamping(self) -> None:
        """Test that expiration parameter is properly clamped to min/max."""
        project = ProjectFactory.create()
        gis_view = GISView.objects.create(
            name="Test View",
            owner=self.user,
            allow_precise_zoom=False,
        )

        commit_sha = "a" * 40
        create_project_geojson(
            project=project,
            commit_sha=commit_sha,
            commit_date=timezone.now(),
            author_name="Author",
            author_email="author@example.com",
            message="Test",
            file=temp_geojson_file(),
        )

        GISProjectView.objects.create(
            gis_view=gis_view,
            project=project,
            commit_sha=commit_sha,
        )

        client = self.client_class()

        # Test with very small expiration (should be clamped to 60)
        response = client.get(
            reverse("api:v1:gis-view-data", kwargs={"id": gis_view.id})
            + "?expires_in=1",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()["data"]["geojson_files"]) == 1

        # Test with very large expiration (should be clamped to 86400)
        response = client.get(
            reverse("api:v1:gis-view-data", kwargs={"id": gis_view.id})
            + "?expires_in=999999",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()["data"]["geojson_files"]) == 1

    def test_serializer_with_empty_description(self) -> None:
        """Test that serializer handles empty description gracefully."""
        gis_view = GISView.objects.create(
            name="Test View",
            description="",  # Empty description
            owner=self.user,
            allow_precise_zoom=False,
        )

        client = self.client_class()
        response = client.get(
            reverse("api:v1:gis-view-data", kwargs={"id": gis_view.id}),
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["data"]["description"] == ""
        assert data["data"]["view_name"] == "Test View"


@pytest.mark.django_db
class TestPublicGISProjectViewSerializer(BaseAPITestCase):
    """Test PublicGISProjectViewSerializer."""

    def test_serializer_field_mapping(self) -> None:
        """Test that serializer correctly maps source fields."""
        data = {
            "project_id": "12345678-1234-1234-1234-123456789012",
            "project_name": "Test Cave Project",
            "url": "https://example.com/geojson.json",
            "commit_sha": "a" * 40,
            "commit_date": "2024-01-15T10:30:00+00:00",
            "use_latest": False,
        }

        serializer = PublicGISProjectViewSerializer(data)
        result = serializer.data

        # Verify field name mappings
        assert result["id"] == data["project_id"]
        assert result["name"] == data["project_name"]
        assert result["geojson_file"] == data["url"]
        assert result["commit_sha"] == data["commit_sha"]
        assert result["commit_date"] == data["commit_date"]
        assert result["use_latest"] is False

    def test_serializer_handles_string_url(self) -> None:
        """Test that serializer handles plain string URL."""
        data = {
            "project_id": "12345678-1234-1234-1234-123456789012",
            "project_name": "Test Project",
            "url": "https://example.com/direct.json",  # URL as string
            "commit_sha": "b" * 40,
            "commit_date": "2024-01-20T15:45:00+00:00",
            "use_latest": False,
        }

        serializer = PublicGISProjectViewSerializer(data)
        result = serializer.data

        assert result["geojson_file"] == "https://example.com/direct.json"

    def test_serializer_many_mode(self) -> None:
        """Test serializer with multiple projects."""
        projects_data = [
            {
                "project_id": "11111111-1111-1111-1111-111111111111",
                "project_name": "Project A",
                "url": "https://example.com/a.json",
                "commit_sha": "a" * 40,
                "commit_date": "2024-01-01T00:00:00+00:00",
                "use_latest": True,
            },
            {
                "project_id": "22222222-2222-2222-2222-222222222222",
                "project_name": "Project B",
                "url": ("https://example.com/b.json",),
                "commit_sha": "b" * 40,
                "commit_date": "2024-02-01T00:00:00+00:00",
                "use_latest": False,
            },
        ]

        serializer = PublicGISProjectViewSerializer(projects_data, many=True)  # type: ignore[arg-type]
        result = serializer.data

        assert len(result) == 2  # noqa: PLR2004
        assert result[0]["name"] == "Project A"
        assert result[1]["name"] == "Project B"
        assert result[0]["use_latest"] is True
        assert result[1]["use_latest"] is False


@pytest.mark.django_db
class TestPublicGISViewSerializer(BaseAPITestCase):
    """Test PublicGISViewSerializer."""

    def test_serializer_basic_structure(self) -> None:
        """Test that serializer produces correct basic structure."""
        gis_view = GISView.objects.create(
            name="Public Test View",
            description="A view for public access",
            allow_precise_zoom=True,
            owner=self.user,
        )

        serializer = PublicGISViewSerializer(gis_view, context={"expires_in": 3600})
        data = serializer.data

        assert "view_name" in data
        assert "view_description" in data
        assert "allow_precise_zoom" in data
        assert "projects" in data
        assert data["view_name"] == "Public Test View"
        assert data["view_description"] == "A view for public access"
        assert data["allow_precise_zoom"] is True
        assert isinstance(data["projects"], list)

    def test_serializer_with_projects(self) -> None:
        """Test serializer includes project data correctly."""
        project = ProjectFactory.create()
        gis_view = GISView.objects.create(
            name="View With Projects",
            description="Has projects",
            owner=self.user,
            allow_precise_zoom=False,
        )

        commit_sha = "c" * 40
        create_project_geojson(
            project=project,
            commit_sha=commit_sha,
            commit_date=timezone.now(),
            author_name="Author",
            author_email="author@example.com",
            message="Test commit",
            file=temp_geojson_file(),
        )

        GISProjectView.objects.create(
            gis_view=gis_view,
            project=project,
            commit_sha=commit_sha,
        )

        serializer = PublicGISViewSerializer(gis_view, context={"expires_in": 3600})
        data = serializer.data

        assert len(data["projects"]) == 1
        project_data = data["projects"][0]
        assert project_data["id"] == str(project.id)
        assert project_data["name"] == project.name
        assert "geojson_file" in project_data
        assert project_data["commit_sha"] == commit_sha
        assert project_data["use_latest"] is False

    def test_serializer_with_use_latest(self) -> None:
        """Test serializer with use_latest flag."""
        project = ProjectFactory.create()
        gis_view = GISView.objects.create(
            name="Latest View",
            owner=self.user,
            allow_precise_zoom=False,
        )

        commit_sha = "d" * 40
        create_project_geojson(
            project=project,
            commit_sha=commit_sha,
            commit_date=timezone.now(),
            author_name="Author",
            author_email="author@example.com",
            message="Latest",
            file=temp_geojson_file(),
        )

        GISProjectView.objects.create(
            gis_view=gis_view,
            project=project,
            use_latest=True,
        )

        serializer = PublicGISViewSerializer(gis_view, context={"expires_in": 3600})
        data = serializer.data

        assert len(data["projects"]) == 1
        assert data["projects"][0]["use_latest"] is True

    def test_serializer_empty_view(self) -> None:
        """Test serializer with view containing no projects."""
        gis_view = GISView.objects.create(
            name="Empty View",
            description="No projects",
            owner=self.user,
            allow_precise_zoom=False,
        )

        serializer = PublicGISViewSerializer(gis_view, context={"expires_in": 3600})
        data = serializer.data

        assert data["view_name"] == "Empty View"
        assert data["projects"] == []

    def test_serializer_empty_description(self) -> None:
        """Test serializer with empty description."""
        gis_view = GISView.objects.create(
            name="No Description View",
            description="",
            owner=self.user,
            allow_precise_zoom=False,
        )

        serializer = PublicGISViewSerializer(gis_view, context={"expires_in": 3600})
        data = serializer.data

        assert data["view_description"] == ""

    def test_serializer_multiple_projects(self) -> None:
        """Test serializer with multiple projects."""
        project1 = ProjectFactory.create()
        project2 = ProjectFactory.create()
        gis_view = GISView.objects.create(
            name="Multi-Project View",
            owner=self.user,
            allow_precise_zoom=False,
        )

        sha1 = "e" * 40
        sha2 = "f" * 40

        create_project_geojson(
            project=project1,
            commit_sha=sha1,
            commit_date=timezone.now(),
            author_name="Author",
            author_email="author@example.com",
            message="Commit 1",
            file=temp_geojson_file(),
        )

        create_project_geojson(
            project=project2,
            commit_sha=sha2,
            commit_date=timezone.now(),
            author_name="Author",
            author_email="author@example.com",
            message="Commit 2",
            file=temp_geojson_file(),
        )

        GISProjectView.objects.create(
            gis_view=gis_view,
            project=project1,
            commit_sha=sha1,
        )

        GISProjectView.objects.create(
            gis_view=gis_view,
            project=project2,
            use_latest=True,
        )

        serializer = PublicGISViewSerializer(gis_view, context={"expires_in": 3600})
        data = serializer.data

        assert len(data["projects"]) == 2  # noqa: PLR2004

        project_ids = {p["id"] for p in data["projects"]}
        assert str(project1.id) in project_ids
        assert str(project2.id) in project_ids

    def test_serializer_respects_expires_in_context(self) -> None:
        """Test that expires_in context is used."""
        project = ProjectFactory.create()
        gis_view = GISView.objects.create(
            name="Expiration Test View",
            owner=self.user,
            allow_precise_zoom=False,
        )

        commit_sha = "1" * 40
        create_project_geojson(
            project=project,
            commit_sha=commit_sha,
            commit_date=timezone.now(),
            author_name="Author",
            author_email="author@example.com",
            message="Test",
            file=temp_geojson_file(),
        )

        GISProjectView.objects.create(
            gis_view=gis_view,
            project=project,
            commit_sha=commit_sha,
        )

        # Both should produce valid URLs with different expirations
        serializer1 = PublicGISViewSerializer(gis_view, context={"expires_in": 3600})
        serializer2 = PublicGISViewSerializer(gis_view, context={"expires_in": 7200})

        data1 = serializer1.data
        data2 = serializer2.data

        assert len(data1["projects"]) == 1
        assert len(data2["projects"]) == 1
        assert "geojson_file" in data1["projects"][0]
        assert "geojson_file" in data2["projects"][0]


@pytest.mark.django_db
class TestPublicGISViewGeoJSONApi(BaseAPITestCase):
    """Test the public GIS View GeoJSON API endpoint for frontend map viewer."""

    def test_public_access_with_valid_token(self) -> None:
        """Test accessing view data with valid token without authentication."""
        project = ProjectFactory.create()
        gis_view = GISView.objects.create(
            name="Public Frontend View",
            description="For frontend map",
            owner=self.user,
            allow_precise_zoom=False,
        )

        commit_sha = "a" * 40
        create_project_geojson(
            project=project,
            commit_sha=commit_sha,
            commit_date=timezone.now(),
            author_name="Author",
            author_email="author@example.com",
            message="Initial commit",
            file=temp_geojson_file(),
        )

        GISProjectView.objects.create(
            gis_view=gis_view,
            project=project,
            commit_sha=commit_sha,
        )

        # Access WITHOUT authentication
        client = self.client_class()
        response = client.get(
            reverse(
                "api:v1:gis-ogc:view-geojson",
                kwargs={"gis_token": gis_view.gis_token},
            )
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["success"] is True
        assert "data" in data

    def test_response_structure(self) -> None:
        """Test that response structure matches frontend expectations."""
        project = ProjectFactory.create()
        gis_view = GISView.objects.create(
            name="Structure Test View",
            description="Testing structure",
            allow_precise_zoom=False,
            owner=self.user,
        )

        commit_sha = "b" * 40
        create_project_geojson(
            project=project,
            commit_sha=commit_sha,
            commit_date=timezone.now(),
            author_name="Author",
            author_email="author@example.com",
            message="Test commit",
            file=temp_geojson_file(),
        )

        GISProjectView.objects.create(
            gis_view=gis_view,
            project=project,
            commit_sha=commit_sha,
        )

        client = self.client_class()
        response = client.get(
            reverse(
                "api:v1:gis-ogc:view-geojson",
                kwargs={"gis_token": gis_view.gis_token},
            )
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()["data"]

        # Verify top-level structure
        assert "view_name" in data
        assert "view_description" in data
        assert "allow_precise_zoom" in data
        assert "projects" in data

        # Verify values
        assert data["view_name"] == "Structure Test View"
        assert data["view_description"] == "Testing structure"
        assert data["allow_precise_zoom"] is False
        assert isinstance(data["projects"], list)

        # Verify project structure
        assert len(data["projects"]) == 1
        project_data = data["projects"][0]
        assert "id" in project_data
        assert "name" in project_data
        assert "geojson_file" in project_data
        assert "commit_sha" in project_data
        assert "commit_date" in project_data
        assert "use_latest" in project_data

        # Verify types
        assert isinstance(project_data["id"], str)
        assert isinstance(project_data["name"], str)
        assert isinstance(project_data["geojson_file"], str)
        assert isinstance(project_data["commit_sha"], str)
        assert isinstance(project_data["commit_date"], str)
        assert isinstance(project_data["use_latest"], bool)

    def test_invalid_token_returns_404(self) -> None:
        """Test that invalid token returns 404."""
        client = self.client_class()
        fake_token = "0" * 40

        response = client.get(
            reverse(
                "api:v1:gis-ogc:view-geojson",
                kwargs={"gis_token": fake_token},
            )
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_empty_view_returns_empty_projects(self) -> None:
        """Test that view with no projects returns empty list."""
        gis_view = GISView.objects.create(
            name="Empty View",
            owner=self.user,
            allow_precise_zoom=False,
        )

        client = self.client_class()
        response = client.get(
            reverse(
                "api:v1:gis-ogc:view-geojson",
                kwargs={"gis_token": gis_view.gis_token},
            )
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()["data"]
        assert data["projects"] == []

    def test_multiple_projects(self) -> None:
        """Test view with multiple projects."""
        project1 = ProjectFactory.create()
        project2 = ProjectFactory.create()
        gis_view = GISView.objects.create(
            name="Multi-Project View",
            owner=self.user,
            allow_precise_zoom=False,
        )

        sha1 = "1" * 40
        sha2 = "2" * 40

        create_project_geojson(
            project=project1,
            commit_sha=sha1,
            commit_date=timezone.now(),
            author_name="Author",
            author_email="author@example.com",
            message="Commit 1",
            file=temp_geojson_file(),
        )

        create_project_geojson(
            project=project2,
            commit_sha=sha2,
            commit_date=timezone.now(),
            author_name="Author",
            author_email="author@example.com",
            message="Commit 2",
            file=temp_geojson_file(),
        )

        GISProjectView.objects.create(
            gis_view=gis_view,
            project=project1,
            commit_sha=sha1,
        )

        GISProjectView.objects.create(
            gis_view=gis_view,
            project=project2,
            use_latest=True,
        )

        client = self.client_class()
        response = client.get(
            reverse(
                "api:v1:gis-ogc:view-geojson",
                kwargs={"gis_token": gis_view.gis_token},
            )
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()["data"]
        assert len(data["projects"]) == 2  # noqa: PLR2004

    def test_use_latest_flag(self) -> None:
        """Test that use_latest returns correct commit."""
        project = ProjectFactory.create()
        gis_view = GISView.objects.create(
            name="Latest Test View",
            owner=self.user,
            allow_precise_zoom=False,
        )

        old_sha = "a" * 40
        new_sha = "b" * 40

        create_project_geojson(
            project=project,
            commit_sha=old_sha,
            commit_date=timezone.now(),
            author_name="Author",
            author_email="author@example.com",
            message="Old commit",
            file=temp_geojson_file(),
        )

        latest = create_project_geojson(
            project=project,
            commit_sha=new_sha,
            commit_date=timezone.now(),
            author_name="Author",
            author_email="author@example.com",
            message="New commit",
            file=temp_geojson_file(),
        )

        GISProjectView.objects.create(
            gis_view=gis_view,
            project=project,
            use_latest=True,
        )

        client = self.client_class()
        response = client.get(
            reverse(
                "api:v1:gis-ogc:view-geojson",
                kwargs={"gis_token": gis_view.gis_token},
            )
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()["data"]
        assert len(data["projects"]) == 1
        assert data["projects"][0]["commit_sha"] == latest.commit_sha
        assert data["projects"][0]["use_latest"] is True

    def test_specific_commit_sha(self) -> None:
        """Test that specific commit_sha returns correct commit."""
        project = ProjectFactory.create()
        gis_view = GISView.objects.create(
            name="Specific Commit View",
            owner=self.user,
            allow_precise_zoom=False,
        )

        old_sha = "1" * 40
        new_sha = "2" * 40

        old_geojson = create_project_geojson(
            project=project,
            commit_sha=old_sha,
            commit_date=timezone.now(),
            author_name="Author",
            author_email="author@example.com",
            message="Old commit",
            file=temp_geojson_file(),
        )

        create_project_geojson(
            project=project,
            commit_sha=new_sha,
            commit_date=timezone.now(),
            author_name="Author",
            author_email="author@example.com",
            message="New commit",
            file=temp_geojson_file(),
        )

        # Add with specific old commit
        GISProjectView.objects.create(
            gis_view=gis_view,
            project=project,
            commit_sha=old_sha,
        )

        client = self.client_class()
        response = client.get(
            reverse(
                "api:v1:gis-ogc:view-geojson",
                kwargs={"gis_token": gis_view.gis_token},
            )
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()["data"]
        assert len(data["projects"]) == 1
        assert data["projects"][0]["commit_sha"] == old_geojson.commit_sha
        assert data["projects"][0]["use_latest"] is False

    def test_partial_missing_geojson(self) -> None:
        """Test that views with some missing GeoJSONs return available ones."""
        project1 = ProjectFactory.create()
        project2 = ProjectFactory.create()
        gis_view = GISView.objects.create(
            name="Partial View",
            owner=self.user,
            allow_precise_zoom=False,
        )

        sha1 = "1" * 40

        # Only create GeoJSON for project1
        create_project_geojson(
            project=project1,
            commit_sha=sha1,
            commit_date=timezone.now(),
            author_name="Author",
            author_email="author@example.com",
            message="Commit 1",
            file=temp_geojson_file(),
        )

        GISProjectView.objects.create(
            gis_view=gis_view,
            project=project1,
            commit_sha=sha1,
        )

        GISProjectView.objects.create(
            gis_view=gis_view,
            project=project2,
            commit_sha="2" * 40,  # Doesn't exist
        )

        client = self.client_class()
        response = client.get(
            reverse(
                "api:v1:gis-ogc:view-geojson",
                kwargs={"gis_token": gis_view.gis_token},
            )
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()["data"]
        # Should only return project1's data
        assert len(data["projects"]) == 1
        assert data["projects"][0]["id"] == str(project1.id)

    def test_geojson_file_url_is_valid(self) -> None:
        """Test that geojson_file contains a valid URL."""
        project = ProjectFactory.create()
        gis_view = GISView.objects.create(
            name="URL Test View",
            owner=self.user,
            allow_precise_zoom=False,
        )

        commit_sha = "a" * 40
        create_project_geojson(
            project=project,
            commit_sha=commit_sha,
            commit_date=timezone.now(),
            author_name="Author",
            author_email="author@example.com",
            message="Test",
            file=temp_geojson_file(),
        )

        GISProjectView.objects.create(
            gis_view=gis_view,
            project=project,
            commit_sha=commit_sha,
        )

        client = self.client_class()
        response = client.get(
            reverse(
                "api:v1:gis-ogc:view-geojson",
                kwargs={"gis_token": gis_view.gis_token},
            )
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()["data"]

        geojson_url = data["projects"][0]["geojson_file"]
        assert geojson_url.startswith("http")
        assert ".geojson" in geojson_url or "geojson" in geojson_url.lower()

    def test_authenticated_user_can_also_access(self) -> None:
        """Test that authenticated users can also access the public endpoint."""
        project = ProjectFactory.create()
        gis_view = GISView.objects.create(
            name="Auth Test View",
            owner=self.user,
            allow_precise_zoom=False,
        )

        commit_sha = "a" * 40
        create_project_geojson(
            project=project,
            commit_sha=commit_sha,
            commit_date=timezone.now(),
            author_name="Author",
            author_email="author@example.com",
            message="Test",
            file=temp_geojson_file(),
        )

        GISProjectView.objects.create(
            gis_view=gis_view,
            project=project,
            commit_sha=commit_sha,
        )

        # Access WITH authentication
        client = self.client_class()
        response = client.get(
            reverse(
                "api:v1:gis-ogc:view-geojson",
                kwargs={"gis_token": gis_view.gis_token},
            ),
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_200_OK

    def test_different_owner_can_access_public_view(self) -> None:
        """Test that a different user can access another user's public view."""
        project = ProjectFactory.create()
        gis_view = GISView.objects.create(
            name="Another User's View",
            owner=self.user,
            allow_precise_zoom=False,
        )

        commit_sha = "a" * 40
        create_project_geojson(
            project=project,
            commit_sha=commit_sha,
            commit_date=timezone.now(),
            author_name="Author",
            author_email="author@example.com",
            message="Test",
            file=temp_geojson_file(),
        )

        GISProjectView.objects.create(
            gis_view=gis_view,
            project=project,
            commit_sha=commit_sha,
        )

        # Access without any authentication (simulating different user)
        client = self.client_class()
        response = client.get(
            reverse(
                "api:v1:gis-ogc:view-geojson",
                kwargs={"gis_token": gis_view.gis_token},
            )
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()["data"]
        assert data["view_name"] == "Another User's View"


@pytest.mark.django_db
class TestOGCGISUserCollectionApi(BaseAPITestCase):
    """Test OGC GIS user-collection endpoint returns JSON-serializable data.

    Regression test: previously the view returned project_geojson.commit
    (a ProjectCommit model instance) as the ``"id"`` field instead of
    project_geojson.commit_sha (a string), causing:
        TypeError: Object of type ProjectCommit is not JSON serializable
    """

    def setUp(self) -> None:
        super().setUp()

        # The user_token URL converter requires [0-9a-fA-F]{40}, so replace
        # the token with one that has a hex-compatible key.
        self.token.delete()
        self.token = Token.objects.create(
            user=self.user, key="a1b2c3d4e5f6a7b8c9d0" * 2
        )

        self.project = ProjectFactory.create(created_by=self.user.email)
        UserProjectPermissionFactory(
            target=self.user,
            level=PermissionLevel.READ_ONLY,
            project=self.project,
        )

    def test_user_collection_returns_commit_sha_string(self) -> None:
        """Call the user-collection endpoint and verify the response ``id``
        is the commit SHA string, not a ProjectCommit object."""

        commit_sha = "b" * 40
        create_project_geojson(
            project=self.project,
            commit_sha=commit_sha,
            commit_date=timezone.now(),
            author_name="Test Author",
            author_email="test@example.com",
            message="Test commit",
            file=temp_geojson_file(),
        )

        response = self.client.get(
            reverse(
                "api:v1:gis-ogc:user-collection",
                kwargs={
                    "key": self.token.key,
                    "commit_sha": commit_sha,
                },
            )
        )

        # Without the fix, this returns 500 with:
        #   TypeError: Object of type ProjectCommit is not JSON serializable
        assert response.status_code == status.HTTP_200_OK

        data = response.json()

        # Verify the id field is the commit SHA string
        assert data["id"] == commit_sha
        assert isinstance(data["id"], str)

        # Verify the rest of the response structure
        assert "title" in data
        assert "description" in data
        assert "links" in data


# ======================================================================
# OGC API - Features conformance tests
# ======================================================================


def _temp_linestring_geojson_file() -> SimpleUploadedFile:
    """Create a GeoJSON with both Point and LineString features."""
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
                            "coordinates": [-87.5, 20.2],
                        },
                        "properties": {"name": "Entrance"},
                    },
                    {
                        "type": "Feature",
                        "geometry": {
                            "type": "LineString",
                            "coordinates": [
                                [-87.5, 20.2],
                                [-87.6, 20.3],
                                [-87.7, 20.4],
                            ],
                        },
                        "properties": {"name": "Passage A"},
                    },
                    {
                        "type": "Feature",
                        "geometry": {
                            "type": "LineString",
                            "coordinates": [
                                [-87.6, 20.3],
                                [-87.65, 20.35],
                            ],
                        },
                        "properties": {"name": "Passage B"},
                    },
                ],
            }
        ),
        content_type="application/geo+json",
    )


# ---------------------------------------------------------------------------
# Base test case for OGC GIS-View endpoints
# ---------------------------------------------------------------------------


class BaseOGCViewTestCase(BaseAPITestCase):
    """Common setUp for all OGC GIS-View endpoint tests.

    Provides ``self.project``, ``self.gis_view``, ``self.commit_sha``,
    and ``self.public_client`` (unauthenticated).
    """

    project: Project
    gis_view: GISView
    commit_sha: str

    def setUp(self) -> None:
        super().setUp()
        self.project = ProjectFactory.create()
        self.gis_view = GISView.objects.create(
            name="OGC Test View",
            owner=self.user,
            allow_precise_zoom=False,
        )
        self.commit_sha = "a" * 40
        create_project_geojson(
            project=self.project,
            commit_sha=self.commit_sha,
            commit_date=timezone.now(),
            author_name="Test Author",
            author_email="test@example.com",
            message="Initial commit",
            file=_temp_linestring_geojson_file(),
        )
        GISProjectView.objects.create(
            gis_view=self.gis_view,
            project=self.project,
            commit_sha=self.commit_sha,
        )
        self.public_client = self.client_class()


@pytest.mark.django_db
class TestOGCLandingPage(BaseOGCViewTestCase):
    """OGC API - Features §7.2: Landing page requirements."""

    def _get_landing(self) -> dict[str, Any]:
        resp = self.public_client.get(
            reverse(
                "api:v1:gis-ogc:view-landing",
                kwargs={"gis_token": self.gis_view.gis_token},
            )
        )
        assert resp.status_code == status.HTTP_200_OK
        return resp.json()  # type: ignore[no-any-return]

    def test_landing_page_returns_200(self) -> None:
        self._get_landing()

    def test_landing_page_has_title(self) -> None:
        data = self._get_landing()
        assert "title" in data
        assert isinstance(data["title"], str)

    def test_landing_page_has_links(self) -> None:
        data = self._get_landing()
        assert "links" in data
        assert isinstance(data["links"], list)
        assert len(data["links"]) >= 3  # noqa: PLR2004  # self, conformance, data

    def test_landing_page_has_self_link(self) -> None:
        data = self._get_landing()
        rels = {link["rel"] for link in data["links"]}
        assert "self" in rels

    def test_landing_page_has_conformance_link(self) -> None:
        data = self._get_landing()
        rels = {link["rel"] for link in data["links"]}
        assert "conformance" in rels

    def test_landing_page_has_data_link(self) -> None:
        """``rel: data`` must point to the collections endpoint."""
        data = self._get_landing()
        data_links = [link for link in data["links"] if link["rel"] == "data"]
        assert len(data_links) == 1
        assert data_links[0]["type"] == "application/json"

    def test_landing_page_has_service_desc_link(self) -> None:
        data = self._get_landing()
        rels = {link["rel"] for link in data["links"]}
        assert "service-desc" in rels

    def test_landing_page_all_links_have_required_fields(self) -> None:
        """Each link object must have href, rel, type."""
        data = self._get_landing()
        for link in data["links"]:
            assert "href" in link, f"Link missing href: {link}"
            assert "rel" in link, f"Link missing rel: {link}"
            assert "type" in link, f"Link missing type: {link}"

    def test_landing_page_invalid_token_returns_404(self) -> None:
        resp = self.public_client.get(
            reverse(
                "api:v1:gis-ogc:view-landing",
                kwargs={"gis_token": "0" * 40},
            )
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestOGCConformance(BaseOGCViewTestCase):
    """OGC API - Features §7.4: Conformance declaration requirements."""

    def _get_conformance(self) -> dict[str, Any]:
        resp = self.public_client.get(
            reverse(
                "api:v1:gis-ogc:view-conformance",
                kwargs={"gis_token": self.gis_view.gis_token},
            )
        )
        assert resp.status_code == status.HTTP_200_OK
        return resp.json()  # type: ignore[no-any-return]

    def test_conformance_returns_200(self) -> None:
        self._get_conformance()

    def test_conformance_has_conforms_to(self) -> None:
        data = self._get_conformance()
        assert "conformsTo" in data
        assert isinstance(data["conformsTo"], list)

    def test_conformance_declares_core(self) -> None:
        data = self._get_conformance()
        assert (
            "http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/core"
            in data["conformsTo"]
        )

    def test_conformance_declares_geojson(self) -> None:
        data = self._get_conformance()
        assert (
            "http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/geojson"
            in data["conformsTo"]
        )

    def test_conformance_does_not_declare_filtering(self) -> None:
        """We intentionally do NOT declare CQL / filter conformance."""
        data = self._get_conformance()
        for cls in data["conformsTo"]:
            assert "filter" not in cls.lower()
            assert "cql" not in cls.lower()

    def test_conformance_invalid_token_returns_404(self) -> None:
        resp = self.public_client.get(
            reverse(
                "api:v1:gis-ogc:view-conformance",
                kwargs={"gis_token": "0" * 40},
            )
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestOGCCollections(BaseOGCViewTestCase):
    """OGC API - Features §7.13-14: Collections requirements."""

    def _get_collections(self) -> dict[str, Any]:
        resp = self.public_client.get(
            reverse(
                "api:v1:gis-ogc:view-data",
                kwargs={"gis_token": self.gis_view.gis_token},
            )
        )
        assert resp.status_code == status.HTTP_200_OK
        return resp.json()  # type: ignore[no-any-return]

    def test_collections_returns_200(self) -> None:
        self._get_collections()

    def test_collections_has_links(self) -> None:
        data = self._get_collections()
        assert "links" in data
        assert isinstance(data["links"], list)

    def test_collections_has_self_link(self) -> None:
        data = self._get_collections()
        rels = {link["rel"] for link in data["links"]}
        assert "self" in rels

    def test_collections_has_collections_array(self) -> None:
        data = self._get_collections()
        assert "collections" in data
        assert isinstance(data["collections"], list)
        assert len(data["collections"]) >= 1

    def test_collection_has_required_fields(self) -> None:
        """Each collection must have id, title, links."""
        data = self._get_collections()
        for coll in data["collections"]:
            assert "id" in coll
            assert "title" in coll
            assert "links" in coll

    def test_collection_has_self_link(self) -> None:
        data = self._get_collections()
        coll = data["collections"][0]
        rels = {link["rel"] for link in coll["links"]}
        assert "self" in rels

    def test_collection_has_items_link(self) -> None:
        data = self._get_collections()
        coll = data["collections"][0]
        items_links = [link for link in coll["links"] if link["rel"] == "items"]
        assert len(items_links) == 1
        assert items_links[0]["type"] == "application/geo+json"

    def test_collection_items_link_ends_with_items(self) -> None:
        """The items href must end with /items (not just the collection URL)."""
        data = self._get_collections()
        coll = data["collections"][0]
        items_href = next(
            link["href"] for link in coll["links"] if link["rel"] == "items"
        )
        assert items_href.endswith("/items")

    def test_collection_id_is_commit_sha(self) -> None:
        data = self._get_collections()
        coll = data["collections"][0]
        assert coll["id"] == self.commit_sha

    def test_collection_has_item_type(self) -> None:
        data = self._get_collections()
        coll = data["collections"][0]
        assert coll.get("itemType") == "feature"


@pytest.mark.django_db
class TestOGCSingleCollection(BaseOGCViewTestCase):
    """OGC API - Features §7.14: Single collection requirements."""

    def _get_collection(self) -> dict[str, Any]:
        resp = self.public_client.get(
            reverse(
                "api:v1:gis-ogc:view-collection",
                kwargs={
                    "gis_token": self.gis_view.gis_token,
                    "commit_sha": self.commit_sha,
                },
            )
        )
        assert resp.status_code == status.HTTP_200_OK
        return resp.json()  # type: ignore[no-any-return]

    def test_single_collection_returns_200(self) -> None:
        self._get_collection()

    def test_single_collection_has_id(self) -> None:
        data = self._get_collection()
        assert data["id"] == self.commit_sha

    def test_single_collection_has_title(self) -> None:
        data = self._get_collection()
        assert "title" in data
        assert data["title"] == self.project.name

    def test_single_collection_has_self_link(self) -> None:
        data = self._get_collection()
        rels = {link["rel"] for link in data["links"]}
        assert "self" in rels

    def test_single_collection_has_items_link(self) -> None:
        data = self._get_collection()
        items_links = [link for link in data["links"] if link["rel"] == "items"]
        assert len(items_links) == 1
        assert items_links[0]["type"] == "application/geo+json"
        assert items_links[0]["href"].endswith("/items")

    def test_single_collection_invalid_sha_returns_404(self) -> None:
        resp = self.public_client.get(
            reverse(
                "api:v1:gis-ogc:view-collection",
                kwargs={
                    "gis_token": self.gis_view.gis_token,
                    "commit_sha": "f" * 40,
                },
            )
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestOGCCollectionItems(BaseOGCViewTestCase):
    """OGC API - Features §7.15-16: /items endpoint requirements."""

    def _get_items_response(self, **extra_kwargs: Any) -> Any:
        return self.public_client.get(
            reverse(
                "api:v1:gis-ogc:view-collection-items",
                kwargs={
                    "gis_token": self.gis_view.gis_token,
                    "commit_sha": self.commit_sha,
                },
            ),
            **extra_kwargs,
        )

    def test_items_returns_200(self) -> None:
        resp = self._get_items_response()
        assert resp.status_code == status.HTTP_200_OK

    def test_items_content_type_is_geojson(self) -> None:
        resp = self._get_items_response()
        assert "application/geo+json" in resp["Content-Type"]

    def test_items_is_valid_feature_collection(self) -> None:
        resp = self._get_items_response()
        data = orjson.loads(b"".join(resp.streaming_content))
        assert data["type"] == "FeatureCollection"
        assert "features" in data
        assert isinstance(data["features"], list)

    def test_items_filters_to_linestring_only(self) -> None:
        """Proxy must strip non-LineString features for QGIS compatibility."""
        resp = self._get_items_response()
        data = orjson.loads(b"".join(resp.streaming_content))
        for feature in data["features"]:
            assert feature["geometry"]["type"] == "LineString"
        # Our fixture has 2 LineStrings and 1 Point -> expect 2
        assert len(data["features"]) == 2  # noqa: PLR2004

    def test_items_has_etag_header(self) -> None:
        resp = self._get_items_response()
        assert "ETag" in resp
        assert resp["ETag"] == f'"{self.commit_sha}"'

    def test_items_has_cache_control_header(self) -> None:
        resp = self._get_items_response()
        assert "Cache-Control" in resp
        assert "public" in resp["Cache-Control"]
        assert "max-age=86400" in resp["Cache-Control"]

    def test_items_has_content_disposition_inline(self) -> None:
        resp = self._get_items_response()
        assert resp.get("Content-Disposition") == "inline"

    def test_items_conditional_request_returns_304(self) -> None:
        """If-None-Match with matching ETag should return 304."""
        etag = f'"{self.commit_sha}"'
        resp = self._get_items_response(
            headers={"if-none-match": etag},
        )
        assert resp.status_code == status.HTTP_304_NOT_MODIFIED
        assert resp["ETag"] == etag

    def test_items_conditional_request_mismatched_etag_returns_200(self) -> None:
        resp = self._get_items_response(
            headers={"if-none-match": '"wrong"'},
        )
        assert resp.status_code == status.HTTP_200_OK

    def test_items_ignores_query_params(self) -> None:
        """limit, bbox, filter params must be silently ignored."""
        resp = self.public_client.get(
            reverse(
                "api:v1:gis-ogc:view-collection-items",
                kwargs={
                    "gis_token": self.gis_view.gis_token,
                    "commit_sha": self.commit_sha,
                },
            )
            + "?limit=10&bbox=-90,19,-86,21&filter=name%3D%27test%27",
        )
        assert resp.status_code == status.HTTP_200_OK
        data = orjson.loads(b"".join(resp.streaming_content))  # type: ignore[attr-defined]
        assert len(data["features"]) == 2  # noqa: PLR2004

    def test_items_invalid_commit_returns_404(self) -> None:
        resp = self.public_client.get(
            reverse(
                "api:v1:gis-ogc:view-collection-items",
                kwargs={
                    "gis_token": self.gis_view.gis_token,
                    "commit_sha": "f" * 40,
                },
            )
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_items_caching_returns_same_content(self) -> None:
        """Second request should be served from cache with identical bytes."""
        resp1 = self._get_items_response()
        resp2 = self._get_items_response()
        body1 = b"".join(resp1.streaming_content)
        body2 = b"".join(resp2.streaming_content)
        assert body1 == body2


@pytest.mark.django_db
class TestOGCDiscoveryFlow(BaseOGCViewTestCase):
    """End-to-end: follow the full QGIS-style discovery chain."""

    def test_full_discovery_chain(self) -> None:
        """Landing -> conformance -> collections -> collection -> items."""
        client = self.public_client
        token = self.gis_view.gis_token

        # 1. Landing page
        landing = client.get(
            reverse("api:v1:gis-ogc:view-landing", kwargs={"gis_token": token})
        ).json()
        assert "links" in landing

        # 2. Follow rel:conformance
        conf_href = next(
            link["href"] for link in landing["links"] if link["rel"] == "conformance"
        )
        conf = client.get(conf_href).json()
        assert "conformsTo" in conf

        # 3. Follow rel:data -> collections
        data_href = next(
            link["href"] for link in landing["links"] if link["rel"] == "data"
        )
        collections = client.get(data_href).json()
        assert len(collections["collections"]) >= 1

        # 4. Follow collection self link -> single collection
        coll = collections["collections"][0]
        self_href = next(
            link["href"] for link in coll["links"] if link["rel"] == "self"
        )
        single = client.get(self_href).json()
        assert single["id"] == coll["id"]

        # 5. Follow items link -> GeoJSON
        items_href = next(
            link["href"] for link in single["links"] if link["rel"] == "items"
        )
        items_resp = client.get(items_href)
        assert items_resp.status_code == status.HTTP_200_OK
        assert "application/geo+json" in items_resp["Content-Type"]

        geojson = orjson.loads(b"".join(items_resp.streaming_content))  # type: ignore[attr-defined]
        assert geojson["type"] == "FeatureCollection"
        assert len(geojson["features"]) >= 1


# ---------------------------------------------------------------------------
# Base test case for OGC User endpoints
# ---------------------------------------------------------------------------


class BaseOGCUserTestCase(BaseAPITestCase):
    """Common setUp for all OGC User endpoint tests.

    Provides ``self.project``, ``self.commit_sha``, and a hex-compatible
    ``self.token`` suitable for the ``user_token`` URL converter.
    """

    project: Project
    commit_sha: str

    def setUp(self) -> None:
        super().setUp()
        # The user_token URL converter requires [0-9a-fA-F]{40}
        self.token.delete()
        self.token = Token.objects.create(
            user=self.user, key="a1b2c3d4e5f6a7b8c9d0" * 2
        )
        self.project = ProjectFactory.create(created_by=self.user.email)
        UserProjectPermissionFactory(
            target=self.user,
            level=PermissionLevel.READ_ONLY,
            project=self.project,
        )
        self.commit_sha = "b" * 40
        create_project_geojson(
            project=self.project,
            commit_sha=self.commit_sha,
            commit_date=timezone.now(),
            author_name="Test Author",
            author_email="test@example.com",
            message="Initial commit",
            file=_temp_linestring_geojson_file(),
        )


@pytest.mark.django_db
class TestOGCUserCollections(BaseOGCUserTestCase):
    """OGC API - Features: user /collections endpoint."""

    def _get_collections(self) -> dict[str, Any]:
        resp = self.client.get(
            reverse(
                "api:v1:gis-ogc:user-data",
                kwargs={"key": self.token.key},
            )
        )
        assert resp.status_code == status.HTTP_200_OK
        return resp.json()  # type: ignore[no-any-return]

    def test_collections_returns_200(self) -> None:
        self._get_collections()

    def test_collections_has_links(self) -> None:
        data = self._get_collections()
        assert "links" in data
        assert isinstance(data["links"], list)

    def test_collections_has_self_link(self) -> None:
        data = self._get_collections()
        rels = {link["rel"] for link in data["links"]}
        assert "self" in rels

    def test_collections_has_collections_array(self) -> None:
        data = self._get_collections()
        assert "collections" in data
        assert isinstance(data["collections"], list)
        assert len(data["collections"]) >= 1

    def test_collection_has_required_fields(self) -> None:
        data = self._get_collections()
        for coll in data["collections"]:
            assert "id" in coll
            assert "title" in coll
            assert "links" in coll

    def test_collection_has_self_link(self) -> None:
        data = self._get_collections()
        coll = data["collections"][0]
        rels = {link["rel"] for link in coll["links"]}
        assert "self" in rels

    def test_collection_has_items_link(self) -> None:
        data = self._get_collections()
        coll = data["collections"][0]
        items_links = [link for link in coll["links"] if link["rel"] == "items"]
        assert len(items_links) == 1
        assert items_links[0]["type"] == "application/geo+json"

    def test_collection_items_link_ends_with_items(self) -> None:
        data = self._get_collections()
        coll = data["collections"][0]
        items_href = next(
            link["href"] for link in coll["links"] if link["rel"] == "items"
        )
        assert items_href.endswith("/items")

    def test_collection_id_is_commit_sha(self) -> None:
        data = self._get_collections()
        coll = data["collections"][0]
        assert coll["id"] == self.commit_sha

    def test_collection_has_item_type(self) -> None:
        data = self._get_collections()
        coll = data["collections"][0]
        assert coll.get("itemType") == "feature"


@pytest.mark.django_db
class TestOGCUserSingleCollection(BaseOGCUserTestCase):
    """OGC API - Features: user single collection endpoint."""

    def _get_collection(self) -> dict[str, Any]:
        resp = self.client.get(
            reverse(
                "api:v1:gis-ogc:user-collection",
                kwargs={
                    "key": self.token.key,
                    "commit_sha": self.commit_sha,
                },
            )
        )
        assert resp.status_code == status.HTTP_200_OK
        return resp.json()  # type: ignore[no-any-return]

    def test_single_collection_returns_200(self) -> None:
        self._get_collection()

    def test_single_collection_has_id(self) -> None:
        data = self._get_collection()
        assert data["id"] == self.commit_sha

    def test_single_collection_has_title(self) -> None:
        data = self._get_collection()
        assert "title" in data
        assert data["title"] == self.project.name

    def test_single_collection_has_self_link(self) -> None:
        data = self._get_collection()
        rels = {link["rel"] for link in data["links"]}
        assert "self" in rels

    def test_single_collection_has_items_link(self) -> None:
        data = self._get_collection()
        items_links = [link for link in data["links"] if link["rel"] == "items"]
        assert len(items_links) == 1
        assert items_links[0]["type"] == "application/geo+json"
        assert items_links[0]["href"].endswith("/items")

    def test_single_collection_invalid_sha_returns_404(self) -> None:
        resp = self.client.get(
            reverse(
                "api:v1:gis-ogc:user-collection",
                kwargs={
                    "key": self.token.key,
                    "commit_sha": "f" * 40,
                },
            )
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_single_collection_no_permission_returns_error(self) -> None:
        """User without access to the project gets an error (401 or 404)."""
        other_project = ProjectFactory.create()
        other_sha = "c" * 40
        create_project_geojson(
            project=other_project,
            commit_sha=other_sha,
            commit_date=timezone.now(),
            author_name="Other",
            author_email="other@example.com",
            message="Other commit",
            file=temp_geojson_file(),
        )
        resp = self.client.get(
            reverse(
                "api:v1:gis-ogc:user-collection",
                kwargs={
                    "key": self.token.key,
                    "commit_sha": other_sha,
                },
            )
        )
        assert resp.status_code in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_404_NOT_FOUND,
        )


@pytest.mark.django_db
class TestOGCUserCollectionItems(BaseOGCUserTestCase):
    """OGC API - Features: user /items endpoint."""

    def _get_items_response(self, **extra_kwargs: Any) -> Any:
        return self.client.get(
            reverse(
                "api:v1:gis-ogc:user-collection-items",
                kwargs={
                    "key": self.token.key,
                    "commit_sha": self.commit_sha,
                },
            ),
            **extra_kwargs,
        )

    def test_items_returns_200(self) -> None:
        resp = self._get_items_response()
        assert resp.status_code == status.HTTP_200_OK

    def test_items_content_type_is_geojson(self) -> None:
        resp = self._get_items_response()
        assert "application/geo+json" in resp["Content-Type"]

    def test_items_is_valid_feature_collection(self) -> None:
        resp = self._get_items_response()
        data = orjson.loads(b"".join(resp.streaming_content))
        assert data["type"] == "FeatureCollection"
        assert "features" in data
        assert isinstance(data["features"], list)

    def test_items_filters_to_linestring_only(self) -> None:
        resp = self._get_items_response()
        data = orjson.loads(b"".join(resp.streaming_content))
        for feature in data["features"]:
            assert feature["geometry"]["type"] == "LineString"
        assert len(data["features"]) == 2  # noqa: PLR2004

    def test_items_has_etag_header(self) -> None:
        resp = self._get_items_response()
        assert "ETag" in resp
        assert resp["ETag"] == f'"{self.commit_sha}"'

    def test_items_has_cache_control_header(self) -> None:
        resp = self._get_items_response()
        assert "Cache-Control" in resp
        assert "public" in resp["Cache-Control"]
        assert "max-age=86400" in resp["Cache-Control"]

    def test_items_has_content_disposition_inline(self) -> None:
        resp = self._get_items_response()
        assert resp.get("Content-Disposition") == "inline"

    def test_items_conditional_request_returns_304(self) -> None:
        etag = f'"{self.commit_sha}"'
        resp = self._get_items_response(
            headers={"if-none-match": etag},
        )
        assert resp.status_code == status.HTTP_304_NOT_MODIFIED
        assert resp["ETag"] == etag

    def test_items_conditional_request_mismatched_etag_returns_200(self) -> None:
        resp = self._get_items_response(
            headers={"if-none-match": '"wrong"'},
        )
        assert resp.status_code == status.HTTP_200_OK

    def test_items_ignores_query_params(self) -> None:
        resp = self.client.get(
            reverse(
                "api:v1:gis-ogc:user-collection-items",
                kwargs={
                    "key": self.token.key,
                    "commit_sha": self.commit_sha,
                },
            )
            + "?limit=10&bbox=-90,19,-86,21",
        )
        assert resp.status_code == status.HTTP_200_OK
        data = orjson.loads(b"".join(resp.streaming_content))  # type: ignore[attr-defined]
        assert len(data["features"]) == 2  # noqa: PLR2004

    def test_items_invalid_commit_returns_404(self) -> None:
        resp = self.client.get(
            reverse(
                "api:v1:gis-ogc:user-collection-items",
                kwargs={
                    "key": self.token.key,
                    "commit_sha": "f" * 40,
                },
            )
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_items_no_permission_returns_error(self) -> None:
        """User without access to the project gets an error (401 or 404)."""
        other_project = ProjectFactory.create()
        other_sha = "c" * 40
        create_project_geojson(
            project=other_project,
            commit_sha=other_sha,
            commit_date=timezone.now(),
            author_name="Other",
            author_email="other@example.com",
            message="Other commit",
            file=_temp_linestring_geojson_file(),
        )
        resp = self.client.get(
            reverse(
                "api:v1:gis-ogc:user-collection-items",
                kwargs={
                    "key": self.token.key,
                    "commit_sha": other_sha,
                },
            )
        )
        assert resp.status_code in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_404_NOT_FOUND,
        )

    def test_items_caching_returns_same_content(self) -> None:
        resp1 = self._get_items_response()
        resp2 = self._get_items_response()
        body1 = b"".join(resp1.streaming_content)
        body2 = b"".join(resp2.streaming_content)
        assert body1 == body2


# ======================================================================
# OGC API - Features: USER discovery endpoints
# ======================================================================


@pytest.mark.django_db
class TestOGCUserLandingPage(BaseOGCUserTestCase):
    """OGC API - Features: user landing page requirements."""

    def _get_landing(self) -> dict[str, Any]:
        resp = self.client.get(
            reverse(
                "api:v1:gis-ogc:user-landing",
                kwargs={"key": self.token.key},
            )
        )
        assert resp.status_code == status.HTTP_200_OK
        return resp.json()  # type: ignore[no-any-return]

    def test_landing_page_returns_200(self) -> None:
        self._get_landing()

    def test_landing_page_has_title(self) -> None:
        data = self._get_landing()
        assert "title" in data
        assert isinstance(data["title"], str)

    def test_landing_page_has_links(self) -> None:
        data = self._get_landing()
        assert "links" in data
        assert isinstance(data["links"], list)
        assert len(data["links"]) >= 3  # noqa: PLR2004

    def test_landing_page_has_self_link(self) -> None:
        data = self._get_landing()
        rels = {link["rel"] for link in data["links"]}
        assert "self" in rels

    def test_landing_page_has_conformance_link(self) -> None:
        data = self._get_landing()
        rels = {link["rel"] for link in data["links"]}
        assert "conformance" in rels

    def test_landing_page_has_data_link(self) -> None:
        data = self._get_landing()
        data_links = [link for link in data["links"] if link["rel"] == "data"]
        assert len(data_links) == 1
        assert data_links[0]["type"] == "application/json"

    def test_landing_page_has_service_desc_link(self) -> None:
        data = self._get_landing()
        rels = {link["rel"] for link in data["links"]}
        assert "service-desc" in rels

    def test_landing_page_all_links_have_required_fields(self) -> None:
        data = self._get_landing()
        for link in data["links"]:
            assert "href" in link, f"Link missing href: {link}"
            assert "rel" in link, f"Link missing rel: {link}"
            assert "type" in link, f"Link missing type: {link}"


@pytest.mark.django_db
class TestOGCUserConformance(BaseOGCUserTestCase):
    """OGC API - Features: user conformance declaration requirements."""

    def _get_conformance(self) -> dict[str, Any]:
        resp = self.client.get(
            reverse(
                "api:v1:gis-ogc:user-conformance",
                kwargs={"key": self.token.key},
            )
        )
        assert resp.status_code == status.HTTP_200_OK
        return resp.json()  # type: ignore[no-any-return]

    def test_conformance_returns_200(self) -> None:
        self._get_conformance()

    def test_conformance_has_conforms_to(self) -> None:
        data = self._get_conformance()
        assert "conformsTo" in data
        assert isinstance(data["conformsTo"], list)

    def test_conformance_declares_core(self) -> None:
        data = self._get_conformance()
        assert (
            "http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/core"
            in data["conformsTo"]
        )

    def test_conformance_declares_geojson(self) -> None:
        data = self._get_conformance()
        assert (
            "http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/geojson"
            in data["conformsTo"]
        )

    def test_conformance_does_not_declare_filtering(self) -> None:
        data = self._get_conformance()
        for cls in data["conformsTo"]:
            assert "filter" not in cls.lower()
            assert "cql" not in cls.lower()


@pytest.mark.django_db
class TestOGCUserDiscoveryFlow(BaseOGCUserTestCase):
    """End-to-end: follow the full QGIS-style discovery chain for user endpoints."""

    def test_full_discovery_chain(self) -> None:
        """Landing -> conformance -> collections -> collection -> items."""
        client = self.client
        key = self.token.key

        # 1. Landing page
        landing = client.get(
            reverse("api:v1:gis-ogc:user-landing", kwargs={"key": key})
        ).json()
        assert "links" in landing

        # 2. Follow rel:conformance
        conf_href = next(
            link["href"] for link in landing["links"] if link["rel"] == "conformance"
        )
        conf = client.get(conf_href).json()
        assert "conformsTo" in conf

        # 3. Follow rel:data -> collections
        data_href = next(
            link["href"] for link in landing["links"] if link["rel"] == "data"
        )
        collections = client.get(data_href).json()
        assert len(collections["collections"]) >= 1

        # 4. Follow collection self link -> single collection
        coll = collections["collections"][0]
        self_href = next(
            link["href"] for link in coll["links"] if link["rel"] == "self"
        )
        single = client.get(self_href).json()
        assert single["id"] == coll["id"]

        # 5. Follow items link -> GeoJSON
        items_href = next(
            link["href"] for link in single["links"] if link["rel"] == "items"
        )
        items_resp = client.get(items_href)
        assert items_resp.status_code == status.HTTP_200_OK
        assert "application/geo+json" in items_resp["Content-Type"]

        geojson = orjson.loads(b"".join(items_resp.streaming_content))  # type: ignore[attr-defined]
        assert geojson["type"] == "FeatureCollection"
        assert len(geojson["features"]) >= 1
