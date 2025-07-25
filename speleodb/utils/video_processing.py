# -*- coding: utf-8 -*-

from __future__ import annotations

import logging
import tempfile
from io import BytesIO
from pathlib import Path
from typing import BinaryIO

import imageio
from django.core.files.base import ContentFile
from PIL import Image
from PIL import ImageDraw

logger = logging.getLogger(__name__)


class VideoProcessor:
    """Utility class for processing videos, including thumbnail extraction."""

    # Supported video extensions
    VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".wmv", ".flv", ".webm"}

    @staticmethod
    def is_video_file(filename: str) -> bool:
        """Check if file is a video based on extension."""
        if not filename:
            return False
        return Path(filename).suffix.lower() in VideoProcessor.VIDEO_EXTENSIONS

    @staticmethod
    def extract_thumbnail(
        video_file: BinaryIO, time_offset: float = 1.0
    ) -> ContentFile[bytes]:
        """
        Extract a thumbnail from video at specified time offset.

        Uses imageio-ffmpeg for real frame extraction.

        Args:
            video_file: File-like object containing the video
            time_offset: Time in seconds to extract frame

        Returns:
            ContentFile containing the thumbnail image in JPEG format
        """
        # Reset file pointer
        video_file.seek(0)

        # Read video and extract frame
        # Note: imageio needs a filename or path, so we'll save to temp file
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_file = Path(tmp_dir) / "temp_video.mp4"
            with tmp_file.open(mode="wb") as f:
                f.write(video_file.read())

            # Get video reader
            with imageio.get_reader(tmp_file.resolve()) as reader:
                # Get video metadata
                fps = reader.get_meta_data().get("fps", 30)  # type: ignore[attr-defined]
                frame_number = int(time_offset * fps)

                # Read the specific frame
                frame = None
                for i, current_frame in enumerate(reader):  # type: ignore[var-annotated,arg-type]
                    frame = current_frame
                    if i >= frame_number:
                        break

                if frame is None:
                    raise ValueError("No frames found in video")

                # Convert numpy array to PIL Image
                img = Image.fromarray(frame)

                # Resize to max 300x200 maintaining aspect ratio
                img.thumbnail((300, 200), Image.Resampling.LANCZOS)

                # Add play button overlay
                img = VideoProcessor._add_play_button_overlay(img)

                # Save to buffer
                buffer = BytesIO()
                img.save(buffer, format="JPEG", quality=85)
                buffer.seek(0)

                logger.info("Successfully extracted video thumbnail using imageio")
                return ContentFile(buffer.read())

    @staticmethod
    def _add_play_button_overlay(img: Image.Image) -> Image.Image:
        """Add a semi-transparent play button overlay to the image."""
        # Create a copy to avoid modifying the original
        img = img.copy()

        # Create an overlay with transparency
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        # Calculate play button position and size
        center_x, center_y = img.width // 2, img.height // 2
        button_radius = min(img.width, img.height) // 6

        # Draw semi-transparent circle background
        circle_bbox = [
            center_x - button_radius,
            center_y - button_radius,
            center_x + button_radius,
            center_y + button_radius,
        ]
        draw.ellipse(circle_bbox, fill=(0, 0, 0, 128))  # Semi-transparent black

        # Draw play triangle
        triangle_size = button_radius // 2
        triangle_points = [
            (center_x - triangle_size // 2, center_y - triangle_size),
            (center_x - triangle_size // 2, center_y + triangle_size),
            (center_x + triangle_size, center_y),
        ]
        draw.polygon(triangle_points, fill=(255, 255, 255, 255))  # White

        # Convert back to RGB and composite
        img = img.convert("RGBA")
        img = Image.alpha_composite(img, overlay)
        return img.convert("RGB")

    @staticmethod
    def create_placeholder() -> ContentFile[bytes]:
        """Create a generic video placeholder image (for backwards compatibility)."""
        # Create a dark gray placeholder
        img = Image.new("RGB", (300, 200), color=(64, 64, 64))
        img = VideoProcessor._add_play_button_overlay(img)

        # Save to buffer
        buffer = BytesIO()
        img.save(buffer, format="JPEG", quality=85)
        buffer.seek(0)

        return ContentFile(buffer.read())
