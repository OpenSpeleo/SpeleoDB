# -*- coding: utf-8 -*-

from __future__ import annotations

import contextlib
import logging
import os
import uuid
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Any
from typing import Self

from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.validators import MaxValueValidator
from django.core.validators import MinValueValidator
from django.db import models

from speleodb.utils.document_processing import DocumentProcessor
from speleodb.utils.image_processing import ImageProcessor
from speleodb.utils.storages import AttachmentStorage
from speleodb.utils.validators import AttachmentValidator
from speleodb.utils.video_processing import VideoProcessor

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from speleodb.surveys.models import LogEntry


class Station(models.Model):
    """
    Represents a survey station where field data collection occurs.
    Stations are positioned using latitude/longitude coordinates.
    """

    # type checking
    resources: models.QuerySet[StationResource]
    log_entries: models.QuerySet[LogEntry]

    id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        primary_key=True,
    )

    # Project relationship
    project = models.ForeignKey(
        "surveys.Project",
        related_name="rel_stations",
        on_delete=models.CASCADE,
        blank=False,
        null=False,
    )

    # Station identification
    name = models.CharField(
        max_length=100, help_text="Station identifier (e.g., 'A1', 'Station-001')"
    )

    description = models.TextField(
        blank=True, default="", help_text="Optional description of the station"
    )

    # Station coordinates
    latitude = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        help_text="Station latitude coordinate",
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
    )

    longitude = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        help_text="Station longitude coordinate",
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
    )

    # Metadata
    created_by = models.EmailField(
        null=False,
        blank=False,
        help_text="User who created or submitted the entry.",
    )

    creation_date = models.DateTimeField(auto_now_add=True)
    modified_date = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Station"
        verbose_name_plural = "Stations"
        unique_together = ("project", "name")
        ordering = ["project", "name"]

    def __str__(self) -> str:
        return f"{self.project.name} - Station {self.name}"

    @property
    def coordinates(self) -> tuple[float, float] | None:
        """Get current coordinates as (longitude, latitude) tuple."""
        if self.latitude is not None and self.longitude is not None:
            return (float(self.longitude), float(self.latitude))
        return None


class StationResourceType(models.TextChoices):
    PHOTO = "photo", "Photo"
    VIDEO = "video", "Video"
    SKETCH = "sketch", "Sketch"
    NOTE = "note", "Note"
    DOCUMENT = "document", "Document"

    @classmethod
    def from_str(cls, value: str) -> Self:
        return cls._member_map_[value.upper()]  # type: ignore[return-value]


def get_station_resource_path(instance: StationResource, filename: str) -> str:
    ext = Path(filename).suffix[1:]

    # Use Redis cache to share a short-lived random key between main file and miniature
    cache_key = f"station_resource:{instance.id}:upload_key"
    if not (filekey := cache.get(cache_key)):
        filekey = os.urandom(6).hex()
        # Short TTL; just long enough for both uploads in a single save cycle
        cache.set(cache_key, filekey, timeout=600)

    # Preserve '_thumb' suffix for miniature filenames
    thumb_suffix = "_thumb" if "_thumb" in filename else ""

    return (
        f"{instance.station.project.id}/"
        f"{instance.station.id}/"
        f"resources/{filekey}{thumb_suffix}.{ext}"
    )


class StationResource(models.Model):
    """
    Stores various types of resources (photos, videos, sketches, notes)
    associated with a survey station.
    """

    id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        primary_key=True,
    )

    # Station relationship
    station = models.ForeignKey(
        Station,
        related_name="resources",
        on_delete=models.CASCADE,
        blank=False,
        null=False,
    )

    # Resource details
    resource_type = models.CharField(
        max_length=20,
        choices=StationResourceType,
    )

    title = models.CharField(max_length=200, help_text="Title or name of the resource")

    description = models.TextField(
        blank=True, default="", help_text="Optional description of the resource"
    )

    # File storage (for photos, videos, documents)
    file = models.FileField(
        upload_to=get_station_resource_path,
        blank=True,
        null=True,
        max_length=255,
        storage=AttachmentStorage(),  # type: ignore[no-untyped-call]
        validators=[AttachmentValidator()],
    )

    # Miniature/thumbnail storage
    miniature = models.ImageField(
        upload_to=get_station_resource_path,
        blank=True,
        null=True,
        max_length=255,
        storage=AttachmentStorage(),  # type: ignore[no-untyped-call]
        help_text="Thumbnail/preview image for the resource",
    )

    # Text content (for notes, sketches)
    text_content = models.TextField(
        blank=True,
        default="",
        help_text="Text content for notes or sketch descriptions",
    )

    # Metadata
    created_by = models.EmailField(
        null=False,
        blank=False,
        help_text="User who created or submitted the entry.",
    )

    creation_date = models.DateTimeField(auto_now_add=True)
    modified_date = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Station Resource"
        verbose_name_plural = "Station Resources"
        ordering = ["station", "-modified_date"]

    def __str__(self) -> str:
        # https://docs.djangoproject.com/en/5.2/ref/models/instances/#django.db.models.Model.get_FOO_display
        return f"{self.station.name} - {self.get_resource_type_display()}: {self.title}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Override save to prevent resource_type from being changed and generate
        miniatures."""
        # If this is an update (has pk) and resource_type is being changed
        if self.pk:
            with contextlib.suppress(self.__class__.DoesNotExist):
                old_instance = self.__class__.objects.get(pk=self.pk)

                if old_instance.resource_type != self.resource_type:
                    raise ValueError(
                        "Cannot change resource type from "
                        f"'{old_instance.resource_type}' to '{self.resource_type}'. "
                        "Resource type is immutable after creation."
                    )

        # Clean the model
        self.full_clean()

        # Check if we need to generate miniature
        should_generate_miniature = False
        old_miniature = None

        if (
            self.resource_type
            in [
                StationResourceType.PHOTO,
                StationResourceType.VIDEO,
                StationResourceType.DOCUMENT,
            ]
            and self.file
        ):
            if self.pk:
                try:
                    old_instance = self.__class__.objects.get(pk=self.pk)
                    # Check if file changed
                    if old_instance.file != self.file:
                        should_generate_miniature = True
                        old_miniature = old_instance.miniature
                except self.__class__.DoesNotExist:
                    should_generate_miniature = True
            else:
                should_generate_miniature = True

        # Generate miniature after save
        if should_generate_miniature:
            try:
                # Delete old miniature if it exists
                if old_miniature:
                    old_miniature.delete(save=False)

                # Generate new miniature based on resource type
                if self.resource_type == StationResourceType.PHOTO:
                    self._generate_photo_miniature()
                elif self.resource_type == StationResourceType.VIDEO:
                    self._generate_video_miniature()
                elif self.resource_type == StationResourceType.DOCUMENT:
                    self._generate_document_miniature()

            except Exception as e:
                raise ValidationError(
                    "Error in the miniature generation process"
                ) from e

        super().save()
        # Clear the temporary upload key so future uploads get a fresh key
        with contextlib.suppress(Exception):
            cache.delete(f"station_resource:{self.id}:upload_key")

    if TYPE_CHECKING:
        # Type hints for Django's auto-generated methods
        # These are created by Django at runtime for fields with choices
        def get_resource_type_display(self) -> str:
            """Get the human-readable name for the resource type.

            This method is auto-generated by Django for fields with choices.
            This stub is here to satisfy type checkers.
            """
            ...

    def clean(self) -> None:
        """Validate resource consistency."""
        super().clean()

        # File-based resources require a file
        if self.resource_type in [
            StationResourceType.PHOTO,
            StationResourceType.VIDEO,
            StationResourceType.DOCUMENT,
        ]:
            if not self.file:
                raise ValidationError(
                    {
                        "file": (
                            f"Resource type '{self.get_resource_type_display()}' "
                            "requires a file."
                        )
                    }
                )

            # Validate file extension matches resource type
            if self.file:
                file_extension = Path(self.file.name).suffix.lower()

                # Define allowed extensions for each resource type
                allowed_extensions = {
                    StationResourceType.PHOTO: {
                        ".jpg",
                        ".jpeg",
                        ".png",
                        ".gif",
                        ".bmp",
                        ".webp",
                        ".heic",  # Allow HEIC for upload (will be converted)
                        ".heif",  # Allow HEIF for upload (will be converted)
                    },
                    StationResourceType.VIDEO: {
                        ".mp4",
                        ".avi",
                        ".mov",
                        ".wmv",
                        ".flv",
                        ".webm",
                    },
                    StationResourceType.DOCUMENT: {
                        ".pdf",
                        ".doc",
                        ".docx",
                        ".txt",
                        ".rtf",
                    },
                }

                if self.resource_type in allowed_extensions:
                    valid_extensions = sorted(allowed_extensions[self.resource_type])  # type: ignore[index]
                    if file_extension not in valid_extensions:
                        raise ValidationError(
                            {
                                "file": (
                                    "Invalid file type for "
                                    f"{self.get_resource_type_display()}. "
                                    f"Allowed types: {', '.join(valid_extensions)}"
                                ),
                            }
                        )
        else:
            # Text-based resources should not have a file or miniature
            if self.file:
                raise ValidationError(
                    {
                        "file": (
                            f"Resource type '{self.get_resource_type_display()}' "
                            "should not have a file."
                        )
                    }
                )
            if self.miniature:
                raise ValidationError(
                    {
                        "miniature": (
                            f"Resource type '{self.get_resource_type_display()}' "
                            "should not have a miniature."
                        )
                    }
                )

    def _generate_photo_miniature(self) -> None:
        """Generate miniature for photo resources."""
        if not self.file:
            return

        # Check if the uploaded file is HEIC/HEIF
        original_extension = Path(self.file.name).suffix.lower()
        is_heic = original_extension in {".heic", ".heif"}

        self.file.open("rb")

        # If it's HEIC, we need to convert the main file to JPEG too
        if is_heic:
            # Convert HEIC to JPEG for the main file
            img = ImageProcessor.process_image_for_web(self.file)

            # Save as JPEG
            main_buffer = BytesIO()
            img.save(main_buffer, format="JPEG", quality=90)
            main_buffer.seek(0)

            # Update the filename to .jpg
            original_name = Path(self.file.name).stem
            new_filename = f"{original_name}.jpg"

            # Replace the file with the converted version
            self.file.delete(save=False)
            self.file.save(new_filename, ContentFile(main_buffer.read()), save=False)

            # Re-open for miniature generation
            self.file.open("rb")

        # Generate miniature
        miniature_content = ImageProcessor.create_miniature(self.file)

        # Generate filename for miniature
        original_name = Path(self.file.name).stem
        miniature_name = f"{original_name}_thumb.jpg"

        # Save miniature
        self.miniature.save(miniature_name, miniature_content, save=False)
        logger.info(f"Generated photo miniature for resource {self.id}")

    def _generate_video_miniature(self) -> None:
        """Generate miniature for video resources."""
        if not self.file:
            return

        self.file.open("rb")
        # Extract thumbnail from video
        miniature_content = VideoProcessor.extract_thumbnail(self.file)

        # Generate filename for miniature
        original_name = Path(self.file.name).stem
        miniature_name = f"{original_name}_thumb.jpg"

        # Save miniature
        self.miniature.save(miniature_name, miniature_content, save=False)
        logger.info(f"Generated video miniature for resource {self.id}")

    def _generate_document_miniature(self) -> None:
        """Generate miniature for document resources."""
        if not self.file or Path(self.file.name).suffix.lower() != ".pdf":
            return

        self.file.open("rb")
        # Generate preview based on document type
        miniature_content = DocumentProcessor.generate_preview(
            self.file, filename=self.file.name
        )

        # Generate filename for miniature
        original_name = Path(self.file.name).stem
        miniature_name = f"{original_name}_thumb.jpg"

        # Save miniature
        self.miniature.save(miniature_name, miniature_content, save=False)
        logger.info(f"Generated document miniature for resource {self.id}")

    @property
    def is_file_based(self) -> bool:
        """Check if this resource type requires file storage."""
        return self.resource_type in [
            StationResourceType.PHOTO,
            StationResourceType.VIDEO,
            StationResourceType.DOCUMENT,
        ]

    @property
    def is_text_based(self) -> bool:
        """Check if this resource type uses text content."""
        return self.resource_type in [
            StationResourceType.NOTE,
            StationResourceType.SKETCH,
        ]
