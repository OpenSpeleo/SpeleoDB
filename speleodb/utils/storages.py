# -*- coding: utf-8 -*-

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from django.conf import settings
from storages.backends.s3 import S3Storage


class BaseS3Storage(S3Storage):
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

    if settings.DEBUG:

        def url(
            self,
            name: Any,
            parameters: Any = None,
            expire: Any = None,
            http_method: Any = None,
        ) -> Any:
            # Let the parent class build the URL
            url = super().url(  # type: ignore[no-untyped-call]
                name, parameters=parameters, expire=expire, http_method=http_method
            )

            # Force HTTP if using a non-SSL endpoint (useful for MinIO local dev)
            if (
                isinstance(self.custom_domain, str)
                and "localhost" in self.custom_domain
            ):
                return url.replace("https://", "http://", 1)

            return url


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


class AttachmentStorage(S3Storage):
    """Private S3 storage for Station Resources uploads.

    Files are stored under the "attachments/" prefix; the model's
    upload_to callable should place them into "project.id/station.id/" subfolder.
    """

    """Custom S3 storage specifically for attachments."""

    bucket_name = BaseS3Storage.bucket_name
    file_overwrite = BaseS3Storage.file_overwrite

    # Cache control for performance
    object_parameters = BaseS3Storage.object_parameters

    location = "attachments"
    default_acl = "private"  # Keep files private for security

    # Use signed URLs for private files
    custom_domain = False


class GeoJSONStorage(S3Storage):
    """Private S3 storage for GeoJSON uploads.

    Files are stored under the "geojson/" prefix; the model's upload_to
    callable should place them into "project.id/commit.sha/" subfolder.
    """

    # NOTE: This class can **not** inherit from BaseS3Storage because it uses a
    # different `get_available_name()` that generates a path based on the project ID
    # and commit SHA.

    bucket_name = BaseS3Storage.bucket_name
    file_overwrite = BaseS3Storage.file_overwrite

    # Cache control for performance
    object_parameters = BaseS3Storage.object_parameters

    location = "geojson"
    default_acl = "private"

    # Use signed URLs for private files
    custom_domain = False


class S3StaticStorage(S3Storage):
    """Public S3 storage for static files with long cache and URL timestamp."""

    querystring_auth = False

    # Prefix for all static assets in the bucket
    location = "staticfiles"

    # 2min caching for static assets
    object_parameters = {"CacheControl": "public, max-age=120"}
