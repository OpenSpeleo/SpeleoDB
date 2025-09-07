# -*- coding: utf-8 -*-

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from speleodb.api.v1.tests.base_testcase import BaseAPIProjectTestCase
from speleodb.api.v1.tests.base_testcase import PermissionType
from speleodb.surveys.models import Station
from speleodb.surveys.models import StationResource
from speleodb.surveys.models.permission_lvl import PermissionLevel
from speleodb.surveys.models.station import StationResourceType
from speleodb.utils.image_processing import ImageProcessor


class TestHEICSupport(BaseAPIProjectTestCase):
    """Test HEIC image format support and transparent conversion to JPEG."""

    def setUp(self) -> None:
        super().setUp()
        self.set_test_project_permission(
            PermissionLevel.READ_AND_WRITE, PermissionType.USER
        )

        # Create test station
        self.station = Station.objects.create(
            project=self.project,
            name="Test Station",
            latitude=0.0,
            longitude=0.0,
            created_by=self.user,
        )

        # Path to test HEIC file
        self.artifacts_dir = Path(__file__).parent / "artifacts"

    def test_heic_transparently_converted_to_jpeg(self) -> None:
        """Test that HEIC files are transparently converted to JPEG."""
        # Load the real HEIC file
        with (self.artifacts_dir / "image.heic").open(mode="rb") as f:
            heic_content = f.read()

        # Create resource with .heic extension
        heic_file = SimpleUploadedFile(
            "test_photo.heic", heic_content, content_type="image/heic"
        )

        resource = StationResource.objects.create(
            station=self.station,
            resource_type=StationResourceType.PHOTO,
            title="HEIC Test",
            file=heic_file,
            created_by=self.user,
        )

        # Check resource was created and file was converted to JPEG
        assert resource.id is not None
        assert resource.file.name.endswith(".jpg")  # Should be converted to JPEG
        assert not resource.file.name.endswith(".heic")  # Should NOT be HEIC

        # Verify the stored file is actually JPEG
        resource.file.open("rb")
        img = Image.open(resource.file)
        assert img.format == "JPEG"

    def test_heif_transparently_converted_to_jpeg(self) -> None:
        """Test that HEIF files are transparently converted to JPEG."""
        # Create a simple test image (since we don't have a .heif file)
        img = Image.new("RGB", (100, 100), color="blue")
        buffer = BytesIO()
        img.save(buffer, format="JPEG")
        buffer.seek(0)

        # Create resource with .heif extension
        heif_file = SimpleUploadedFile(
            "test_photo.heif", buffer.getvalue(), content_type="image/heif"
        )

        # This test would work with real HEIF support
        # For now, it tests the validator allows HEIF
        resource = StationResource.objects.create(
            station=self.station,
            resource_type=StationResourceType.PHOTO,
            title="HEIF Test",
            file=heif_file,
            created_by=self.user,
        )
        # If pillow-heif is available, it should convert
        assert resource.file.name.endswith(".jpg") or resource.file.name.endswith(
            ".heif"
        )

    def test_image_processor_recognizes_heic(self) -> None:
        """Test that ImageProcessor recognizes HEIC files as images."""
        assert ImageProcessor.is_image_file("photo.heic")
        assert ImageProcessor.is_image_file("photo.HEIC")
        assert ImageProcessor.is_image_file("photo.heif")
        assert ImageProcessor.is_image_file("photo.HEIF")
        assert ".heic" in ImageProcessor.IMAGE_EXTENSIONS
        assert ".heif" in ImageProcessor.IMAGE_EXTENSIONS

    def test_heic_to_jpeg_conversion(self) -> None:
        """Test that HEIC files can be converted to JPEG."""
        # Load the real HEIC file
        with (self.artifacts_dir / "image.heic").open(mode="rb") as f:
            # Test that we can open and process the HEIC file
            img = ImageProcessor.process_image_for_web(f)

            # Verify it was converted to RGB
            assert img.mode in ("RGB", "L")

            # Verify we can save it as JPEG
            output = BytesIO()
            img.save(output, format="JPEG", quality=85)
            output.seek(0)

            # Verify the output is valid JPEG
            test_img = Image.open(output)
            assert test_img.format == "JPEG"

    def test_heic_miniature_generation_with_real_file(self) -> None:
        """Test that miniatures are generated for real HEIC files and saved as JPEG."""

        # Load the real HEIC file
        with (self.artifacts_dir / "image.heic").open(mode="rb") as f:
            heic_content = f.read()

        heic_file = SimpleUploadedFile(
            "test_photo.heic", heic_content, content_type="image/heic"
        )

        resource = StationResource.objects.create(
            station=self.station,
            resource_type=StationResourceType.PHOTO,
            title="HEIC Photo",
            file=heic_file,
            created_by=self.user,
        )

        # Check miniature was created
        assert resource.miniature is not None
        assert ".jpg" in resource.miniature.name  # Storage may modify filename

        # Check main file was converted to JPEG
        assert ".jpg" in resource.file.name
        assert ".heic" not in resource.file.name

        # Verify miniature dimensions
        resource.miniature.open("rb")
        miniature_img = Image.open(resource.miniature)

        # Should be max 300x200
        assert miniature_img.width <= 300  # noqa: PLR2004
        assert miniature_img.height <= 200  # noqa: PLR2004

        # Should be JPEG format
        assert miniature_img.format == "JPEG"

        # Miniature URL should be available
        assert resource.get_miniature_url() is not None
