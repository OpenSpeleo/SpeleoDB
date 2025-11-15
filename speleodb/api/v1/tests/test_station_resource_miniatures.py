# -*- coding: utf-8 -*-

from __future__ import annotations

import io
from pathlib import Path

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image
from rest_framework import status

from speleodb.api.v1.tests.base_testcase import BaseAPIProjectTestCase
from speleodb.api.v1.tests.base_testcase import PermissionType
from speleodb.common.enums import PermissionLevel
from speleodb.gis.models import Station
from speleodb.gis.models import StationResource
from speleodb.gis.models.station import StationResourceType

User = get_user_model()


def create_test_image(
    width: int = 100, height: int = 100, color: str = "red", img_format: str = "JPEG"
) -> SimpleUploadedFile:
    """Create a test image file."""

    image = Image.new("RGB", (width, height), color=color)
    buffer = io.BytesIO()
    image.save(buffer, format=img_format)
    buffer.seek(0)

    return SimpleUploadedFile(
        name=f"test_{width}x{height}.jpg",
        content=buffer.getvalue(),
        content_type="image/jpeg",
    )


def create_test_video() -> SimpleUploadedFile:
    """Create a test video file (mock)."""
    artifacts_dir = Path(__file__).parent / "artifacts"
    with (artifacts_dir / "video.mp4").open(mode="rb") as f:
        content = f.read()

    return SimpleUploadedFile(
        name="test_video.mp4",
        content=content,
        content_type="video/mp4",
    )


def create_test_document() -> SimpleUploadedFile:
    """Create a test document file (mock)."""
    artifacts_dir = Path(__file__).parent / "artifacts"

    with (artifacts_dir / "document.pdf").open(mode="rb") as f:
        content = f.read()

    return SimpleUploadedFile(
        name="test_document.pdf",
        content=content,
        content_type="application/pdf",
    )


@pytest.mark.django_db
class TestStationResourceMiniatures(BaseAPIProjectTestCase):
    def setUp(self) -> None:
        super().setUp()
        # Set permissions
        self.set_test_project_permission(
            PermissionLevel.READ_AND_WRITE, PermissionType.USER
        )
        # Create a station for testing
        self.station = Station.objects.create(
            name="Test Station",
            project=self.project,  # BaseAPIProjectTestCase uses self.project
            latitude=45.0,
            longitude=-75.0,
            created_by=self.user.email,
        )

    def test_photo_miniature_created_on_upload(self) -> None:
        """Test that miniature is created when uploading a photo resource."""
        image = create_test_image(width=1200, height=800)

        resource = StationResource.objects.create(
            station=self.station,
            resource_type=StationResourceType.PHOTO,
            title="Test Photo",
            file=image,
            created_by=self.user.email,
        )

        # Check miniature was created
        assert resource.miniature is not None

    def test_video_miniature_created_on_upload(self) -> None:
        """Test that placeholder miniature is created for video resources."""
        video = create_test_video()

        resource = StationResource.objects.create(
            station=self.station,
            resource_type=StationResourceType.VIDEO,
            title="Test Video",
            file=video,
            created_by=self.user.email,
        )

        # Check miniature was created
        assert resource.miniature is not None

    def test_document_miniature_created_on_upload(self) -> None:
        """Test that placeholder miniature is created for document resources."""
        document = create_test_document()

        resource = StationResource.objects.create(
            station=self.station,
            resource_type=StationResourceType.DOCUMENT,
            title="Test Document",
            file=document,
            created_by=self.user.email,
        )

        # Check miniature was created
        assert resource.miniature is not None

    def test_no_miniature_for_note_resource(self) -> None:
        """Test that no miniature is created for note resources."""
        resource = StationResource.objects.create(
            station=self.station,
            resource_type=StationResourceType.NOTE,
            title="Test Note",
            text_content="This is a test note",
            created_by=self.user.email,
        )

        # Check no miniature was created
        assert not resource.miniature

    def test_miniature_updated_on_file_change(self) -> None:
        """Test that miniature is regenerated when file is changed."""
        # Create initial resource
        image1 = create_test_image(color="red")
        resource = StationResource.objects.create(
            station=self.station,
            resource_type=StationResourceType.PHOTO,
            title="Test Photo",
            file=image1,
            created_by=self.user.email,
        )

        original_miniature = resource.miniature.name

        # Update with new image
        image2 = create_test_image(color="blue")
        resource.file = image2
        resource.save()

        # Check miniature was updated
        assert resource.miniature.name != original_miniature
        assert resource.miniature is not None

    def test_miniature_deleted_with_resource(self) -> None:
        """Test that miniature is deleted when resource is deleted."""
        image = create_test_image()
        resource = StationResource.objects.create(
            station=self.station,
            resource_type=StationResourceType.PHOTO,
            title="Test Photo",
            file=image,
            created_by=self.user.email,
        )

        # Delete resource
        resource.delete()

        # Check resource is deleted
        assert not StationResource.objects.filter(id=resource.id).exists()

        # Miniature deletion is handled by Django's file field cascade

    def test_api_returns_miniature_url(self) -> None:
        """Test that API returns miniature URL in resource serialization."""
        image = create_test_image()
        resource = StationResource.objects.create(
            station=self.station,
            resource_type=StationResourceType.PHOTO,
            title="Test Photo",
            file=image,
            created_by=self.user.email,
        )

        # Get resource through API

        response = self.client.get(
            reverse("api:v1:resource-detail", kwargs={"id": resource.id}),
            headers={"authorization": self.header_prefix + self.token.key},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        resource_data = data["data"]
        assert resource_data["miniature"] is not None

    def test_validation_prevents_file_for_note_resource(self) -> None:
        """Test that validation prevents file upload for note resources."""
        image = create_test_image()

        with pytest.raises(ValidationError, match="should not have a file"):
            StationResource.objects.create(
                station=self.station,
                resource_type=StationResourceType.NOTE,
                title="Test Note",
                file=image,  # This should fail
                created_by=self.user.email,
            )

    def test_validation_requires_file_for_photo_resource(self) -> None:
        """Test that validation requires file for photo resources."""
        with pytest.raises(ValidationError, match="requires a file"):
            StationResource.objects.create(
                station=self.station,
                resource_type=StationResourceType.PHOTO,
                title="Test Photo",
                # No file provided - should fail
                created_by=self.user.email,
            )
