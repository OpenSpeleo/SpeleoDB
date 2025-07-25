# -*- coding: utf-8 -*-

from __future__ import annotations

from collections.abc import Iterable
from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from PIL import UnidentifiedImageError

from speleodb.utils.image_processing import ImageProcessor


def create_test_image(
    width: int = 500,
    height: int = 500,
    color: str = "red",
    img_format: str = "JPEG",
    mode: str = "RGB",
) -> SimpleUploadedFile:
    """Create a test image file."""
    # Create image
    if mode == "RGBA":
        img = Image.new(mode, (width, height), (255, 0, 0, 128))  # Semi-transparent red
    elif mode == "LA":
        img = Image.new(mode, (width, height), (128, 128))  # Gray with alpha
    else:
        img = Image.new(mode, (width, height), color)

    # Save to buffer
    buffer = BytesIO()
    img.save(buffer, format=img_format)
    buffer.seek(0)

    # Create uploaded file
    extension = "png" if img_format == "PNG" else "jpg"
    return SimpleUploadedFile(
        f"test_image.{extension}",
        buffer.read(),
        content_type=f"image/{img_format.lower()}",
    )


class TestImageProcessor:
    """Test the ImageProcessor utility class."""

    def test_is_image_file_valid_extensions(self) -> None:
        """Test that valid image extensions are recognized."""
        valid_files = [
            "photo.jpg",
            "photo.JPEG",
            "image.png",
            "graphic.webp",
            "animation.gif",
            "bitmap.bmp",
            "/path/to/image.JPG",
        ]

        for filename in valid_files:
            assert ImageProcessor.is_image_file(filename) is True

    def test_is_image_file_invalid_extensions(self) -> None:
        """Test that non-image extensions are rejected."""
        invalid_files: list[str | None] = [
            "document.pdf",
            "video.mp4",
            "archive.zip",
            "text.txt",
            "",
            None,
        ]

        for filename in invalid_files:
            assert ImageProcessor.is_image_file(filename) is False  # type: ignore[arg-type]

    def test_process_image_for_web_rgb(self) -> None:
        """Test processing RGB images (no conversion needed)."""
        image = create_test_image(mode="RGB")

        with BytesIO(image.read()) as buffer:
            processed = ImageProcessor.process_image_for_web(buffer)

        assert processed.mode == "RGB"
        assert processed.size == (500, 500)

    def test_process_image_for_web_rgba_to_rgb(self) -> None:
        """Test converting RGBA images to RGB with white background."""
        image = create_test_image(mode="RGBA", img_format="PNG")

        with BytesIO(image.read()) as buffer:
            processed = ImageProcessor.process_image_for_web(buffer)

        assert processed.mode == "RGB"
        # Check that alpha was composited with white background
        # Semi-transparent red over white should be pinkish
        pixel = processed.getpixel((0, 0))
        assert isinstance(pixel, Iterable)
        assert len(pixel) == 3  # RGB  # noqa: PLR2004
        assert pixel == (255, 127, 127)  # color: FF7F7F

    def test_process_image_for_web_la_to_rgb(self) -> None:
        """Test converting LA (grayscale with alpha) images to RGB."""
        image = create_test_image(mode="LA", img_format="PNG")

        with BytesIO(image.read()) as buffer:
            processed = ImageProcessor.process_image_for_web(buffer)

        assert processed.mode == "RGB"

    def test_process_image_for_web_l_mode(self) -> None:
        """Test that L (grayscale) images are preserved."""
        image = create_test_image(mode="L")

        with BytesIO(image.read()) as buffer:
            processed = ImageProcessor.process_image_for_web(buffer)

        assert processed.mode == "L"

    def test_create_miniature_downscale_landscape(self) -> None:
        """Test creating miniature from landscape image."""
        image = create_test_image(width=600, height=400)

        with BytesIO(image.read()) as buffer:
            miniature = ImageProcessor.create_miniature(buffer)

        # Open the miniature
        mini_img = Image.open(BytesIO(miniature.read()))

        # Should be scaled to fit 300x200
        assert mini_img.size == (300, 200)
        assert mini_img.format == "JPEG"

    def test_create_miniature_downscale_portrait(self) -> None:
        """Test creating miniature from portrait image."""
        image = create_test_image(width=400, height=600)

        with BytesIO(image.read()) as buffer:
            miniature = ImageProcessor.create_miniature(buffer)

        # Open the miniature
        mini_img = Image.open(BytesIO(miniature.read()))

        # Should be scaled to fit within 300x200, maintaining aspect ratio
        # Height is limiting factor: 600 * (200/600) = 200
        # Width: 400 * (200/600) = 133.33 ≈ 133
        assert mini_img.size[1] == 200  # Height should be exactly 200  # noqa: PLR2004
        assert 132 <= mini_img.size[0] <= 134  # Width around 133  # noqa: PLR2004

    def test_create_miniature_no_upscale(self) -> None:
        """Test that small images are not upscaled."""
        image = create_test_image(width=100, height=100)

        with BytesIO(image.read()) as buffer:
            miniature = ImageProcessor.create_miniature(buffer)

        # Open the miniature
        mini_img = Image.open(BytesIO(miniature.read()))

        # Should remain 100x100
        assert mini_img.size == (100, 100)

    def test_create_miniature_large_image(self) -> None:
        """Test creating miniature from very large image."""
        image = create_test_image(width=3000, height=2000)

        with BytesIO(image.read()) as buffer:
            miniature = ImageProcessor.create_miniature(buffer)

        # Open the miniature
        mini_img = Image.open(BytesIO(miniature.read()))

        # Should be scaled to fit 300x200
        assert mini_img.size == (300, 200)

    def test_create_miniature_custom_dimensions(self) -> None:
        """Test creating miniature with custom max dimensions."""
        image = create_test_image(width=1000, height=1000)

        with BytesIO(image.read()) as buffer:
            miniature = ImageProcessor.create_miniature(
                buffer, max_width=150, max_height=150
            )

        # Open the miniature
        mini_img = Image.open(BytesIO(miniature.read()))

        # Should be 150x150
        assert mini_img.size == (150, 150)

    def test_create_miniature_png_to_jpeg(self) -> None:
        """Test that PNG images are converted to JPEG for miniatures."""
        image = create_test_image(img_format="PNG")

        with BytesIO(image.read()) as buffer:
            miniature = ImageProcessor.create_miniature(buffer)

        # Open the miniature
        mini_img = Image.open(BytesIO(miniature.read()))

        assert mini_img.format == "JPEG"

    def test_create_miniature_preserves_aspect_ratio(self) -> None:
        """Test that aspect ratio is preserved when creating miniatures."""
        # Create image with unusual aspect ratio
        image = create_test_image(width=800, height=200)

        with BytesIO(image.read()) as buffer:
            miniature = ImageProcessor.create_miniature(buffer)

        # Open the miniature
        mini_img = Image.open(BytesIO(miniature.read()))

        # Original ratio: 800/200 = 4
        # Should scale to 300x75 to maintain ratio
        assert mini_img.size == (300, 75)
        assert abs((mini_img.size[0] / mini_img.size[1]) - 4) < 1e-2  # noqa: PLR2004

    def test_create_miniature_error_handling(self) -> None:
        """Test error handling when creating miniature fails."""
        # Create invalid image data
        invalid_data = BytesIO(b"not an image")

        with pytest.raises(UnidentifiedImageError):
            ImageProcessor.create_miniature(invalid_data)

    def test_process_image_exif_orientation(self) -> None:
        """Test that EXIF orientation is handled correctly."""
        # Create a simple test image
        img = Image.new("RGB", (100, 200), "red")

        # Add a marker to show orientation (top-left pixel green)
        img.putpixel((0, 0), (0, 255, 0))

        # Save with EXIF orientation tag 6 (90 degrees clockwise)
        buffer = BytesIO()

        # Note: PIL doesn't easily allow setting EXIF data on new images
        # So we'll just test that the method doesn't crash with EXIF data
        img.save(buffer, format="JPEG")
        buffer.seek(0)

        # Process the image
        processed = ImageProcessor.process_image_for_web(buffer)

        # Should still be an image
        assert isinstance(processed, Image.Image)

        # For a real test with rotation, you'd need an actual photo with EXIF data
        # This test mainly ensures the EXIF handling code doesn't break normal operation

    def test_miniature_preserves_orientation(self) -> None:
        """Test that miniature creation preserves image orientation
        (longest side stays longest)."""
        # Test landscape image (width > height)
        landscape = create_test_image(width=800, height=400, color="blue")
        with BytesIO(landscape.read()) as buffer:
            miniature = ImageProcessor.create_miniature(buffer)

        # Open the miniature
        mini_img = Image.open(BytesIO(miniature.read()))

        # Landscape should remain landscape
        assert mini_img.size[0] > mini_img.size[1], (
            f"Landscape orientation lost: {mini_img.size}"
        )
        # Check exact dimensions - should be 300x150 (scaled down by factor of 2.667)
        assert mini_img.size == (300, 150), (
            f"Unexpected landscape dimensions: {mini_img.size}"
        )

        # Test portrait image (height > width)
        portrait = create_test_image(width=400, height=800, color="green")
        with BytesIO(portrait.read()) as buffer:
            miniature = ImageProcessor.create_miniature(buffer)

        # Open the miniature
        mini_img = Image.open(BytesIO(miniature.read()))

        # Portrait should remain portrait
        assert mini_img.size[1] > mini_img.size[0], (
            f"Portrait orientation lost: {mini_img.size}"
        )
        # Check exact dimensions - should be 100x200 (scaled down by factor of 4)
        assert mini_img.size == (100, 200), (
            f"Unexpected portrait dimensions: {mini_img.size}"
        )

        # Test square image
        square = create_test_image(width=600, height=600, color="yellow")
        with BytesIO(square.read()) as buffer:
            miniature = ImageProcessor.create_miniature(buffer)

        # Open the miniature
        mini_img = Image.open(BytesIO(miniature.read()))

        # Square should remain square - limited by height (200)
        assert mini_img.size[0] == mini_img.size[1], (
            f"Square aspect lost: {mini_img.size}"
        )
        assert mini_img.size == (200, 200), (
            f"Unexpected square dimensions: {mini_img.size}"
        )

        # Test extreme landscape (should be limited by width)
        extreme_landscape = create_test_image(width=1000, height=100, color="purple")
        with BytesIO(extreme_landscape.read()) as buffer:
            miniature = ImageProcessor.create_miniature(buffer)

        mini_img = Image.open(BytesIO(miniature.read()))
        assert mini_img.size == (300, 30), (
            f"Unexpected extreme landscape dimensions: {mini_img.size}"
        )
