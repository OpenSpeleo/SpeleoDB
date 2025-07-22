# -*- coding: utf-8 -*-

from __future__ import annotations

import uuid
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Any

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from storages.backends.s3boto3 import S3Boto3Storage  # type: ignore[attr-defined]

# Import the existing storage utilities
from speleodb.utils.storages import HAS_S3_STORAGE
from speleodb.utils.storages import LocalStationResourceStorage

if TYPE_CHECKING:
    from django.core.files.storage import Storage


def get_person_photo_storage() -> Storage:
    """Get the appropriate storage backend for person photos."""
    if HAS_S3_STORAGE:
        return PersonPhotoStorage()  # type: ignore[no-untyped-call]
    return LocalPersonPhotoStorage()


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


class LocalPersonPhotoStorage(LocalStationResourceStorage):
    """Local file storage for person photos - extends LocalStationResourceStorage."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        # Don't call parent init, override completely
        location = Path(settings.MEDIA_ROOT) / "people" / "photos"

        # Import here to avoid circular import

        FileSystemStorage.__init__(self, *args, location=location, **kwargs)  # type: ignore[misc]

        # Ensure directory exists
        Path(self.location).mkdir(parents=True, exist_ok=True)
