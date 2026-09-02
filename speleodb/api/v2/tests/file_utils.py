# -*- coding: utf-8 -*-

from __future__ import annotations

import hashlib
from pathlib import Path
from urllib.parse import urlsplit
from urllib.parse import urlunsplit

import requests
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile


def sha256_from_url(url: str) -> str:
    sha256 = hashlib.sha256()
    request_url, headers = _internal_s3_request(url)
    with requests.api.get(
        request_url,
        headers=headers,
        stream=True,
        timeout=10,
    ) as r:
        r.raise_for_status()  # ensure the request succeeded
        for chunk in r.iter_content(chunk_size=8192):
            if chunk:  # skip keep-alive chunks
                sha256.update(chunk)
    return sha256.hexdigest()


def _internal_s3_request(url: str) -> tuple[str, dict[str, str]]:
    """Route test downloads internally while preserving the signed host."""
    browser_endpoint = getattr(settings, "AWS_S3_BROWSER_ENDPOINT_URL", None)
    service_endpoint = getattr(settings, "AWS_S3_ENDPOINT_URL", None)
    if not browser_endpoint or not service_endpoint:
        return url, {}

    parsed_url = urlsplit(url)
    browser_url = urlsplit(browser_endpoint)
    service_url = urlsplit(service_endpoint)
    if parsed_url.netloc != browser_url.netloc or not service_url.netloc:
        return url, {}

    request_url = urlunsplit(
        parsed_url._replace(
            scheme=service_url.scheme,
            netloc=service_url.netloc,
        )
    )
    if request_url == url:
        return url, {}

    # SigV4 signs the Host header. Connect through the Compose service name but
    # retain the browser-facing host used when Django generated the signature.
    return request_url, {"Host": parsed_url.netloc}


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
