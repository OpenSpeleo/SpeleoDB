"""Protect session-authenticated uploads at the Django/storage boundary."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from django.test import Client
from django.urls import reverse
from rest_framework import status

from speleodb.gis.models import GISLayer
from speleodb.users.tests.factories import VerifiedUserFactory

if TYPE_CHECKING:
    from speleodb.users.models import User


@pytest.mark.django_db
def test_session_upload_requires_rendered_csrf_token() -> None:
    user: User = VerifiedUserFactory.create()
    client: Client = Client(enforce_csrf_checks=True)
    client.force_login(user)
    page = client.get(reverse("private:gis_layers"))
    assert page.status_code == status.HTTP_200_OK
    csrf_input = re.search(rb'name="csrfmiddlewaretoken" value="([^"]+)"', page.content)
    assert csrf_input is not None
    endpoint: str = reverse("api:v2:gis-layers")
    contents: bytes = b'{ "type": "FeatureCollection", "features": [] }\n'

    try:
        # DRF marks denied session requests for rollback; confine that expected
        # failure to a savepoint before checking state and submitting again.
        with transaction.atomic():
            rejected = client.post(
                endpoint,
                {
                    "name": "Rejected without CSRF",
                    "source_file": SimpleUploadedFile("layer.geojson", contents),
                },
            )
        assert rejected.status_code == status.HTTP_403_FORBIDDEN
        assert "CSRF" in rejected.json()["detail"]
        assert not GISLayer.objects.exists()

        accepted = client.post(
            endpoint,
            {
                "name": "Session upload",
                "source_file": SimpleUploadedFile("layer.geojson", contents),
            },
            headers={"x-csrftoken": csrf_input.group(1).decode()},
        )
        assert accepted.status_code == status.HTTP_201_CREATED
        layer: GISLayer = GISLayer.objects.get()
        assert str(layer.id) == accepted.json()["id"]
        assert layer.created_by == user.email
        assert layer.name == "Session upload"
        assert layer.source_f.name == layer.data_f.name
        # This reads back from the configured real S3-compatible service.
        with layer.source_f.open("rb") as stored_file:
            assert stored_file.read() == contents
    finally:
        deleted_files: set[tuple[int, str]] = set()
        for layer in GISLayer.objects.filter(created_by=user.email):
            for field in (layer.source_f, layer.data_f):
                if field.name:
                    stored_file_key: tuple[int, str] = (id(field.storage), field.name)
                    if stored_file_key not in deleted_files:
                        field.delete(save=False)
                        deleted_files.add(stored_file_key)
