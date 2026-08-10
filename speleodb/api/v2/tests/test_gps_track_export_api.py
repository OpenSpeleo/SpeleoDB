# -*- coding: utf-8 -*-

from __future__ import annotations

import re
import uuid
from typing import TYPE_CHECKING
from typing import Any
from typing import cast

import gpxpy
import orjson
import pytest
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from parameterized.parameterized import parameterized
from rest_framework import status

from speleodb.api.v2.tests.base_testcase import BaseAPITestCase
from speleodb.api.v2.tests.factories import TokenFactory
from speleodb.common.enums import PermissionLevel
from speleodb.gis.models import GPSTrack
from speleodb.gis.models import GPSTrackUserPermission
from speleodb.users.tests.factories import UserFactory

if TYPE_CHECKING:
    from collections.abc import Iterable

    from speleodb.users.models import User


def _geojson_feature(
    geometry_type: str,
    coordinates: object,
) -> dict[str, object]:
    return {
        "type": "Feature",
        "geometry": {"type": geometry_type, "coordinates": coordinates},
        "properties": {},
    }


def _geojson_feature_collection(
    *features: dict[str, object],
) -> dict[str, object]:
    return {"type": "FeatureCollection", "features": list(features)}


def _create_gps_track(
    *,
    user: User,
    geojson: dict[str, object],
    name: str = "Export Track",
) -> GPSTrack:
    filename = f"{uuid.uuid4()}.geojson"
    uploaded_file = SimpleUploadedFile(
        filename,
        orjson.dumps(geojson),
        content_type="application/geo+json",
    )
    track = GPSTrack(user=user, name=name, color="#377eb8")
    track.file.save(filename, uploaded_file, save=False)
    track.save()
    return track


def _response_bytes(response: Any) -> bytes:
    return b"".join(cast("Iterable[bytes]", response.streaming_content))


@pytest.mark.django_db
class TestGPSTrackExportGPXAPI(BaseAPITestCase):
    def test_owner_exports_gpx_with_ordered_segments_and_elevation(self) -> None:
        geojson = _geojson_feature_collection(
            _geojson_feature(
                "LineString",
                [[-87.501234, 20.196710], [-87.502345, 20.197821, 8.25]],
            ),
            _geojson_feature(
                "MultiLineString",
                [
                    [[-87.6, 20.3, -1], [-87.61, 20.31, 0]],
                    [[-87.7, 20.4], [-87.71, 20.41]],
                ],
            ),
        )
        track = _create_gps_track(
            user=self.user,
            geojson=geojson,
            name="Cueva Águila & Norte",
        )
        track.file.open("rb")
        original_geojson = track.file.read()
        track.file.close()

        response = self.client.get(
            reverse("api:v2:gps-track-export-gpx", kwargs={"id": track.id}),
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response["Content-Type"] == "application/gpx+xml"
        assert re.fullmatch(
            r'attachment; filename="gps_track_Cueva Águila & Norte_'
            r'\d{4}-\d{2}-\d{2}\.gpx"',
            response["Content-Disposition"],
        )

        raw_gpx = _response_bytes(response).decode("utf-8")
        assert '<gpx xmlns="http://www.topografix.com/GPX/1/1"' in raw_gpx
        assert 'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"' in raw_gpx
        assert (
            'xsi:schemaLocation="http://www.topografix.com/GPX/1/1 '
            'http://www.topografix.com/GPX/1/1/gpx.xsd"'
        ) in raw_gpx
        assert 'version="1.1"' in raw_gpx
        assert 'creator="SpeleoDB"' in raw_gpx
        assert "gpx.py -- https://github.com/tkrajina/gpxpy" not in raw_gpx

        parsed = gpxpy.parse(raw_gpx)
        assert parsed.name == "Cueva Águila & Norte"
        assert len(parsed.tracks) == 1
        assert parsed.tracks[0].name == "Cueva Águila & Norte"
        assert [
            [
                (point.longitude, point.latitude, point.elevation)
                for point in segment.points
            ]
            for segment in parsed.tracks[0].segments
        ] == [
            [(-87.501234, 20.19671, None), (-87.502345, 20.197821, 8.25)],
            [(-87.6, 20.3, -1.0), (-87.61, 20.31, 0.0)],
            [(-87.7, 20.4, None), (-87.71, 20.41, None)],
        ]

        track.refresh_from_db()
        track.file.open("rb")
        assert track.file.read() == original_geojson
        track.file.close()

    def test_empty_feature_collection_exports_valid_named_empty_track(self) -> None:
        track = _create_gps_track(
            user=self.user,
            geojson=_geojson_feature_collection(),
            name="Empty Track",
        )

        response = self.client.get(
            reverse("api:v2:gps-track-export-gpx", kwargs={"id": track.id}),
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_200_OK
        parsed = gpxpy.parse(_response_bytes(response).decode("utf-8"))
        assert len(parsed.tracks) == 1
        assert parsed.tracks[0].name == "Empty Track"
        assert parsed.tracks[0].segments == []

    def test_unsupported_geometry_returns_explicit_bad_request(self) -> None:
        track = _create_gps_track(
            user=self.user,
            geojson=_geojson_feature_collection(
                _geojson_feature("Point", [-87.5, 20.1])
            ),
        )

        response = self.client.get(
            reverse("api:v2:gps-track-export-gpx", kwargs={"id": track.id}),
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data == {
            "error": (
                "GPS Track cannot be exported: Feature 0 has unsupported geometry "
                "type 'Point'. Only LineString and MultiLineString are supported."
            )
        }

    def test_malformed_stored_json_returns_explicit_bad_request(self) -> None:
        track = _create_gps_track(
            user=self.user,
            geojson=_geojson_feature_collection(),
        )

        stored_name = track.file.name
        assert stored_name is not None
        storage = track.file.storage
        storage.delete(stored_name)
        saved_name = storage.save(stored_name, ContentFile(b"{malformed"))
        assert saved_name == stored_name

        response = self.client.get(
            reverse("api:v2:gps-track-export-gpx", kwargs={"id": track.id}),
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["error"].startswith("GPS Track cannot be exported:")

    def test_export_requires_authentication(self) -> None:
        track = _create_gps_track(
            user=self.user,
            geojson=_geojson_feature_collection(),
        )

        response = self.client.get(
            reverse("api:v2:gps-track-export-gpx", kwargs={"id": track.id})
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_user_without_permission_cannot_export(self) -> None:
        other_user = UserFactory.create()
        track = _create_gps_track(
            user=other_user,
            geojson=_geojson_feature_collection(),
        )

        response = self.client.get(
            reverse("api:v2:gps-track-export-gpx", kwargs={"id": track.id}),
            headers={"authorization": self.auth},
        )

        assert response.status_code in {
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND,
        }

    @parameterized.expand(
        [
            PermissionLevel.READ_ONLY,
            PermissionLevel.READ_AND_WRITE,
            PermissionLevel.ADMIN,
        ],
    )
    def test_every_readable_permission_level_can_export(
        self,
        level: PermissionLevel,
    ) -> None:
        track = _create_gps_track(
            user=self.user,
            geojson=_geojson_feature_collection(),
        )
        collaborator = UserFactory.create()
        collaborator_token = TokenFactory.create(user=collaborator)
        GPSTrackUserPermission.objects.create(
            user=collaborator,
            gps_track=track,
            level=level,
        )

        response = self.client.get(
            reverse("api:v2:gps-track-export-gpx", kwargs={"id": track.id}),
            headers={"authorization": f"Token {collaborator_token.key}"},
        )

        assert response.status_code == status.HTTP_200_OK

    def test_revoked_permission_cannot_export(self) -> None:
        track = _create_gps_track(
            user=self.user,
            geojson=_geojson_feature_collection(),
        )
        collaborator = UserFactory.create()
        collaborator_token = TokenFactory.create(user=collaborator)
        permission = GPSTrackUserPermission.objects.create(
            user=collaborator,
            gps_track=track,
            level=PermissionLevel.READ_ONLY,
            is_active=False,
            deactivated_by=self.user,
        )

        response = self.client.get(
            reverse("api:v2:gps-track-export-gpx", kwargs={"id": track.id}),
            headers={"authorization": f"Token {collaborator_token.key}"},
        )

        assert permission.is_active is False
        assert response.status_code in {
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND,
        }

    def test_inactive_track_cannot_be_exported(self) -> None:
        track = _create_gps_track(
            user=self.user,
            geojson=_geojson_feature_collection(),
        )
        track.is_active = False
        track.save(update_fields=["is_active", "modified_date"])

        response = self.client.get(
            reverse("api:v2:gps-track-export-gpx", kwargs={"id": track.id}),
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_unknown_track_returns_not_found(self) -> None:
        response = self.client.get(
            reverse("api:v2:gps-track-export-gpx", kwargs={"id": uuid.uuid4()}),
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
