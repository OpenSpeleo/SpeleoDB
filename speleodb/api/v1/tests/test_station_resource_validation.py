# -*- coding: utf-8 -*-

from __future__ import annotations

from pathlib import Path

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status

from speleodb.api.v1.tests.base_testcase import BaseAPIProjectTestCase
from speleodb.surveys.models import Station
from speleodb.surveys.models import StationResource
from speleodb.surveys.models.permission_lvl import PermissionLevel


class TestStationResourceFileValidation(BaseAPIProjectTestCase):
    """Test file type validation for station resources."""

    def setUp(self) -> None:
        """Set up test data."""
        super().setUp()
        self.set_test_project_permission(PermissionLevel.READ_AND_WRITE)
        self.station = Station.objects.create(
            project=self.project,
            name="Test Station",
            latitude=45.0,
            longitude=-73.0,
            created_by=self.user,
        )

    def create_test_file(
        self, filename: str, content: bytes | None = None
    ) -> SimpleUploadedFile:
        """Create a test file with the given filename."""
        if content is None:
            content = b"test content"
        return SimpleUploadedFile(filename, content)

    def test_photo_accepts_valid_image_formats(self) -> None:
        """Test that photo resources accept valid image formats."""
        valid_extensions = [
            ".jpg",
            ".jpeg",
            ".png",
            ".gif",
            ".bmp",
            ".webp",
            ".heic",
            ".heif",
        ]  # HEIC/HEIF are converted to JPEG

        for ext in valid_extensions:
            resource = StationResource(
                station=self.station,
                resource_type=StationResource.ResourceType.PHOTO,
                title=f"Test {ext}",
                file=self.create_test_file(f"test{ext}"),
                created_by=self.user,
            )
            # Should not raise ValidationError
            resource.full_clean()

    def test_photo_rejects_invalid_formats(self) -> None:
        """Test that photo resources reject non-image formats."""
        invalid_files = ["test.mp4", "test.pdf", "test.txt", "test.doc"]

        for filename in invalid_files:
            resource = StationResource(
                station=self.station,
                resource_type=StationResource.ResourceType.PHOTO,
                title="Test Photo",
                file=self.create_test_file(filename),
                created_by=self.user,
            )

            with pytest.raises(ValidationError) as exc_info:
                resource.full_clean()

            assert "file" in exc_info.value.error_dict
            error_message = str(exc_info.value.error_dict["file"][0])

            # Check for either custom validation message or FileExtensionValidator
            # message
            assert "Invalid file type for Photo" in error_message or (
                "File extension" in error_message and "not allowed" in error_message
            )

    def test_video_accepts_valid_video_formats(self) -> None:
        """Test that video resources accept valid video formats."""
        valid_extensions = [".mp4", ".avi", ".mov", ".wmv", ".flv", ".webm"]

        for ext in valid_extensions:
            resource = StationResource(
                station=self.station,
                resource_type=StationResource.ResourceType.VIDEO,
                title=f"Test {ext}",
                file=self.create_test_file(f"test{ext}"),
                created_by=self.user,
            )
            # Should not raise ValidationError
            resource.full_clean()

    def test_video_rejects_invalid_formats(self) -> None:
        """Test that video resources reject non-video formats."""
        invalid_files = ["test.jpg", "test.pdf", "test.txt", "test.png"]

        for filename in invalid_files:
            resource = StationResource(
                station=self.station,
                resource_type=StationResource.ResourceType.VIDEO,
                title="Test Video",
                file=self.create_test_file(filename),
                created_by=self.user,
            )

            with pytest.raises(ValidationError) as exc_info:
                resource.full_clean()

            assert "file" in exc_info.value.error_dict
            error_message = str(exc_info.value.error_dict["file"][0])

            # Check for either custom validation message or FileExtensionValidator
            # message
            assert "Invalid file type for Video" in error_message or (
                "File extension" in error_message and "not allowed" in error_message
            )

    def test_document_accepts_valid_document_formats(self) -> None:
        """Test that document resources accept valid document formats."""
        valid_extensions = [".pdf", ".doc", ".docx", ".txt", ".rtf"]

        for ext in valid_extensions:
            resource = StationResource(
                station=self.station,
                resource_type=StationResource.ResourceType.DOCUMENT,
                title=f"Test {ext}",
                file=self.create_test_file(f"test{ext}"),
                created_by=self.user,
            )
            # Should not raise ValidationError
            resource.full_clean()

    def test_document_rejects_invalid_formats(self) -> None:
        """Test that document resources reject non-document formats."""
        invalid_files = ["test.jpg", "test.mp4", "test.png", "test.exe"]

        for filename in invalid_files:
            resource = StationResource(
                station=self.station,
                resource_type=StationResource.ResourceType.DOCUMENT,
                title="Test Document",
                file=self.create_test_file(filename),
                created_by=self.user,
            )

            with pytest.raises(ValidationError) as exc_info:
                resource.full_clean()

            assert "file" in exc_info.value.error_dict
            error_message = str(exc_info.value.error_dict["file"][0])

            # Check for either custom validation message or FileExtensionValidator
            # message
            assert "Invalid file type for Document" in error_message or (
                "File extension" in error_message and "not allowed" in error_message
            )

    def test_note_and_sketch_reject_files(self) -> None:
        """Test that note and sketch resources reject any files."""
        for resource_type in [
            StationResource.ResourceType.NOTE,
            StationResource.ResourceType.SKETCH,
        ]:
            resource = StationResource(
                station=self.station,
                resource_type=resource_type,
                title="Test",
                file=self.create_test_file("test.txt"),
                text_content="Some content",
                created_by=self.user,
            )

            with pytest.raises(ValidationError) as exc_info:
                resource.full_clean()

            assert "file" in exc_info.value.error_dict
            error_message = str(exc_info.value.error_dict["file"][0])
            assert "should not have a file" in error_message

    def test_api_returns_validation_errors(self) -> None:
        """Test that API returns proper validation errors."""
        # Try to create a photo with a video file
        response = self.client.post(
            "/api/v1/resources/",
            {
                "station_id": str(self.station.id),
                "resource_type": "photo",
                "title": "Test Photo",
                "file": self.create_test_file("test.mp4"),
            },
            format="multipart",
            headers={"authorization": self.header_prefix + self.token.key},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert "errors" in data
        assert "file" in data["errors"]
        assert "Invalid file type for Photo" in str(data["errors"]["file"])

    def test_real_file_uploads(self) -> None:
        """Test with real artifact files."""
        artifacts_dir = Path(__file__).parent / "artifacts"

        # Test valid photo upload
        with (artifacts_dir / "image.jpg").open(mode="rb") as f:
            response = self.client.post(
                "/api/v1/resources/",
                {
                    "station_id": str(self.station.id),
                    "resource_type": "photo",
                    "title": "Test Photo",
                    "file": SimpleUploadedFile(
                        "photo.jpg", f.read(), content_type="image/jpeg"
                    ),
                },
                format="multipart",
                headers={"authorization": self.header_prefix + self.token.key},
            )
        assert response.status_code == status.HTTP_201_CREATED

        # Test invalid photo upload (using video file)
        with (artifacts_dir / "video.mp4").open(mode="rb") as f:
            response = self.client.post(
                "/api/v1/resources/",
                {
                    "station_id": str(self.station.id),
                    "resource_type": "photo",
                    "title": "Test Photo",
                    "file": SimpleUploadedFile(
                        "video.mp4", f.read(), content_type="video/mp4"
                    ),
                },
                format="multipart",
                headers={"authorization": self.header_prefix + self.token.key},
            )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert "Invalid file type for Photo" in str(data["errors"]["file"])
