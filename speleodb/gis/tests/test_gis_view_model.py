# -*- coding: utf-8 -*-

from __future__ import annotations

import orjson
import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from speleodb.api.v1.tests.factories import ProjectFactory
from speleodb.gis.models import GISView
from speleodb.gis.models import GISViewProject
from speleodb.gis.models import ProjectGeoJSON
from speleodb.users.tests.factories import UserFactory


def temp_geojson_file() -> SimpleUploadedFile:
    """Create a temporary GeoJSON file for testing."""
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
class TestGISViewModel:
    """Test suite for GISView model."""

    def test_create_gis_view(self) -> None:
        """Test creating a basic GIS view."""
        user = UserFactory.create()
        gis_view = GISView.objects.create(
            name="Test View",
            description="A test GIS view",
            owner=user,
        )

        assert gis_view.id is not None
        assert gis_view.gis_token is not None
        assert len(gis_view.gis_token) == 40  # noqa: PLR2004
        assert str(gis_view) == f"Test View ({gis_view.gis_token[:8]}...)"

    def test_token_is_unique(self) -> None:
        """Test that tokens are unique across GIS views."""
        user = UserFactory.create()
        view1 = GISView.objects.create(
            name="View 1",
            owner=user,
        )
        view2 = GISView.objects.create(
            name="View 2",
            owner=user,
        )

        assert view1.gis_token != view2.gis_token

    def test_regenerate_token(self) -> None:
        """Test token regeneration."""
        user = UserFactory.create()
        gis_view = GISView.objects.create(
            name="Test View",
            owner=user,
        )

        old_token = gis_view.gis_token
        gis_view.regenerate_token()

        assert gis_view.gis_token != old_token
        assert len(gis_view.gis_token) == 40  # noqa: PLR2004


@pytest.mark.django_db
class TestGISViewProjectModel:
    """Test suite for GISViewProject model."""

    def test_create_view_project_with_commit(self) -> None:
        """Test creating a view project with specific commit."""
        user = UserFactory.create()
        project = ProjectFactory.create()
        gis_view = GISView.objects.create(
            name="Test View",
            owner=user,
        )

        view_project = GISViewProject.objects.create(
            gis_view=gis_view,
            project=project,
            commit_sha="a" * 40,
            use_latest=False,
        )

        assert view_project.commit_sha == "a" * 40
        assert view_project.use_latest is False

    def test_create_view_project_with_latest(self) -> None:
        """Test creating a view project using latest commit."""
        user = UserFactory.create()
        project = ProjectFactory.create()
        gis_view = GISView.objects.create(
            name="Test View",
            owner=user,
        )

        view_project = GISViewProject.objects.create(
            gis_view=gis_view,
            project=project,
            use_latest=True,
        )

        assert view_project.use_latest is True
        assert not view_project.commit_sha  # Should be cleared/empty

    def test_unique_project_per_view(self) -> None:
        """Test that a project can only be added once to a view."""
        user = UserFactory.create()
        project = ProjectFactory.create()
        gis_view = GISView.objects.create(
            name="Test View",
            owner=user,
        )

        GISViewProject.objects.create(
            gis_view=gis_view,
            project=project,
            use_latest=True,
        )

        # Try to add same project again
        # Note: ValidationError is raised by full_clean() before IntegrityError
        with pytest.raises(ValidationError):
            GISViewProject.objects.create(
                gis_view=gis_view,
                project=project,
                commit_sha="b" * 40,
            )

    def test_commit_sha_validation_length(self) -> None:
        """Test that commit SHA must be 40 characters."""
        user = UserFactory.create()
        project = ProjectFactory.create()
        gis_view = GISView.objects.create(
            name="Test View",
            owner=user,
        )

        view_project = GISViewProject(
            gis_view=gis_view,
            project=project,
            commit_sha="abc123",  # Too short
            use_latest=False,
        )

        with pytest.raises(ValidationError) as exc_info:
            view_project.save()

        assert "commit_sha" in str(exc_info.value)

    def test_commit_sha_validation_hex(self) -> None:
        """Test that commit SHA must be hexadecimal."""
        user = UserFactory.create()
        project = ProjectFactory.create()
        gis_view = GISView.objects.create(
            name="Test View",
            owner=user,
        )

        view_project = GISViewProject(
            gis_view=gis_view,
            project=project,
            commit_sha="z" * 40,  # Invalid hex
            use_latest=False,
        )
        with pytest.raises(ValidationError) as exc_info:
            view_project.save()

        assert "commit_sha" in str(exc_info.value)

    def test_must_specify_commit_or_latest(self) -> None:
        """Test that either use_latest or commit_sha must be set."""
        user = UserFactory.create()
        project = ProjectFactory.create()
        gis_view = GISView.objects.create(
            name="Test View",
            owner=user,
        )

        view_project = GISViewProject(
            gis_view=gis_view,
            project=project,
            use_latest=False,
            commit_sha="",
        )
        with pytest.raises(ValidationError):
            view_project.save()

    def test_use_latest_clears_commit_sha(self) -> None:
        """Test that use_latest=True clears commit_sha."""
        user = UserFactory.create()
        project = ProjectFactory.create()
        gis_view = GISView.objects.create(
            name="Test View",
            owner=user,
        )

        view_project = GISViewProject(
            gis_view=gis_view,
            project=project,
            commit_sha="a" * 40,
            use_latest=True,
        )
        view_project.save()

        assert view_project.use_latest is True
        assert not view_project.commit_sha  # Should be cleared


@pytest.mark.django_db
class TestGISViewIntegration:
    """Integration tests for GIS view functionality."""

    def test_get_geojson_urls_with_specific_commits(self) -> None:
        """Test getting GeoJSON URLs with specific commits."""
        user = UserFactory.create()
        project = ProjectFactory.create()
        gis_view = GISView.objects.create(
            name="Test View",
            owner=user,
        )

        # Create a GeoJSON for the project
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

        # Add project to view
        GISViewProject.objects.create(
            gis_view=gis_view,
            project=project,
            commit_sha=commit_sha,
        )

        # Get URLs
        urls = gis_view.get_geojson_urls()

        assert len(urls) == 1
        assert urls[0]["project_id"] == str(project.id)
        assert urls[0]["commit_sha"] == commit_sha
        assert "url" in urls[0]

    def test_get_geojson_urls_with_latest(self) -> None:
        """Test getting GeoJSON URLs using latest commit."""
        user = UserFactory.create()
        project = ProjectFactory.create()
        gis_view = GISView.objects.create(
            name="Test View",
            owner=user,
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

        latest_geojson = ProjectGeoJSON.objects.create(
            project=project,
            commit_sha=new_sha,
            commit_date=timezone.now(),
            commit_author_name="John Doe",
            commit_author_email="john.doe@example.com",
            commit_message="Initial commit",
            file=temp_geojson_file(),
        )

        # Add project to view with use_latest
        GISViewProject.objects.create(
            gis_view=gis_view,
            project=project,
            use_latest=True,
        )

        # Get URLs
        urls = gis_view.get_geojson_urls()

        assert len(urls) == 1
        assert urls[0]["commit_sha"] == latest_geojson.commit_sha
        assert urls[0]["use_latest"] is True

    def test_get_geojson_urls_skips_missing_commits(self) -> None:
        """Test that missing GeoJSONs are skipped gracefully."""
        user = UserFactory.create()
        project = ProjectFactory.create()
        gis_view = GISView.objects.create(
            name="Test View",
            owner=user,
        )

        # Add project with non-existent commit
        GISViewProject.objects.create(
            gis_view=gis_view,
            project=project,
            commit_sha="a" * 40,  # Doesn't exist
        )

        # Get URLs - should return empty list
        urls = gis_view.get_geojson_urls()
        assert len(urls) == 0

    def test_get_geojson_urls_multiple_projects(self) -> None:
        """Test getting URLs for multiple projects."""
        user = UserFactory.create()

        project1 = ProjectFactory.create()
        project2 = ProjectFactory.create()

        geojson_objs = [
            ProjectGeoJSON.objects.create(
                project=project1,
                commit_sha="a" * 40,
                commit_date=timezone.now(),
                commit_author_name="John Doe",
                commit_author_email="john.doe@example.com",
                commit_message="Initial commit",
                file=temp_geojson_file(),
            ),
            ProjectGeoJSON.objects.create(
                project=project2,
                commit_sha="b" * 40,
                commit_date=timezone.now(),
                commit_author_name="John Doe",
                commit_author_email="john.doe@example.com",
                commit_message="Initial commit",
                file=temp_geojson_file(),
            ),
        ]

        gis_view = GISView.objects.create(
            name="Test View",
            owner=user,
        )

        # Add both projects
        GISViewProject.objects.create(
            gis_view=gis_view,
            project=geojson_objs[0].project,
            commit_sha=geojson_objs[0].commit_sha,
        )

        GISViewProject.objects.create(
            gis_view=gis_view,
            project=geojson_objs[1].project,
            use_latest=True,
        )

        # Get URLs
        urls = gis_view.get_geojson_urls()

        assert len(urls) == len(geojson_objs)
        project_ids = {url["project_id"] for url in urls}

        assert str(geojson_objs[0].project.id) in project_ids
        assert str(geojson_objs[1].project.id) in project_ids
