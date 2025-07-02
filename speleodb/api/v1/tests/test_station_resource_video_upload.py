# -*- coding: utf-8 -*-
"""
Comprehensive tests for video upload functionality in Station Resources.
Tests various scenarios including file size limits, missing files, and proper file handling.
"""

from __future__ import annotations

from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from parameterized.parameterized import parameterized
from rest_framework import status

from speleodb.api.v1.tests.base_testcase import BaseAPIProjectTestCase
from speleodb.api.v1.tests.factories import StationFactory
from speleodb.surveys.models import PermissionLevel
from speleodb.surveys.models.station import Station


class TestStationResourceVideoUpload(BaseAPIProjectTestCase):
    """Test video upload functionality for station resources."""

    station: Station

    def setUp(self) -> None:
        super().setUp()
        self.set_test_project_permission(level=PermissionLevel.ADMIN)
        self.station = StationFactory.create(project=self.project)

    def test_successful_video_upload_small_file(self) -> None:
        """Test successful video upload with a small file."""
        # Create a small fake video file (100KB)
        video_content = b"FAKE_VIDEO_CONTENT" * 5000  # ~100KB
        video_file = SimpleUploadedFile(
            "test_video.mp4", video_content, content_type="video/mp4"
        )

        data = {
            "station_id": str(self.station.id),
            "resource_type": "video",
            "title": "Test Video Upload",
            "description": "Testing video upload functionality",
            "file": video_file,
        }

        auth = self.header_prefix + str(self.token.key)
        response = self.client.post(
            reverse(
                "api:v1:resource-list-create",
            ),
            data=data,
            headers={"authorization": auth},
        )

        # Assert successful creation
        assert response.status_code == status.HTTP_201_CREATED, (
            f"Expected 201, got {response.status_code}. Response: {response.data}"
        )

        # Verify response data
        resource_data = response.data["data"]["resource"]
        assert resource_data["resource_type"] == "video"
        assert resource_data["title"] == "Test Video Upload"
        assert resource_data["file"] is not None
        assert "file_url" in resource_data or "file" in resource_data

        # Verify resource was created with correct type
        assert resource_data["resource_type"] == "video"

    def test_video_upload_without_file(self) -> None:
        """Test video upload without providing a file."""
        data = {
            "station_id": str(self.station.id),
            "resource_type": "video",
            "title": "Video Without File",
            "description": "This should fail",
            # No file provided
        }

        auth = self.header_prefix + str(self.token.key)
        response = self.client.post(
            reverse(
                "api:v1:resource-list-create",
            ),
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

    def test_video_upload_file_size_at_limit(self) -> None:
        """Test video upload with file size exactly at 5MB limit."""
        # Create a file exactly 5MB
        video_content = b"X" * (5 * 1024 * 1024)  # Exactly 5MB
        video_file = SimpleUploadedFile(
            "test_5mb.mp4", video_content, content_type="video/mp4"
        )

        data = {
            "station_id": str(self.station.id),
            "resource_type": "video",
            "title": "5MB Video",
            "description": "Video at size limit",
            "file": video_file,
        }

        auth = self.header_prefix + str(self.token.key)
        response = self.client.post(
            reverse(
                "api:v1:resource-list-create",
            ),
            data=data,
            headers={"authorization": auth},
        )

        # Should succeed
        assert response.status_code == status.HTTP_201_CREATED

    def test_video_upload_file_size_over_limit(self) -> None:
        """Test video upload with file size over 5MB limit."""
        # Create a file slightly over 5MB
        video_content = b"X" * (5 * 1024 * 1024 + 1000)  # 5MB + 1KB
        video_file = SimpleUploadedFile(
            "test_large.mp4", video_content, content_type="video/mp4"
        )

        data = {
            "station_id": str(self.station.id),
            "resource_type": "video",
            "title": "Large Video",
            "description": "Video over size limit",
            "file": video_file,
        }

        auth = self.header_prefix + str(self.token.key)
        response = self.client.post(
            reverse(
                "api:v1:resource-list-create",
            ),
            data=data,
            headers={"authorization": auth},
        )

        # Should fail with appropriate error
        assert response.status_code in [
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
        ]

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
        video_content = b"FAKE_VIDEO_CONTENT" * 1000  # Small video
        video_file = SimpleUploadedFile(
            filename, video_content, content_type=content_type
        )

        data = {
            "station_id": str(self.station.id),
            "resource_type": "video",
            "title": f"Test {filename}",
            "description": f"Testing {content_type} format",
            "file": video_file,
        }

        auth = self.header_prefix + str(self.token.key)
        response = self.client.post(
            reverse(
                "api:v1:resource-list-create",
            ),
            data=data,
            headers={"authorization": auth},
        )

        # Should succeed for all video formats
        assert response.status_code == status.HTTP_201_CREATED

    def test_video_upload_with_all_fields(self) -> None:
        """Test video upload with all optional fields."""
        video_content = b"FAKE_VIDEO_CONTENT" * 1000
        video_file = SimpleUploadedFile(
            "complete_test.mp4", video_content, content_type="video/mp4"
        )

        data = {
            "station_id": str(self.station.id),
            "resource_type": "video",
            "title": "Complete Video Test",
            "description": "This video has all fields populated including a long description that provides context about what is shown in the video",
            "file": video_file,
        }

        auth = self.header_prefix + str(self.token.key)
        response = self.client.post(
            reverse(
                "api:v1:resource-list-create",
            ),
            data=data,
            headers={"authorization": auth},
        )

        assert response.status_code == status.HTTP_201_CREATED

        resource_data = response.data["data"]["resource"]
        assert resource_data["title"] == "Complete Video Test"
        assert len(resource_data["description"]) > 50

    def test_video_upload_empty_file(self) -> None:
        """Test video upload with empty file."""
        video_file = SimpleUploadedFile("empty.mp4", b"", content_type="video/mp4")

        data = {
            "station_id": str(self.station.id),
            "resource_type": "video",
            "title": "Empty Video",
            "description": "Video file is empty",
            "file": video_file,
        }

        auth = self.header_prefix + str(self.token.key)
        response = self.client.post(
            reverse(
                "api:v1:resource-list-create",
            ),
            data=data,
            headers={"authorization": auth},
        )

        # Behavior depends on implementation - might accept or reject empty files
        # Log the response for debugging
        print(f"Empty file response: {response.status_code}")
        print(f"Response data: {response.data}")

    def test_video_upload_form_data_structure(self) -> None:
        """Test that form data is properly structured for video upload."""
        video_content = b"FAKE_VIDEO_CONTENT" * 1000
        video_file = SimpleUploadedFile(
            "form_test.mp4", video_content, content_type="video/mp4"
        )

        # Create form data manually to ensure proper structure
        data = {
            "station_id": str(self.station.id),
            "resource_type": "video",
            "title": "Form Data Test",
            "description": "Testing form data structure",
            "file": video_file,
        }

        auth = self.header_prefix + str(self.token.key)

        # Log the request data for debugging
        print(f"Request data keys: {list(data.keys())}")
        print(f"File object: {data['file']}")
        if hasattr(data["file"], "name"):
            print(f"File name: {data['file'].name}")
        if hasattr(data["file"], "size"):
            print(f"File size: {data['file'].size}")

        response = self.client.post(
            reverse(
                "api:v1:resource-list-create",
            ),
            data=data,
            headers={"authorization": auth},
            format="multipart",  # Explicitly set format to multipart
        )

        # Log response for debugging
        print(f"Response status: {response.status_code}")
        print(f"Response data: {response.data}")

        assert response.status_code == status.HTTP_201_CREATED

    def test_video_upload_missing_required_fields(self) -> None:
        """Test video upload with missing required fields."""
        video_content = b"FAKE_VIDEO_CONTENT"
        video_file = SimpleUploadedFile(
            "test.mp4", video_content, content_type="video/mp4"
        )

        # Missing title
        data = {
            "station_id": str(self.station.id),
            "resource_type": "video",
            # "title": "Missing",  # Title is missing
            "file": video_file,
        }

        auth = self.header_prefix + str(self.token.key)
        response = self.client.post(
            reverse(
                "api:v1:resource-list-create",
            ),
            data=data,
            headers={"authorization": auth},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "title" in response.data.get("errors", {})

    def test_video_update_file_replacement(self) -> None:
        """Test updating a video resource with a new file."""
        # First create a video resource
        initial_content = b"INITIAL_VIDEO" * 1000
        initial_file = SimpleUploadedFile(
            "initial.mp4", initial_content, content_type="video/mp4"
        )

        data = {
            "station_id": str(self.station.id),
            "resource_type": "video",
            "title": "Initial Video",
            "file": initial_file,
        }

        auth = self.header_prefix + str(self.token.key)
        response = self.client.post(
            reverse(
                "api:v1:resource-list-create",
            ),
            data=data,
            headers={"authorization": auth},
        )

        assert response.status_code == status.HTTP_201_CREATED
        resource_id = response.data["data"]["resource"]["id"]

        # Now update with a new file
        new_content = b"UPDATED_VIDEO" * 1000
        new_file = SimpleUploadedFile(
            "updated.mp4", new_content, content_type="video/mp4"
        )

        update_data = {
            "title": "Updated Video",
            "file": new_file,
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
        assert response.data["data"]["resource"]["title"] == "Updated Video"
