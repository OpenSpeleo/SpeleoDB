# -*- coding: utf-8 -*-

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from django.conf import settings
from storages.backends.s3boto3 import S3Boto3Storage  # type: ignore[attr-defined]


class BaseS3Storage(S3Boto3Storage):
    """Base class for S3 storage configurations."""

    bucket_name = settings.AWS_STORAGE_BUCKET_NAME
    custom_domain = settings.AWS_S3_CUSTOM_DOMAIN  # Use CDN/direct S3 URL
    file_overwrite = False

    # Cache control for performance
    object_parameters = {
        "CacheControl": "public, max-age=86400",
    }

    def get_available_name(self, name: str, max_length: int | None = None) -> Any:
        """Generate unique filename to avoid conflicts."""
        # Generate unique filename
        path = Path(name)
        unique_name = f"{uuid.uuid4().hex}_{path.name}"
        return super().get_available_name(unique_name, max_length)  # type: ignore[no-untyped-call]


class S3MediaStorage(BaseS3Storage):
    """Custom S3 storage for media files."""

    location = "media/default"  # Base location for media files
    default_acl = "private"
    # Use signed URLs for private files
    custom_domain = False  # type: ignore[assignment]


class PersonPhotoStorage(BaseS3Storage):
    """
    Custom S3 storage for person photos.

    Note: Requires S3 bucket policy to allow public read access to media/people/* path.
    """

    location = "media/people/photos"
    default_acl = (  # type: ignore[var-annotated]
        None  # No ACL - bucket policy handles public access
    )
    querystring_auth = False  # No signed URLs - relies on bucket policy


class StationResourceStorage(BaseS3Storage):
    """Custom S3 storage specifically for station resources."""

    location = "stations/resources"
    default_acl = "private"  # Keep files private for security
    # Use signed URLs for private files
    custom_domain = False  # type: ignore[assignment]
