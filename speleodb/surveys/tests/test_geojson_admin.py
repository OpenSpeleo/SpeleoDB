from __future__ import annotations

import json
from typing import Any

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework import status

from speleodb.surveys.models import GeoJSON
from speleodb.surveys.models import Project
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
        name="Geo Admin", description="d", country="US", created_by=user
    )


@pytest.mark.django_db
def test_admin_create_geojson(admin_client: Any, project: Project) -> None:
    url = reverse("admin:surveys_geojson_add")
    valid = json.dumps({"type": "FeatureCollection", "features": []}).encode()
    upload = SimpleUploadedFile(
        "map.geojson", valid, content_type="application/geo+json"
    )

    resp = admin_client.post(
        url,
        data={
            "project": project.id,
            "commit_sha": "f" * 40,
            "file": upload,
        },
        follow=True,
    )
    assert resp.status_code == status.HTTP_200_OK
    assert GeoJSON.objects.filter(commit_sha="f" * 40).exists()


@pytest.mark.django_db
def test_admin_view_form(admin_client: Any, project: Project) -> None:
    obj = GeoJSON.objects.create(
        project=project,
        commit_sha="1" * 40,
        file=SimpleUploadedFile(
            "map.geojson",
            json.dumps({"type": "FeatureCollection", "features": []}).encode(),
        ),
    )
    url = reverse("admin:surveys_geojson_change", args=[obj.id])
    resp = admin_client.get(url)
    assert resp.status_code == status.HTTP_200_OK
