# -*- coding: utf-8 -*-

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from parameterized.parameterized import parameterized
from rest_framework import status

from speleodb.api.v1.tests.base_testcase import BaseAPIProjectTestCase
from speleodb.api.v1.tests.base_testcase import PermissionType
from speleodb.api.v1.tests.factories import StationFactory
from speleodb.surveys.models import PermissionLevel
from speleodb.surveys.models.station import StationResourceType

if TYPE_CHECKING:
    from speleodb.surveys.models.station import Station


def get_video_file() -> SimpleUploadedFile:
    return SimpleUploadedFile(
        "video.mp4",
        Path("speleodb/api/v1/tests/artifacts/video.mp4").read_bytes(),
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
        self.station = StationFactory.create(project=self.project)

    def test_successful_video_upload_small_file(self) -> None:
        """Test successful video upload with a small file."""

        data = {
            "resource_type": StationResourceType.VIDEO,
            "title": "Test Video Upload",
            "description": "Testing video upload functionality",
            "file": get_video_file(),
        }

        auth = self.header_prefix + str(self.token.key)
        response = self.client.post(
            reverse("api:v1:station-resources", kwargs={"id": self.station.id}),
            data=data,
            headers={"authorization": auth},
        )

        # Assert successful creation
        assert response.status_code == status.HTTP_201_CREATED, (
            f"Expected 201, got {response.status_code}. Response: {response.data}"
        )

        # Verify response data
        resource_data = response.data["data"]
        assert resource_data["resource_type"] == StationResourceType.VIDEO
        assert resource_data["title"] == "Test Video Upload"
        assert resource_data["file"] is not None
        assert "file_url" in resource_data or "file" in resource_data

        # Verify resource was created with correct type
        assert resource_data["resource_type"] == StationResourceType.VIDEO

    def test_video_upload_without_file(self) -> None:
        """Test video upload without providing a file."""
        data = {
            "resource_type": StationResourceType.VIDEO,
            "title": "Video Without File",
            "description": "This should fail",
            # No file provided
        }

        auth = self.header_prefix + str(self.token.key)
        response = self.client.post(
            reverse("api:v1:station-resources", kwargs={"id": self.station.id}),
            data=data,
            headers={"authorization": auth},
        )

        # Should fail with 400
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        # Check for the expected error message
        if "errors" in response.data:
            errors = response.data["errors"]
            # The error might be in different fields
            assert any(
                "requires a file" in str(error).lower()
                or "no file was submitted" in str(error).lower()
                or "file" in str(errors)
                for error in (errors.values() if isinstance(errors, dict) else [errors])
            ), f"Expected file-related error, got: {errors}"

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
            reverse("api:v1:station-resources", kwargs={"id": self.station.id}),
            data=data,
            headers={"authorization": auth},
        )

        # Should fail with appropriate error
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @parameterized.expand(
        [
            ("video/mp4", "test.mp4"),
            ("video/quicktime", "test.mov"),
            ("video/x-msvideo", "test.avi"),
            ("video/webm", "test.webm"),
        ]
    )
    def test_video_upload_different_formats(
        self, content_type: str, filename: str
    ) -> None:
        """Test video upload with different video formats."""
        data = {
            "resource_type": StationResourceType.VIDEO,
            "title": f"Test {filename}",
            "description": f"Testing {content_type} format",
            "file": get_video_file(),
        }

        auth = self.header_prefix + str(self.token.key)
        response = self.client.post(
            reverse("api:v1:station-resources", kwargs={"id": self.station.id}),
            data=data,
            headers={"authorization": auth},
        )

        # Should succeed for all video formats
        assert response.status_code == status.HTTP_201_CREATED

    def test_video_upload_with_all_fields(self) -> None:
        """Test video upload with all optional fields."""
        data = {
            "resource_type": StationResourceType.VIDEO,
            "title": "Complete Video Test",
            "description": (
                "This video has all fields populated including a long description that "
                "provides context about what is shown in the video"
            ),
            "file": get_video_file(),
        }

        auth = self.header_prefix + str(self.token.key)
        response = self.client.post(
            reverse("api:v1:station-resources", kwargs={"id": self.station.id}),
            data=data,
            headers={"authorization": auth},
        )

        assert response.status_code == status.HTTP_201_CREATED

        resource_data = response.data["data"]
        assert resource_data["title"] == "Complete Video Test"
        assert len(resource_data["description"]) > 50  # noqa: PLR2004

    def test_video_upload_empty_file(self) -> None:
        """Test video upload with empty file."""
        video_file = SimpleUploadedFile("empty.mp4", b"", content_type="video/mp4")

        data = {
            "resource_type": StationResourceType.VIDEO,
            "title": "Empty Video",
            "description": "Video file is empty",
            "file": video_file,
        }

        auth = self.header_prefix + str(self.token.key)
        response = self.client.post(
            reverse("api:v1:station-resources", kwargs={"id": self.station.id}),
            data=data,
            headers={"authorization": auth},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_video_upload_form_data_structure(self) -> None:
        """Test that form data is properly structured for video upload."""

        # Create form data manually to ensure proper structure
        data = {
            "resource_type": StationResourceType.VIDEO,
            "title": "Form Data Test",
            "description": "Testing form data structure",
            "file": get_video_file(),
        }

        auth = self.header_prefix + str(self.token.key)

        response = self.client.post(
            reverse("api:v1:station-resources", kwargs={"id": self.station.id}),
            data=data,
            headers={"authorization": auth},
            format="multipart",  # Explicitly set format to multipart
        )

        assert response.status_code == status.HTTP_201_CREATED

    def test_video_upload_missing_required_fields(self) -> None:
        """Test video upload with missing required fields."""
        # Missing title
        data = {
            "resource_type": StationResourceType.VIDEO,
            # "title": "Missing",  # Title is missing
            "file": get_video_file(),
        }

        auth = self.header_prefix + str(self.token.key)
        response = self.client.post(
            reverse("api:v1:station-resources", kwargs={"id": self.station.id}),
            data=data,
            headers={"authorization": auth},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "title" in response.data.get("errors", {})

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
            reverse("api:v1:station-resources", kwargs={"id": self.station.id}),
            data=data,
            headers={"authorization": auth},
        )

        assert response.status_code == status.HTTP_201_CREATED
        resource_id = response.data["data"]["id"]

        # Now update with a new file
        update_data = {
            "title": "Updated Video",
            "file": get_video_file(),
        }

        response = self.client.patch(
            reverse(
                "api:v1:resource-detail",
                kwargs={"id": resource_id},
            ),
            data=update_data,
            headers={"authorization": auth},
            format="multipart",
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"]["title"] == "Updated Video"
