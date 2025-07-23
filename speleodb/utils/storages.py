# -*- coding: utf-8 -*-

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from django.conf import settings
from storages.backends.s3boto3 import S3Boto3Storage  # type: ignore[attr-defined]


class S3MediaStorage(S3Boto3Storage):
    """Custom S3 storage for media files."""

    bucket_name = settings.AWS_STORAGE_BUCKET_NAME
    location = "media"
    default_acl = "private"
    file_overwrite = False
    custom_domain = False  # Use signed URLs for private files


class PublicMediaStorage(S3Boto3Storage):
    """Custom S3 storage for public media files."""

    bucket_name = settings.AWS_STORAGE_BUCKET_NAME
    location = "media/public"
    default_acl = "public-read"
    file_overwrite = False
    custom_domain = settings.AWS_S3_CUSTOM_DOMAIN


class StationResourceStorage(S3Boto3Storage):
    """Custom S3 storage specifically for station resources."""

    bucket_name = settings.AWS_STORAGE_BUCKET_NAME
    location = "stations/resources"
    default_acl = "private"  # Keep files private for security
    file_overwrite = False
    custom_domain = False  # Use signed URLs for private access

    def get_available_name(self, name: str, max_length: int | None = None) -> Any:
        """Generate unique filename to avoid conflicts."""
        # Generate unique filename
        path = Path(name)
        unique_name = f"{uuid.uuid4().hex}_{path.name}"
        return super().get_available_name(unique_name, max_length)  # type: ignore[no-untyped-call]
