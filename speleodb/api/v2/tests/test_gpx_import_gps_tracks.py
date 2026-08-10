"""GPS Track lifecycle assertions for the existing GPX import endpoint."""

from __future__ import annotations

from typing import TYPE_CHECKING

import orjson
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
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


@pytest.mark.django_db
def test_gpx_import_creates_owner_admin_and_keeps_duplicate_behavior() -> None:
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
    track = GPSTrack.objects.get(user=user)
    owner_permission = track.permissions.get(user=user)
    assert owner_permission.level == PermissionLevel.ADMIN
    assert owner_permission.is_active
    with track.file.open("rb") as stored_file:
        geojson = orjson.loads(stored_file.read())
    assert geojson["features"][0]["geometry"]["coordinates"] == [
        [-87.5001, 20.1001, 12],
        [-87.5002, 20.1002, 13],
    ]

    duplicate_response = import_track()

    assert duplicate_response.status_code == status.HTTP_200_OK
    assert duplicate_response.data["gps_tracks_created"] == 0
    assert GPSTrack.objects.filter(user=user, is_active=True).count() == 1
    assert track.permissions.count() == 1
