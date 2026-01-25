# -*- coding: utf-8 -*-

from __future__ import annotations

import logging
import tempfile
from io import BytesIO
from pathlib import Path
from typing import BinaryIO

import ffmpeg
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
    def extract_thumbnail(video_file: BinaryIO) -> ContentFile[bytes]:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_dir_path = Path(tmp_dir)
            input_path = tmp_dir_path / "input.mp4"
            frame_path = tmp_dir_path / "frame.jpg"

            # Stream to disk (no full RAM load)
            video_file.seek(0)
            with input_path.open("wb") as f:
                for chunk in iter(lambda: video_file.read(1024 * 1024), b""):
                    f.write(chunk)

            try:
                # Open the file with ffmpeg
                stream = ffmpeg.input(str(input_path))  # type: ignore[no-untyped-call]

                # Accurate frame selection (safe for short / 1-frame videos)
                stream = ffmpeg.filter(stream, "thumbnail")

                stream = ffmpeg.output(
                    stream,
                    str(frame_path),
                    vframes=1,
                    format="image2",
                    vcodec="mjpeg",
                    **{"q:v": 2},
                )
                stdout, stderr = ffmpeg.run(
                    stream,
                    capture_stdout=True,
                    capture_stderr=True,
                )
            except ffmpeg.Error as e:
                raise RuntimeError("Error extracting the thumbnail with ffmpeg") from e

            if not frame_path.exists():
                raise FileNotFoundError(
                    f"FFMPEG did not generate the thumbnail:\n"
                    f"{stdout.decode()=}\n{stderr.decode()=}"
                )

            img = Image.open(frame_path)
            img.thumbnail((300, 200), Image.Resampling.LANCZOS)
            img = VideoProcessor._add_play_button_overlay(img)  # type: ignore[assignment]

            buffer = BytesIO()
            img.save(buffer, format="JPEG", quality=85)
            buffer.seek(0)

            return ContentFile(buffer.read())

    @staticmethod
    def _add_play_button_overlay(
        img: Image.Image,
    ) -> Image.Image:
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
