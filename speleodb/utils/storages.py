# -*- coding: utf-8 -*-

from __future__ import annotations

import uuid
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Any

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from storages.backends.s3boto3 import S3Boto3Storage  # type: ignore[attr-defined]

if TYPE_CHECKING:
    from django.core.files.storage import Storage

# Only import S3 storage when USE_S3 is True
HAS_S3_STORAGE = getattr(settings, "USE_S3", False)


class MediaStorage:
    """Factory for media storage - returns S3 or local storage based on settings."""

    def __new__(cls) -> S3MediaStorage | FileSystemStorage:  # type: ignore[misc]
        if HAS_S3_STORAGE:
            return S3MediaStorage()  # type: ignore[no-untyped-call]
        return FileSystemStorage()


def get_station_resource_storage() -> Storage:
    """Get the appropriate storage backend for station resources."""
    if HAS_S3_STORAGE:
        return StationResourceStorage()  # type: ignore[no-untyped-call]

    return LocalStationResourceStorage()


# Only define S3 classes if S3 is enabled and available
if HAS_S3_STORAGE:

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

else:
    # Placeholder classes when S3 is not available
    class S3MediaStorage:  # type: ignore[no-redef]
        def __init__(self) -> None:
            raise ImportError(
                "S3 storage not available - USE_S3 is False or django-storages not "
                "installed"
            )

    class PublicMediaStorage:  # type: ignore[no-redef]
        def __init__(self) -> None:
            raise ImportError(
                "S3 storage not available - USE_S3 is False or django-storages not "
                "installed"
            )

    class StationResourceStorage:  # type: ignore[no-redef]
        def __init__(self) -> None:
            raise ImportError(
                "S3 storage not available - USE_S3 is False or django-storages not "
                "installed"
            )


class LocalStationResourceStorage(FileSystemStorage):
    """Local file storage for station resources during development."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        # Set location to a subdirectory for station resources
        if not hasattr(settings, "MEDIA_ROOT"):
            raise ValueError("`MEDIA_ROOT` is not defined")

        location = Path(settings.MEDIA_ROOT) / "stations" / "resources"

        super().__init__(*args, location=location, **kwargs)  # type: ignore[misc]

        # Ensure directory exists
        Path(self.location).mkdir(parents=True, exist_ok=True)

    def _save(self, name: str, content: Any) -> Any:
        """Save file with unique name to avoid conflicts."""

        # Generate unique filename for local storage too
        path = Path(name)
        unique_name = f"{uuid.uuid4().hex}_{path.name}"

        return super()._save(unique_name, content)  # type: ignore[misc]
