# -*- coding: utf-8 -*-

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework import status

from speleodb.api.v2.tests.base_testcase import BaseAPIProjectTestCase
from speleodb.api.v2.tests.base_testcase import PermissionType
from speleodb.api.v2.tests.factories import SubSurfaceStationFactory
from speleodb.common.enums import PermissionLevel
from speleodb.common.enums import StationResourceType
from speleodb.gis.models import StationResource

if TYPE_CHECKING:
    from speleodb.gis.models import Station


def get_video_file() -> SimpleUploadedFile:
    return SimpleUploadedFile(
        "video.mp4",
        (Path(__file__).parent / "artifacts" / "video.mp4").read_bytes(),
        content_type="video/mp4",
    )


class TestStationResourceVideoUpload(BaseAPIProjectTestCase):
    """Test video upload functionality for station resources."""

    station: Station

    def setUp(self) -> None:
        super().setUp()
        self.set_test_project_permission(
            level=PermissionLevel.ADMIN, permission_type=PermissionType.USER
        )
        self.station = SubSurfaceStationFactory.create(project=self.project)

    def test_video_upload_file_size_over_limit(self) -> None:
        """Test video upload with file size over 5MB limit."""
        # Create a file slightly over 5MB
        video_content = b"X" * (5 * 1024 * 1024 + 1000)  # 5MB + 1KB
        video_file = SimpleUploadedFile(
            "test_large.mp4", video_content, content_type="video/mp4"
        )

        data = {
            "resource_type": StationResourceType.VIDEO,
            "title": "Large Video",
            "description": "Video over size limit",
            "file": video_file,
        }

        auth = self.header_prefix + str(self.token.key)
        response = self.client.post(
            reverse("api:v2:station-resources", kwargs={"id": self.station.id}),
            data=data,
            headers={"authorization": auth},
        )

        # Should fail with appropriate error
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_video_update_file_replacement(self) -> None:
        """Test updating a video resource with a new file."""
        # First create a video resource
        data = {
            "resource_type": StationResourceType.VIDEO,
            "title": "Initial Video",
            "file": get_video_file(),
        }

        auth = self.header_prefix + str(self.token.key)
        response = self.client.post(
            reverse("api:v2:station-resources", kwargs={"id": self.station.id}),
            data=data,
            headers={"authorization": auth},
        )

        assert response.status_code == status.HTTP_201_CREATED
        resource_id = response.data["id"]
        resource = StationResource.objects.get(id=resource_id)
        original_filename = resource.file.name

        # Now update with a new file
        update_data = {
            "title": "Updated Video",
            "file": get_video_file(),
        }

        response = self.client.patch(
            reverse(
                "api:v2:resource-detail",
                kwargs={"id": resource_id},
            ),
            data=update_data,
            headers={"authorization": auth},
            format="multipart",
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["title"] == "Updated Video"
        resource.refresh_from_db()
        assert resource.file.name != original_filename
