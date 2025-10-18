# -*- coding: utf-8 -*-

from __future__ import annotations

import contextlib
from pathlib import Path
from typing import TYPE_CHECKING

import jsonschema_rs
import orjson
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator

if TYPE_CHECKING:
    from django.db.models.fields.files import FieldFile


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


class AttachmentValidator(FileExtensionValidator):
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


class GeoJsonValidator(FileExtensionValidator):
    """
    Validator for GEOJSON files. Validates with JSON Schema.
    """

    # Define allowed extensions for each resource type
    ALLOWED_EXTENSIONS = ["json", "geojson"]

    def __init__(self) -> None:
        # Copied from: https://geojson.org/schema/GeoJSON.json
        schema = orjson.loads(
            Path("speleodb/surveys/schemas/geojson.json").read_bytes()
        )
        self.schema_validator = jsonschema_rs.validator_for(schema)

    def __call__(self, value: FieldFile) -> None:  # type: ignore[override]
        # 1. Validate the file extension
        # ------------------------------
        extension = Path(value.name).suffix[1:].lower()  # type: ignore[arg-type]
        if extension not in self.ALLOWED_EXTENSIONS:
            raise ValidationError(
                message=(
                    "File extension “%(extension)s” is not allowed. "
                    "Allowed extensions are: %(allowed_extensions)s."
                ),
                code="invalid_extension",
                params={
                    "extension": extension,
                    "allowed_extensions": ", ".join(self.ALLOWED_EXTENSIONS),
                },
            )

        file = None
        try:
            # 2. Validate the JSON SCHEMA
            # ---------------------------

            # NOTE: value.open() does not return a context manager
            file = value.open(mode="rb")
            data = orjson.loads(file.read())
            if not self.schema_validator.is_valid(data):
                raise ValidationError(
                    message=(
                        "The file uploaded does not appear to be a valid GeoJSON "
                        "file. Check https://geojson.org/schema/GeoJSON.json for "
                        "the validation schema being used."
                    ),
                    code="invalid_jsonschema",
                )

            # NOTE: do not close the file here, as it may be managed by Django

        finally:
            with contextlib.suppress(
                AttributeError, OSError, ValueError, AttributeError
            ):
                if file is not None:
                    file.seek(0)
