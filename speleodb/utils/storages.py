# -*- coding: utf-8 -*-

from __future__ import annotations

from django.conf import settings
from django.core.files.storage import FileSystemStorage

# Only import S3 storage when USE_S3 is True
if getattr(settings, "USE_S3", False):
    try:
        from storages.backends.s3boto3 import S3Boto3Storage

        HAS_S3_STORAGE = True
    except ImportError:
        # Fall back to local storage if django-storages is not available
        HAS_S3_STORAGE = False
        print("Warning: django-storages not installed, falling back to local storage")
else:
    HAS_S3_STORAGE = False


class MediaStorage:
    """Factory for media storage - returns S3 or local storage based on settings."""

    def __new__(cls):
        if getattr(settings, "USE_S3", False) and HAS_S3_STORAGE:
            return S3MediaStorage()
        return FileSystemStorage()


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

        def get_available_name(self, name: str, max_length=None) -> str:
            """Generate unique filename to avoid conflicts."""
            import uuid
            from pathlib import Path

            # Generate unique filename
            path = Path(name)
            unique_name = f"{uuid.uuid4().hex}_{path.name}"
            return super().get_available_name(unique_name, max_length)

else:
    # Placeholder classes when S3 is not available
    class S3MediaStorage:
        def __init__(self):
            raise ImportError(
                "S3 storage not available - USE_S3 is False or django-storages not installed"
            )

    class PublicMediaStorage:
        def __init__(self):
            raise ImportError(
                "S3 storage not available - USE_S3 is False or django-storages not installed"
            )

    class StationResourceStorage:
        def __init__(self):
            raise ImportError(
                "S3 storage not available - USE_S3 is False or django-storages not installed"
            )


class LocalStationResourceStorage(FileSystemStorage):
    """Local file storage for station resources during development."""

    def __init__(self, *args, **kwargs):
        # Set location to a subdirectory for station resources
        if hasattr(settings, "MEDIA_ROOT"):
            location = f"{settings.MEDIA_ROOT}/stations/resources"
        else:
            location = "stations/resources"

        super().__init__(location=location, *args, **kwargs)

        # Ensure directory exists
        import os

        os.makedirs(self.location, exist_ok=True)

    def _save(self, name: str, content):
        """Save file with unique name to avoid conflicts."""
        import uuid
        from pathlib import Path

        # Generate unique filename for local storage too
        path = Path(name)
        unique_name = f"{uuid.uuid4().hex}_{path.name}"

        return super()._save(unique_name, content)
