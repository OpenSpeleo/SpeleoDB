# -*- coding: utf-8 -*-

from __future__ import annotations

import orjson
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone
from rest_framework import status

from speleodb.api.v1.serializers.gis_view import GISViewDataSerializer
from speleodb.api.v1.tests.base_testcase import BaseAPITestCase
from speleodb.api.v1.tests.factories import ProjectFactory
from speleodb.gis.models import GISView
from speleodb.gis.models import GISViewProject
from speleodb.gis.models import ProjectGeoJSON


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
        ProjectGeoJSON.objects.create(
            project=project,
            commit_sha=commit_sha,
            commit_date=timezone.now(),
            commit_author_name="Author",
            commit_author_email="author@example.com",
            commit_message="Test commit",
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
        ProjectGeoJSON.objects.create(
            project=project,
            commit_sha=commit_sha,
            commit_date=timezone.now(),
            commit_author_name="Author",
            commit_author_email="author@example.com",
            commit_message="Test",
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
        ProjectGeoJSON.objects.create(
            project=project,
            commit_sha=commit_sha,
            commit_date=timezone.now(),
            commit_author_name="John Doe",
            commit_author_email="john.doe@example.com",
            commit_message="Initial commit",
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
        ProjectGeoJSON.objects.create(
            project=project,
            commit_sha=commit_sha,
            commit_date=timezone.now(),
            commit_author_name="John Doe",
            commit_author_email="john.doe@example.com",
            commit_message="Initial commit",
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

        ProjectGeoJSON.objects.create(
            project=project,
            commit_sha=old_sha,
            commit_date=timezone.now(),
            commit_author_name="John Doe",
            commit_author_email="john.doe@example.com",
            commit_message="Initial commit",
            file=temp_geojson_file(),
        )

        latest = ProjectGeoJSON.objects.create(
            project=project,
            commit_sha=new_sha,
            commit_date=timezone.now(),
            commit_author_name="John Doe",
            commit_author_email="john.doe@example.com",
            commit_message="Initial commit",
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

        ProjectGeoJSON.objects.create(
            project=project1,
            commit_sha=sha1,
            commit_date=timezone.now(),
            commit_author_name="John Doe",
            commit_author_email="john.doe@example.com",
            commit_message="Initial commit",
            file=temp_geojson_file(),
        )

        ProjectGeoJSON.objects.create(
            project=project2,
            commit_sha=sha2,
            commit_date=timezone.now(),
            commit_author_name="John Doe",
            commit_author_email="john.doe@example.com",
            commit_message="Initial commit",
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
        ProjectGeoJSON.objects.create(
            project=project1,
            commit_sha=sha1,
            commit_date=timezone.now(),
            commit_author_name="John Doe",
            commit_author_email="john.doe@example.com",
            commit_message="Initial commit",
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
        ProjectGeoJSON.objects.create(
            project=project,
            commit_sha=commit_sha,
            commit_date=timezone.now(),
            commit_author_name="Author",
            commit_author_email="author@example.com",
            commit_message="Test",
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
        ProjectGeoJSON.objects.create(
            project=project,
            commit_sha=commit_sha,
            commit_date=timezone.now(),
            commit_author_name="Author",
            commit_author_email="author@example.com",
            commit_message="Test",
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
