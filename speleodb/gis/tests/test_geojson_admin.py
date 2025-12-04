from __future__ import annotations

import json
from typing import Any

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone
from rest_framework import status

from speleodb.api.v1.tests.test_project_geojson_commits_api import sha1_hash
from speleodb.gis.models import ProjectGeoJSON
from speleodb.surveys.models import Project
from speleodb.surveys.models import ProjectCommit
from speleodb.users.models import User


@pytest.fixture
def user(db: None) -> User:
    return User.objects.create_user(email="admin@test.org", password="x")  # noqa: S106


@pytest.fixture
def admin_client(client: Any, admin_user: User) -> Any:  # built-in fixture admin_user
    client.force_login(admin_user)
    return client


@pytest.fixture
def project(db: None, user: User) -> Project:
    return Project.objects.create(
        name="Geo Admin",
        description="d",
        country="US",
        created_by=user.email,
    )


@pytest.mark.django_db
def test_admin_list_geojson(admin_client: Any, project: Project) -> None:
    """Test that the admin list view works for ProjectGeoJSON."""
    # Create a ProjectCommit first
    commit_sha = sha1_hash()
    commit = ProjectCommit.objects.create(
        id=commit_sha,
        project=project,
        author_name="John Doe",
        author_email="john.doe@example.com",
        authored_date=timezone.now(),
        message="Initial commit",
    )

    # Create the ProjectGeoJSON
    ProjectGeoJSON.objects.create(
        commit=commit,
        project=project,
        file=SimpleUploadedFile(
            "map.geojson",
            json.dumps({"type": "FeatureCollection", "features": []}).encode(),
            content_type="application/geo+json",
        ),
    )

    # Verify the list view works
    url = reverse("admin:gis_projectgeojson_changelist")
    resp = admin_client.get(url)
    assert resp.status_code == status.HTTP_200_OK
    assert ProjectGeoJSON.objects.filter(commit=commit_sha).count() == 1


@pytest.mark.django_db
def test_admin_view_form(admin_client: Any, project: Project) -> None:
    """Test that the admin change view works for viewing a ProjectGeoJSON."""
    # Create a ProjectCommit first
    commit_sha = sha1_hash()
    commit = ProjectCommit.objects.create(
        id=commit_sha,
        project=project,
        author_name="John Doe",
        author_email="john.doe@example.com",
        authored_date=timezone.now(),
        message="Initial commit",
    )

    obj = ProjectGeoJSON.objects.create(
        commit=commit,
        project=project,
        file=SimpleUploadedFile(
            "map.geojson",
            json.dumps({"type": "FeatureCollection", "features": []}).encode(),
        ),
    )
    url = reverse("admin:gis_projectgeojson_change", args=[obj.pk])
    resp = admin_client.get(url)
    assert resp.status_code == status.HTTP_200_OK
