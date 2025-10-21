# -*- coding: utf-8 -*-

from __future__ import annotations

import hashlib
from pathlib import Path

import requests
from django.core.files.uploadedfile import SimpleUploadedFile


def sha256_from_url(url: str) -> str:
    sha256 = hashlib.sha256()
    with requests.get(url, stream=True, timeout=10) as r:
        r.raise_for_status()  # ensure the request succeeded
        for chunk in r.iter_content(chunk_size=8192):
            if chunk:  # skip keep-alive chunks
                sha256.update(chunk)
    return sha256.hexdigest()


def create_test_image(name: str = "test.jpg") -> SimpleUploadedFile:
    """Create a test image file."""
    # Load real image from artifacts
    artifacts_dir = Path(__file__).parent / "artifacts"

    with (artifacts_dir / "image.jpg").open(mode="rb") as f:
        jpeg_content = f.read()

    return SimpleUploadedFile(name, jpeg_content, content_type="image/jpeg")


def create_test_video(name: str = "test.mp4") -> SimpleUploadedFile:
    """Create a test image file."""
    # Load real image from artifacts
    artifacts_dir = Path(__file__).parent / "artifacts"

    with (artifacts_dir / "video.mp4").open(mode="rb") as f:
        video_content = f.read()

    return SimpleUploadedFile(name, video_content, content_type="video/mp4")


def create_test_text_file(name: str = "test.txt") -> SimpleUploadedFile:
    """Create a test text file."""

    return SimpleUploadedFile(
        name,
        b"Cave survey report...",
        content_type="text/plain",
    )
