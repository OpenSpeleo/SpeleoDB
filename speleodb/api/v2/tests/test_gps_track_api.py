# -*- coding: utf-8 -*-

"""Tests for `gps-tracks` (list) and `gps-track-detail` (GET/PUT/PATCH/DELETE).

View lives in `speleodb/api/v2/views/gps_track.py`. GPSTrack is a private
per-user GeoJSON track (ownership permission).
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import orjson
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework import status

from speleodb.api.v2.tests.base_testcase import BaseAPITestCase
from speleodb.api.v2.tests.factories import TokenFactory
from speleodb.gis.models import GPSTrack
from speleodb.users.tests.factories import UserFactory

if TYPE_CHECKING:
    from speleodb.users.models import User


def _geojson_file(name: str = "track.geojson") -> SimpleUploadedFile:
    """Build a minimal valid FeatureCollection GeoJSON upload file."""
    return SimpleUploadedFile(
        name,
        orjson.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "geometry": {
                            "type": "LineString",
                            "coordinates": [
                                [-87.501234, 20.196710],
                                [-87.502345, 20.197821],
                            ],
                        },
                        "properties": {"name": "Test Trail"},
                    }
                ],
            }
        ),
        content_type="application/geo+json",
    )


def _create_gps_track(user: User, name: str = "My Track") -> GPSTrack:
    track = GPSTrack(user=user, name=name, color="#377eb8")
    track.file.save(f"{uuid.uuid4()}.geojson", _geojson_file(), save=False)
    track.save()
    return track


@pytest.mark.django_db
class TestGPSTrackList(BaseAPITestCase):
    """GET /api/v2/gps_tracks/ - returns current user's tracks only."""

    def test_requires_authentication(self) -> None:
        response = self.client.get(reverse("api:v2:gps-tracks"))
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_returns_only_own_tracks(self) -> None:
        _ = _create_gps_track(self.user, name="Mine")
        other_user = UserFactory.create()
        _ = _create_gps_track(other_user, name="Theirs")

        response = self.client.get(
            reverse("api:v2:gps-tracks"), headers={"authorization": self.auth}
        )
        assert response.status_code == status.HTTP_200_OK, response.data
        assert isinstance(response.data, list)
        names = [t["name"] for t in response.data]
        assert "Mine" in names
        assert "Theirs" not in names

    def test_empty_list(self) -> None:
        response = self.client.get(
            reverse("api:v2:gps-tracks"), headers={"authorization": self.auth}
        )
        assert response.status_code == status.HTTP_200_OK, response.data
        assert response.data == []


@pytest.mark.django_db
class TestGPSTrackDetailRead(BaseAPITestCase):
    """GET /api/v2/gps_tracks/<id>/ - owner only."""

    def test_owner_can_read(self) -> None:
        track = _create_gps_track(self.user, name="Readme")
        response = self.client.get(
            reverse("api:v2:gps-track-detail", kwargs={"id": track.id}),
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_200_OK, response.data
        assert response.data["id"] == str(track.id)
        assert response.data["name"] == "Readme"

    def test_stranger_gets_forbidden(self) -> None:
        other = UserFactory.create()
        track = _create_gps_track(other, name="Theirs")

        response = self.client.get(
            reverse("api:v2:gps-track-detail", kwargs={"id": track.id}),
            headers={"authorization": self.auth},
        )
        # The ownership permission enforces 403/404.
        assert response.status_code in (
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND,
        ), response.data

    def test_404_for_unknown_id(self) -> None:
        response = self.client.get(
            reverse("api:v2:gps-track-detail", kwargs={"id": uuid.uuid4()}),
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestGPSTrackDetailWrite(BaseAPITestCase):
    """PUT / PATCH / DELETE on detail endpoint."""

    def test_owner_can_patch_name(self) -> None:
        track = _create_gps_track(self.user, name="Old")
        response = self.client.patch(
            reverse("api:v2:gps-track-detail", kwargs={"id": track.id}),
            {"name": "New"},
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_200_OK, response.data
        track.refresh_from_db()
        assert track.name == "New"

    def test_owner_can_patch_color(self) -> None:
        track = _create_gps_track(self.user, name="With color")
        response = self.client.patch(
            reverse("api:v2:gps-track-detail", kwargs={"id": track.id}),
            {"color": "#e41a1c"},
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_200_OK, response.data
        track.refresh_from_db()
        assert track.color == "#e41a1c"

    def test_patch_rejects_invalid_color(self) -> None:
        track = _create_gps_track(self.user, name="Track")
        response = self.client.patch(
            reverse("api:v2:gps-track-detail", kwargs={"id": track.id}),
            {"color": "not-a-color"},
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.data
        assert "errors" in response.data

    def test_stranger_cannot_patch(self) -> None:
        other = UserFactory.create()
        track = _create_gps_track(other, name="Other's")
        response = self.client.patch(
            reverse("api:v2:gps-track-detail", kwargs={"id": track.id}),
            {"name": "Hacked"},
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code in (
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND,
        ), response.data

    def test_owner_can_delete(self) -> None:
        track = _create_gps_track(self.user, name="Delete me")
        track_id = track.id
        response = self.client.delete(
            reverse("api:v2:gps-track-detail", kwargs={"id": track_id}),
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_200_OK, response.data
        assert not GPSTrack.objects.filter(id=track_id).exists()

    def test_stranger_cannot_delete(self) -> None:
        other = UserFactory.create()
        track = _create_gps_track(other, name="Other's")
        response = self.client.delete(
            reverse("api:v2:gps-track-detail", kwargs={"id": track.id}),
            headers={"authorization": self.auth},
        )
        assert response.status_code in (
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND,
        ), response.data
        assert GPSTrack.objects.filter(id=track.id).exists()

    def test_detail_requires_authentication(self) -> None:
        track = _create_gps_track(self.user, name="Track")
        response = self.client.get(
            reverse("api:v2:gps-track-detail", kwargs={"id": track.id}),
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestGPSTrackPermissionMatrix(BaseAPITestCase):
    """Sanity matrix: owner vs stranger for every method."""

    def setUp(self) -> None:
        super().setUp()
        self.track = _create_gps_track(self.user, name="Mine")
        self.stranger = UserFactory.create()
        self.stranger_token = TokenFactory.create(user=self.stranger)
        self.stranger_auth = "Token " + self.stranger_token.key

    def test_owner_can_list_stranger_sees_empty(self) -> None:
        for auth in [self.auth, self.stranger_auth]:
            response = self.client.get(
                reverse("api:v2:gps-tracks"), headers={"authorization": auth}
            )
            assert response.status_code == status.HTTP_200_OK
            if auth == self.stranger_auth:
                assert response.data == []
            else:
                assert len(response.data) == 1

    def test_stranger_blocked_from_detail(self) -> None:
        response = self.client.get(
            reverse("api:v2:gps-track-detail", kwargs={"id": self.track.id}),
            headers={"authorization": self.stranger_auth},
        )
        assert response.status_code in (
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND,
        )
