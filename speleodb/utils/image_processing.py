# -*- coding: utf-8 -*-

from __future__ import annotations

import logging
from io import BytesIO
from pathlib import Path
from typing import BinaryIO

from django.core.files.base import ContentFile
from PIL import Image
from PIL.ImageOps import exif_transpose

# Register HEIF plugin with Pillow on import
from pillow_heif import register_heif_opener  # type: ignore[attr-defined]

register_heif_opener()

logger = logging.getLogger(__name__)


class ImageProcessor:
    """Utility class for processing images, including miniature generation."""

    # Supported image extensions
    IMAGE_EXTENSIONS = {
        ".jpg",
        ".jpeg",
        ".png",
        ".webp",
        ".gif",
        ".bmp",
        ".heic",
        ".heif",
    }

    @staticmethod
    def process_image_for_web(image_file: BinaryIO) -> Image.Image:
        """
        Convert image to RGB format suitable for web display.

        Handles RGBA, LA, and other formats by converting to RGB with white background.
        Also applies EXIF orientation to the actual pixel data.
        """
        image_file.seek(0)
        img = Image.open(image_file)

        img = exif_transpose(img, in_place=False)  # type: ignore[assignment]

        # Convert RGBA to RGB if necessary
        if img.mode in ("RGBA", "LA"):
            # Create a white background
            background = Image.new("RGB", img.size, (255, 255, 255))

            if img.mode == "RGBA":
                background.paste(img, mask=img.split()[3])  # Use alpha channel as mask
            else:
                background.paste(img, mask=img.split()[1])  # LA mode

            img = background  # type: ignore[assignment]

        elif img.mode not in ("RGB", "L"):
            img = img.convert("RGB")  # type: ignore[assignment]

        return img

    @staticmethod
    def create_miniature(
        image_file: BinaryIO, max_width: int = 300, max_height: int = 200
    ) -> ContentFile[bytes]:
        """
        Create a miniature with preserved aspect ratio.

        The image will be scaled down to fit within max_width x max_height,
        maintaining the original aspect ratio. Images smaller than the max
        dimensions will not be upscaled.

        Args:
            image_file: File-like object containing the image
            max_width: Maximum width for the miniature
            max_height: Maximum height for the miniature

        Returns:
            ContentFile containing the miniature image in JPEG format
        """
        # Process image for web compatibility (this also handles EXIF orientation)
        img = ImageProcessor.process_image_for_web(image_file)

        # Calculate new dimensions preserving aspect ratio
        width, height = img.size

        # Calculate scaling ratio (only downscale, never upscale)
        width_ratio = max_width / width if width > max_width else 1
        height_ratio = max_height / height if height > max_height else 1
        ratio = min(width_ratio, height_ratio)

        if ratio < 1:
            # Need to resize
            new_width = int(width * ratio)
            new_height = int(height * ratio)
            img_resized = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        else:
            # Image is already small enough
            img_resized = img

        # Save to buffer in JPEG format without EXIF data
        buffer = BytesIO()
        img_resized.save(buffer, format="JPEG", quality=85, optimize=True)
        buffer.seek(0)

        return ContentFile(buffer.read())

    @staticmethod
    def is_image_file(filename: str) -> bool:
        """
        Check if file is an image based on extension.

        Args:
            filename: The filename to check

        Returns:
            True if the file extension indicates an image file
        """
        if not filename:
            return False

        return Path(filename).suffix.lower() in ImageProcessor.IMAGE_EXTENSIONS
