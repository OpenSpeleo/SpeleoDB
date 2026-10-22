"""Persistence contracts behind the resource editor's multipart PATCH form."""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from speleodb.api.v2.tests.factories import SurfaceMonitoringNetworkFactory
from speleodb.api.v2.tests.factories import (
    SurfaceMonitoringNetworkUserPermissionFactory,
)
from speleodb.api.v2.tests.factories import SurfaceStationFactory
from speleodb.api.v2.tests.file_utils import sha256_from_url
from speleodb.common.enums import PermissionLevel
from speleodb.common.enums import StationResourceType
from speleodb.gis.models import StationResource

if TYPE_CHECKING:
    from speleodb.users.models import User


@pytest.mark.django_db
@pytest.mark.parametrize(
    "resource_type", [StationResourceType.NOTE, StationResourceType.DOCUMENT]
)
def test_multipart_edit_preserves_type_and_persists_replacement_content(
    user: User, resource_type: StationResourceType
) -> None:
    network = SurfaceMonitoringNetworkFactory.create(created_by=user.email)
    SurfaceMonitoringNetworkUserPermissionFactory.create(
        network=network, user=user, level=PermissionLevel.READ_AND_WRITE
    )
    station = SurfaceStationFactory.create(network=network, created_by=user.email)
    resource = StationResource(
        station=station,
        resource_type=resource_type,
        title="Original title",
        description="Original description",
        text_content="Original note"
        if resource_type == StationResourceType.NOTE
        else "",
        created_by=user.email,
    )
    replacement = "Replacement café 🦇".encode()
    if resource_type == StationResourceType.DOCUMENT:
        resource.file = SimpleUploadedFile(
            "original.txt", b"Original document", content_type="text/plain"
        )
    resource.save()
    original_file = resource.file.name
    storage = resource.file.storage
    payload: dict[str, str | SimpleUploadedFile] = {
        "title": "Updated title",
        "description": "",
    }
    if resource_type == StationResourceType.NOTE:
        payload["text_content"] = "Updated note café 🦇"
    else:
        payload["file"] = SimpleUploadedFile(
            "replacement.txt", replacement, content_type="text/plain"
        )
    client = APIClient()
    client.force_authenticate(user=user)
    url = reverse("api:v2:resource-detail", kwargs={"id": resource.id})
    try:
        # A disabled select contributes no resource_type field to a browser form.
        response = client.patch(url, payload, format="multipart")
        assert response.status_code == status.HTTP_200_OK
        resource.refresh_from_db()
        assert resource.title == "Updated title"
        assert resource.description == ""
        assert resource.resource_type == resource_type
        detail = client.get(url)
        assert detail.status_code == status.HTTP_200_OK
        assert detail.data["title"] == resource.title
        assert detail.data["description"] == ""
        assert detail.data["resource_type"] == resource_type
        if resource_type == StationResourceType.NOTE:
            # The model normalizes accented text while retaining other Unicode.
            assert resource.text_content == "Updated note cafe 🦇"
            assert detail.data["text_content"] == resource.text_content
            assert detail.data["file"] is None
        else:
            assert resource.file.name != original_file
            with resource.file.open("rb") as stored:
                assert stored.read() == replacement
            assert (
                sha256_from_url(detail.data["file"])
                == hashlib.sha256(replacement).hexdigest()
            )
    finally:
        # Replacement retains the original object; clean up both fixture-owned keys.
        resource.refresh_from_db()
        for key in {original_file, resource.file.name}:
            if key:
                storage.delete(key)
