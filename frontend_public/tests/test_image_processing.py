# -*- coding: utf-8 -*-
"""Tests for image processing functionality."""

from __future__ import annotations

from io import BytesIO
from typing import TYPE_CHECKING

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from frontend_public.models import BoardMember
from frontend_public.models import ExplorerMember
from frontend_public.models import TechnicalMember

if TYPE_CHECKING:
    type PersonAbstract = BoardMember | TechnicalMember | ExplorerMember


def create_test_image(
    width: int = 800, height: int = 600, color: str = "red", img_format: str = "JPEG"
) -> SimpleUploadedFile:
    """Create a test image with specified dimensions."""
    img = Image.new("RGB", (width, height), color=color)
    img_bytes = BytesIO()
    img.save(img_bytes, format=img_format)
    img_bytes.seek(0)

    extension = "jpg" if img_format == "JPEG" else img_format.lower()
    return SimpleUploadedFile(
        name=f"test_photo.{extension}",
        content=img_bytes.read(),
        content_type=f"image/{img_format.lower()}",
    )


@pytest.mark.django_db
class TestImageProcessing:
    """Test image processing functionality."""

    def test_thumbnail_creation(self, db: None) -> None:
        """Test that a 200x200 thumbnail is created from uploaded image."""
        # Create a large test image
        original_image = create_test_image(width=1200, height=800)

        # Create a person with the image
        person = BoardMember.objects.create(
            full_name="Test Person",
            title="Test Title",
            description="Test Description",
            photo=original_image,
        )

        # Open the saved photo
        person.photo.open()
        saved_img = Image.open(person.photo)

        # Check dimensions - should be 200x200
        assert saved_img.size == (200, 200)

    def test_square_crop_from_landscape(self, db: None) -> None:
        """Test that landscape images are center-cropped to square."""
        # Create a landscape image
        landscape_image = create_test_image(width=800, height=400, color="blue")

        person = BoardMember.objects.create(
            full_name="Test Person",
            title="Test Title",
            description="Test Description",
            photo=landscape_image,
        )

        # Check that the thumbnail is square
        person.photo.open()
        saved_img = Image.open(person.photo)
        assert saved_img.size == (200, 200)

    def test_square_crop_from_portrait(self, db: None) -> None:
        """Test that portrait images are center-cropped to square."""
        # Create a portrait image
        portrait_image = create_test_image(width=400, height=800, color="green")

        person = BoardMember.objects.create(
            full_name="Test Person",
            title="Test Title",
            description="Test Description",
            photo=portrait_image,
        )

        # Check that the thumbnail is square
        person.photo.open()
        saved_img = Image.open(person.photo)
        assert saved_img.size == (200, 200)

    def test_small_image_upscale(self, db: None) -> None:
        """Test that small images are upscaled to 200x200."""
        # Create a small image
        small_image = create_test_image(width=100, height=100, color="yellow")

        person = BoardMember.objects.create(
            full_name="Test Person",
            title="Test Title",
            description="Test Description",
            photo=small_image,
        )

        # Check that the thumbnail is still 200x200
        person.photo.open()
        saved_img = Image.open(person.photo)
        assert saved_img.size == (200, 200)

    def test_png_to_jpeg_conversion(self, db: None) -> None:
        """Test that PNG images are converted to JPEG for thumbnails."""
        # Create a PNG image
        png_image = create_test_image(width=500, height=500, img_format="PNG")

        person = BoardMember.objects.create(
            full_name="Test Person",
            title="Test Title",
            description="Test Description",
            photo=png_image,
        )

        # Check that the thumbnail is JPEG
        person.photo.open()
        saved_img = Image.open(person.photo)
        assert saved_img.format == "JPEG"
        assert saved_img.size == (200, 200)

    def test_transparency_handling(self, db: None) -> None:
        """Test that transparent images get a white background."""
        # Create a PNG with transparency
        img = Image.new("RGBA", (400, 400), (255, 0, 0, 128))  # Semi-transparent red
        img_bytes = BytesIO()
        img.save(img_bytes, format="PNG")
        img_bytes.seek(0)

        transparent_image = SimpleUploadedFile(
            name="transparent.png", content=img_bytes.read(), content_type="image/png"
        )

        person = BoardMember.objects.create(
            full_name="Test Person",
            title="Test Title",
            description="Test Description",
            photo=transparent_image,
        )

        # Check that the thumbnail has no transparency
        person.photo.open()
        saved_img = Image.open(person.photo)
        assert saved_img.mode == "RGB"  # No alpha channel
        assert saved_img.size == (200, 200)

    def test_photo_update(self, db: None) -> None:
        """Test that updating a photo creates new thumbnail."""
        # Create initial person with image
        first_image = create_test_image(width=600, height=600, color="red")
        person = BoardMember.objects.create(
            full_name="Test Person",
            title="Test Title",
            description="Test Description",
            photo=first_image,
        )

        first_photo_name = person.photo.name

        # Update with a new image
        second_image = create_test_image(width=800, height=800, color="blue")
        person.photo = second_image
        person.save()

        # Check that photo name changed
        assert person.photo.name != first_photo_name

        # Check new thumbnail
        person.photo.open()
        saved_img = Image.open(person.photo)
        assert saved_img.size == (200, 200)

    def test_no_photo_processing_without_change(self, db: None) -> None:
        """Test that photo is not reprocessed when saving without changes."""
        # Create person with image
        image = create_test_image(width=400, height=400)
        person = BoardMember.objects.create(
            full_name="Test Person",
            title="Test Title",
            description="Test Description",
            photo=image,
        )

        original_photo_name = person.photo.name

        # Update other fields without changing photo
        person.title = "New Title"
        person.save()

        # Photo name should not change
        assert person.photo.name == original_photo_name

    def test_all_model_types(self, db: None) -> None:
        """Test that image processing works for all person model types."""

        models: list[type[PersonAbstract]] = [
            BoardMember,
            TechnicalMember,
            ExplorerMember,
        ]

        for model_class in models:
            image = create_test_image(width=500, height=500)
            person = model_class.objects.create(
                full_name=f"Test {model_class.__name__}",
                title="Test Title",
                description="Test Description",
                photo=image,
            )

            # Check thumbnail created
            person.photo.open()
            saved_img = Image.open(person.photo)
            assert saved_img.size == (200, 200)
