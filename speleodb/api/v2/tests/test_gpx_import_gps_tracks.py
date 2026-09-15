"""GPX publication and rollback through real SQL and configured object storage."""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

import orjson
from allauth.account.models import EmailAddress
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.db import models
from django.db.utils import IntegrityError
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from speleodb.api.v2.tests.database_constraints import unique_import_names
from speleodb.api.v2.tests.factories import TokenFactory
from speleodb.api.v2.tests.test_file_upload_error_handling import SentryEventTestCase
from speleodb.common.enums import PermissionLevel
from speleodb.gis.models import GPSTrack
from speleodb.gis.models import GPSTrackUserPermission
from speleodb.users.tests.factories import UserFactory
from speleodb.utils.s3_storages import GPSTrackStorage

if TYPE_CHECKING:
    from rest_framework.response import Response

    from speleodb.users.models import User

GPX_TRACK: bytes = b"""<?xml version="1.0" encoding="UTF-8"?>
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
EXPECTED_REIMPORTED_TRACKS: int = 2


class GPXTrackPublicationTests(SentryEventTestCase):
    client: APIClient
    user: User
    auth: str
    storage: GPSTrackStorage
    original_files: set[str]

    def setUp(self) -> None:
        super().setUp()
        self.user = UserFactory.create()
        token = TokenFactory.create(user=self.user)
        EmailAddress.objects.create(
            user=self.user, email=self.user.email, verified=True, primary=True
        )
        self.client = APIClient()
        self.auth = f"Token {token.key}"
        field = GPSTrack._meta.get_field("file")  # noqa: SLF001
        assert isinstance(field, models.FileField)
        assert isinstance(field.storage, GPSTrackStorage)
        self.storage = field.storage
        self.original_files = set(self.storage.listdir("")[1])
        self.addCleanup(self._delete_test_files)

    def _delete_test_files(self) -> None:
        for name in set(self.storage.listdir("")[1]) - self.original_files:
            self.storage.delete(name)

    def _import(self, content: bytes = GPX_TRACK) -> Response:
        return self.client.put(
            reverse("api:v2:gpx-import"),
            {"file": SimpleUploadedFile("track.gpx", content)},
            format="multipart",
            headers={"authorization": self.auth},
        )

    def test_gpx_import_creates_owner_admin_for_each_import(self) -> None:
        first_response: Response = self._import()

        assert first_response.status_code == status.HTTP_200_OK
        assert first_response.data["gps_tracks_created"] == 1
        track: GPSTrack = GPSTrack.objects.get(created_by=self.user.email)
        creator_permission = track.permissions.get(user=self.user)
        assert creator_permission.level == PermissionLevel.ADMIN
        assert creator_permission.is_active
        with track.file.open("rb") as stored_file:
            geojson = orjson.loads(stored_file.read())
        assert geojson["features"][0]["geometry"]["coordinates"] == [
            [-87.5001, 20.1001, 12],
            [-87.5002, 20.1002, 13],
        ]

        duplicate_response: Response = self._import()

        assert duplicate_response.status_code == status.HTTP_200_OK
        assert duplicate_response.data["gps_tracks_created"] == 1
        assert (
            GPSTrack.objects.filter(created_by=self.user.email, is_active=True).count()
            == EXPECTED_REIMPORTED_TRACKS
        )
        assert track.permissions.count() == 1
        assert not self.sentry_events

    def test_gpx_import_cleans_stored_tracks_when_publication_rolls_back(self) -> None:
        assert not connection.in_atomic_block
        # A successful request proves authentication, storage and permissions work.
        assert self._import().status_code == status.HTTP_200_OK
        original_ids = set(GPSTrack.objects.values_list("id", flat=True))
        original_permissions = set(
            GPSTrackUserPermission.objects.values_list("id", flat=True)
        )
        stored_before: set[str] = set(self.storage.listdir("")[1])
        uploads: list[int] = []
        deletions: list[int] = []

        # Native SDK events observe completed real requests; the client and its
        # transport remain unchanged. Both objects must actually reach storage.
        def record_upload(parsed: dict[str, Any], **kwargs: Any) -> None:
            uploads.append(parsed["ResponseMetadata"]["HTTPStatusCode"])

        def record_delete(parsed: dict[str, Any], **kwargs: Any) -> None:
            deletions.append(parsed["ResponseMetadata"]["HTTPStatusCode"])

        events = self.storage.connection.meta.client.meta.events
        events.register("after-call.s3.PutObject", record_upload)
        events.register("after-call.s3.DeleteObject", record_delete)
        self.addCleanup(events.unregister, "after-call.s3.PutObject", record_upload)
        self.addCleanup(events.unregister, "after-call.s3.DeleteObject", record_delete)

        second_track: bytes = GPX_TRACK.split(b"<trk>", 1)[1].split(b"</trk>", 1)[0]
        content: bytes = GPX_TRACK.replace(
            b"</gpx>", b"<trk>" + second_track + b"</trk></gpx>"
        ).replace(b"Imported Track", b"Duplicate rollback track")
        with (
            unique_import_names(GPSTrack, created_by=self.user.email),
            self.assertLogs("speleodb.api.v2.views.gpx_import", level="ERROR"),
        ):
            response: Response = self._import(content)

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        exception: BaseException = self._reported_exception()
        assert isinstance(exception, IntegrityError), exception
        assert "unique" in str(exception).lower()
        assert uploads == [status.HTTP_200_OK, status.HTTP_200_OK]
        assert deletions == [status.HTTP_204_NO_CONTENT, status.HTTP_204_NO_CONTENT]
        assert not connection.in_atomic_block
        assert set(GPSTrack.objects.values_list("id", flat=True)) == original_ids
        assert (
            set(GPSTrackUserPermission.objects.values_list("id", flat=True))
            == original_permissions
        )
        assert set(self.storage.listdir("")[1]) == stored_before
