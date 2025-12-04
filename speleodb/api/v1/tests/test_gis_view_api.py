# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import TYPE_CHECKING

import orjson
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone
from rest_framework import status

from speleodb.api.v1.serializers.gis_view import GISViewDataSerializer
from speleodb.api.v1.serializers.gis_view import PublicGISViewProjectSerializer
from speleodb.api.v1.serializers.gis_view import PublicGISViewSerializer
from speleodb.api.v1.tests.base_testcase import BaseAPITestCase
from speleodb.api.v1.tests.factories import ProjectFactory
from speleodb.gis.models import GISView
from speleodb.gis.models import GISViewProject
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
            owner=self.user,
        )

        serializer = GISViewDataSerializer(gis_view, context={"expires_in": 3600})
        data = serializer.data

        assert "view_id" in data
        assert "view_name" in data
        assert "description" in data
        assert "geojson_files" in data
        assert data["view_name"] == "Test View"
        assert data["description"] == "Test description"
        assert isinstance(data["geojson_files"], list)

    def test_serializer_with_geojson_files(self) -> None:
        """Test serializer includes GeoJSON file data."""

        project = ProjectFactory.create()
        gis_view = GISView.objects.create(
            name="Test View",
            owner=self.user,
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

        GISViewProject.objects.create(
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

        GISViewProject.objects.create(
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
        GISViewProject.objects.create(
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

        assert len(data.get("links", [])) == 4  # noqa: PLR2004
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

        GISViewProject.objects.create(
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

        GISViewProject.objects.create(
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

        GISViewProject.objects.create(
            gis_view=gis_view,
            project=project1,
            commit_sha=sha1,
        )

        GISViewProject.objects.create(
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
        GISViewProject.objects.create(
            gis_view=gis_view,
            project=project1,
            commit_sha=sha1,
        )

        GISViewProject.objects.create(
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

        GISViewProject.objects.create(
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
        assert "geojson_files" in response_data

        # Verify values
        assert response_data["view_name"] == "Test View"
        assert response_data["description"] == "Test description"

        # Verify types
        assert isinstance(response_data["view_id"], str)
        assert isinstance(response_data["view_name"], str)
        assert isinstance(response_data["description"], str)
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

        GISViewProject.objects.create(
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
class TestPublicGISViewProjectSerializer(BaseAPITestCase):
    """Test PublicGISViewProjectSerializer."""

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

        serializer = PublicGISViewProjectSerializer(data)
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

        serializer = PublicGISViewProjectSerializer(data)
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

        serializer = PublicGISViewProjectSerializer(projects_data, many=True)  # type: ignore[arg-type]
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
            owner=self.user,
        )

        serializer = PublicGISViewSerializer(gis_view, context={"expires_in": 3600})
        data = serializer.data

        assert "view_name" in data
        assert "view_description" in data
        assert "projects" in data
        assert data["view_name"] == "Public Test View"
        assert data["view_description"] == "A view for public access"
        assert isinstance(data["projects"], list)

    def test_serializer_with_projects(self) -> None:
        """Test serializer includes project data correctly."""
        project = ProjectFactory.create()
        gis_view = GISView.objects.create(
            name="View With Projects",
            description="Has projects",
            owner=self.user,
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

        GISViewProject.objects.create(
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

        GISViewProject.objects.create(
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

        GISViewProject.objects.create(
            gis_view=gis_view,
            project=project1,
            commit_sha=sha1,
        )

        GISViewProject.objects.create(
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

        GISViewProject.objects.create(
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

        GISViewProject.objects.create(
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

        GISViewProject.objects.create(
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
        assert "projects" in data

        # Verify values
        assert data["view_name"] == "Structure Test View"
        assert data["view_description"] == "Testing structure"
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

        GISViewProject.objects.create(
            gis_view=gis_view,
            project=project1,
            commit_sha=sha1,
        )

        GISViewProject.objects.create(
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

        GISViewProject.objects.create(
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
        GISViewProject.objects.create(
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

        GISViewProject.objects.create(
            gis_view=gis_view,
            project=project1,
            commit_sha=sha1,
        )

        GISViewProject.objects.create(
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

        GISViewProject.objects.create(
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

        GISViewProject.objects.create(
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

        GISViewProject.objects.create(
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
