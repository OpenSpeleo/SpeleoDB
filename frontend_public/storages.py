# -*- coding: utf-8 -*-

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from django.conf import settings
from storages.backends.s3boto3 import S3Boto3Storage  # type: ignore[attr-defined]


class PersonPhotoStorage(S3Boto3Storage):
    """
    Custom S3 storage for person photos.

    Note: Requires S3 bucket policy to allow public read access to media/people/* path.
    See S3_BUCKET_POLICY.json for example.
    """

    bucket_name = settings.AWS_STORAGE_BUCKET_NAME
    location = "media/people/photos"
    default_acl: None = None  # No ACL - bucket policy handles public access
    file_overwrite = False
    custom_domain = settings.AWS_S3_CUSTOM_DOMAIN  # Use CDN/direct S3 URL
    querystring_auth = False  # No signed URLs - relies on bucket policy

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
