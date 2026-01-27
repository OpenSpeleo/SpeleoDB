# -*- coding: utf-8 -*-

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from speleodb.utils.video_processing import VideoProcessor


class TestVideoProcessor:
    """Test VideoProcessor utility class."""

    def test_is_video_file(self) -> None:
        """Test video file detection."""
        # Valid video extensions
        assert VideoProcessor.is_video_file("test.mp4") is True
        assert VideoProcessor.is_video_file("test.MP4") is True
        assert VideoProcessor.is_video_file("test.avi") is True
        assert VideoProcessor.is_video_file("test.mov") is True
        assert VideoProcessor.is_video_file("test.wmv") is True
        assert VideoProcessor.is_video_file("test.flv") is True
        assert VideoProcessor.is_video_file("test.webm") is True

        # Invalid extensions
        assert VideoProcessor.is_video_file("test.jpg") is False
        assert VideoProcessor.is_video_file("test.png") is False
        assert VideoProcessor.is_video_file("test.pdf") is False
        assert VideoProcessor.is_video_file("test.txt") is False
        assert VideoProcessor.is_video_file("") is False
        assert VideoProcessor.is_video_file(None) is False  # type: ignore[arg-type]

    def test_create_placeholder(self) -> None:
        """Test placeholder creation."""
        content = VideoProcessor.create_placeholder()

        # Check it's a ContentFile
        assert hasattr(content, "read")

        # Read and verify it's a valid image
        content.seek(0)
        img = Image.open(content)
        assert img.format == "JPEG"
        assert img.size == (300, 200)

    def test_extract_thumbnail_with_real_video(self) -> None:
        """Test thumbnail extraction with a real video file."""
        artifacts_dir = Path(__file__).parent.parent.parent / "api/v1/tests/artifacts"

        with (artifacts_dir / "video.mp4").open(mode="rb") as f:
            content = VideoProcessor.extract_thumbnail(f)

            # Verify it created a valid thumbnail
            content.seek(0)
            img = Image.open(content)
            assert img.format == "JPEG"
            # Check size in bounds (may not be exactly 300x200 due to aspect ratio)
            assert img.width <= 300  # noqa: PLR2004
            assert img.height <= 200  # noqa: PLR2004

    def test_extract_thumbnail_error_handling(self) -> None:
        """Test error handling in thumbnail extraction."""
        # Test with invalid video data
        fake_video = BytesIO(b"not a video")

        # Should raise an exception
        with pytest.raises(
            RuntimeError, match="Error extracting the thumbnail with ffmpeg"
        ):
            VideoProcessor.extract_thumbnail(fake_video)

    def test_add_play_button_overlay(self) -> None:
        """Test that play button overlay is added correctly."""
        # Create a test image
        test_img = Image.new("RGB", (300, 200), color=(100, 100, 100))

        # Add overlay
        result = VideoProcessor._add_play_button_overlay(test_img)  # noqa: SLF001

        # Check it's still the right size and format
        assert result.size == (300, 200)
        assert result.mode == "RGB"

        # Check that it's different from the original (overlay was added)
        assert list(test_img.get_flattened_data()) != list(result.get_flattened_data())
