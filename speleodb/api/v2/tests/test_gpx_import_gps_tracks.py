"""GPS Track lifecycle assertions for the existing GPX import endpoint."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import orjson
import pytest
from django.core.files.storage import InMemoryStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from speleodb.common.enums import PermissionLevel
from speleodb.gis.models import GPSTrack
from speleodb.users.tests.factories import UserFactory

if TYPE_CHECKING:
    from rest_framework.response import Response

GPX_TRACK = b"""<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="SpeleoDB" xmlns="http://www.topografix.com/GPX/1/1">
  <trk>
    <name>Imported Track</name>
    <trkseg>
      <trkpt lat="20.1001" lon="-87.5001"><ele>12.75</ele></trkpt>
      <trkpt lat="20.1002" lon="-87.5002"><ele>13.25</ele></trkpt>
    </trkseg>
  </trk>
</gpx>
"""
EXPECTED_REIMPORTED_TRACKS = 2


@pytest.mark.django_db
def test_gpx_import_creates_owner_admin_for_each_import() -> None:
    user = UserFactory.create()
    client = APIClient()
    client.force_authenticate(user=user)

    def import_track() -> Response:
        return client.put(
            reverse("api:v2:gpx-import"),
            {"file": SimpleUploadedFile("track.gpx", GPX_TRACK)},
            format="multipart",
        )

    first_response = import_track()

    assert first_response.status_code == status.HTTP_200_OK
    assert first_response.data["gps_tracks_created"] == 1
    track = GPSTrack.objects.get(created_by=user.email)
    creator_permission = track.permissions.get(user=user)
    assert creator_permission.level == PermissionLevel.ADMIN
    assert creator_permission.is_active
    with track.file.open("rb") as stored_file:
        geojson = orjson.loads(stored_file.read())
    assert geojson["features"][0]["geometry"]["coordinates"] == [
        [-87.5001, 20.1001, 12],
        [-87.5002, 20.1002, 13],
    ]

    duplicate_response = import_track()

    assert duplicate_response.status_code == status.HTTP_200_OK
    assert duplicate_response.data["gps_tracks_created"] == 1
    assert (
        GPSTrack.objects.filter(created_by=user.email, is_active=True).count()
        == EXPECTED_REIMPORTED_TRACKS
    )
    assert track.permissions.count() == 1


@pytest.mark.django_db
@override_settings(DEBUG=False)
def test_gpx_import_cleans_stored_track_when_publication_rolls_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = UserFactory.create()
    client = APIClient()
    client.force_authenticate(user=user)
    storage = InMemoryStorage()
    monkeypatch.setattr(GPSTrack._meta.get_field("file"), "storage", storage)  # noqa: SLF001

    with patch(
        "speleodb.api.v2.views.gpx_import.GPSTrackUserPermission.objects.create",
        side_effect=RuntimeError("permission insert failed"),
    ):
        response = client.put(
            reverse("api:v2:gpx-import"),
            {"file": SimpleUploadedFile("track.gpx", GPX_TRACK)},
            format="multipart",
        )

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert not GPSTrack.objects.exists()
    directories, files = storage.listdir("")
    assert directories == []
    assert files == []
