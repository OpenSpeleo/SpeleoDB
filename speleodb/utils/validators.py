# -*- coding: utf-8 -*-

from __future__ import annotations

from django.core.validators import FileExtensionValidator


class ImageWithHeicSupportValidator(FileExtensionValidator):
    """
    Validator that allows HEIC/HEIF files for upload (they will be converted).

    This validator allows HEIC/HEIF extensions during upload, but the application
    will transparently convert them to JPEG before storage.
    """

    storage_extensions: list[str]

    def __init__(self, allowed_extensions: list[str]) -> None:
        # Add HEIC/HEIF to the allowed list for validation
        extended_extensions = [*list(allowed_extensions), "heic", "heif"]
        super().__init__(allowed_extensions=extended_extensions)

        # Store the original allowed extensions (without HEIC/HEIF)
        self.storage_extensions = allowed_extensions

    def get_storage_extensions(self) -> list[str]:
        """Get the list of extensions allowed for storage (excludes HEIC/HEIF)."""
        return self.storage_extensions


class StationResourceFileValidator(FileExtensionValidator):
    """
    Validator for StationResource files that allows HEIC/HEIF for photos.

    This validator allows HEIC/HEIF extensions during upload for photos,
    but the application will transparently convert them to JPEG before storage.
    """

    # Define allowed extensions for each resource type
    IMAGE_EXTENSIONS = ["jpg", "jpeg", "png", "gif", "bmp", "webp"]
    VIDEO_EXTENSIONS = ["mp4", "avi", "mov", "wmv", "flv", "webm"]
    DOCUMENT_EXTENSIONS = ["pdf", "doc", "docx", "txt", "rtf"]
    SKETCH_EXTENSIONS = ["svg"]

    def __init__(self) -> None:
        # Combine all extensions and add HEIC/HEIF for upload
        all_extensions = (
            *self.IMAGE_EXTENSIONS,
            *["heic", "heif"],  # Allow HEIC upload (will be converted)
            *self.VIDEO_EXTENSIONS,
            *self.DOCUMENT_EXTENSIONS,
            *self.SKETCH_EXTENSIONS,
        )
        super().__init__(allowed_extensions=all_extensions)
