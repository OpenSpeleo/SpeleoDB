# -*- coding: utf-8 -*-

from __future__ import annotations

import decimal
import uuid
from typing import TYPE_CHECKING
from typing import Any
from typing import Self

from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.core.validators import MaxValueValidator
from django.core.validators import MinValueValidator
from django.db import models

if TYPE_CHECKING:
    from django.core.files.storage import Storage


def get_station_resource_storage() -> Storage:
    """Get the appropriate storage backend for station resources."""
    if getattr(settings, "USE_S3", False):
        from speleodb.utils.storages import StationResourceStorage  # noqa: PLC0415

        return StationResourceStorage()  # type: ignore[no-untyped-call]

    from speleodb.utils.storages import LocalStationResourceStorage  # noqa: PLC0415

    return LocalStationResourceStorage()  # type: ignore[no-untyped-call]


class Station(models.Model):
    """
    Represents a survey station where field data collection occurs.
    Stations are positioned using latitude/longitude coordinates.
    """

    id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        primary_key=True,
        unique=True,
    )

    # Project relationship
    project = models.ForeignKey(
        "surveys.Project",
        related_name="stations",
        on_delete=models.CASCADE,
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
        validators=[
            MinValueValidator(decimal.Decimal("-90.0")),
            MaxValueValidator(decimal.Decimal("90.0")),
        ],
    )

    longitude = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        help_text="Station longitude coordinate",
        validators=[
            MinValueValidator(decimal.Decimal("-180.0")),
            MaxValueValidator(decimal.Decimal("180.0")),
        ],
    )

    # Metadata
    created_by = models.ForeignKey(
        "users.User",
        related_name="stations_created",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
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


class StationResource(models.Model):
    """
    Stores various types of resources (photos, videos, sketches, notes)
    associated with a survey station.
    """

    class ResourceType(models.TextChoices):
        PHOTO = "photo", "Photo"
        VIDEO = "video", "Video"
        SKETCH = "sketch", "Sketch"
        NOTE = "note", "Note"
        DOCUMENT = "document", "Document"

    id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        primary_key=True,
        unique=True,
    )

    # Station relationship
    station = models.ForeignKey(
        Station,
        related_name="resources",
        on_delete=models.CASCADE,
    )

    # Resource details
    resource_type = models.CharField(
        max_length=20,
        choices=ResourceType.choices,
    )

    title = models.CharField(max_length=200, help_text="Title or name of the resource")

    description = models.TextField(
        blank=True, default="", help_text="Optional description of the resource"
    )

    # File storage (for photos, videos, documents)
    file = models.FileField(
        upload_to="stations/resources/%Y/%m/%d/",
        blank=True,
        null=True,
        storage=get_station_resource_storage(),
        validators=[
            FileExtensionValidator(
                allowed_extensions=[
                    "jpg",
                    "jpeg",
                    "png",
                    "gif",
                    "bmp",
                    "webp",  # Images
                    "mp4",
                    "avi",
                    "mov",
                    "wmv",
                    "flv",
                    "webm",  # Videos
                    "pdf",
                    "doc",
                    "docx",
                    "txt",
                    "rtf",  # Documents
                    "svg",  # Sketches
                ]
            )
        ],
    )

    # Text content (for notes, or sketch data)
    text_content = models.TextField(
        blank=True, default="", help_text="Text content for notes or sketch SVG data"
    )

    # Metadata
    created_by = models.ForeignKey(
        "users.User",
        related_name="station_resources_created",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    creation_date = models.DateTimeField(auto_now_add=True)
    modified_date = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Station Resource"
        verbose_name_plural = "Station Resources"
        ordering = ["station", "-modified_date"]

    def __str__(self) -> str:
        # https://docs.djangoproject.com/en/5.2/ref/models/instances/#django.db.models.Model.get_FOO_display
        return f"{self.station.name} - {self.get_resource_type_display()}: {self.title}"  # pyright: ignore[reportAttributeAccessIssue]

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Override save to prevent resource_type from being changed."""
        # If this is an update (has pk) and resource_type is being changed
        if self.pk and hasattr(self, "_loaded_resource_type"):
            if self._loaded_resource_type != self.resource_type:  # type: ignore[has-type]
                raise ValueError(
                    f"Cannot change resource type from '{self._loaded_resource_type}' "  # type: ignore[has-type]
                    f"to '{self.resource_type}'. Resource type is immutable after "
                    "creation."
                )

        super().save(*args, **kwargs)

        # Store the current resource_type for future checks
        self._loaded_resource_type = self.resource_type

    @classmethod
    def from_db(cls, db: Any, field_names: Any, values: Any) -> Self:
        """Store the original resource_type when loading from database."""
        instance = super().from_db(db, field_names, values)
        # Store the loaded resource_type to check against later
        instance._loaded_resource_type = instance.resource_type  # noqa: SLF001
        return instance

    @property
    def is_file_based(self) -> bool:
        """Check if this resource type requires file storage."""
        return self.resource_type in [
            self.ResourceType.PHOTO,
            self.ResourceType.VIDEO,
            self.ResourceType.DOCUMENT,
        ]

    @property
    def is_text_based(self) -> bool:
        """Check if this resource type uses text content."""
        return self.resource_type in [
            self.ResourceType.NOTE,
            self.ResourceType.SKETCH,
        ]

    def get_file_url(self) -> str | None:
        """Get the file URL (public URL for S3, regular URL for local)."""
        if not self.file:
            return None

        if getattr(settings, "USE_S3", False):
            # Return public URL for S3 (no signing needed)
            try:
                # Use the storage's URL method which will return public URL
                return self.file.url  # type: ignore[no-any-return]
            except AttributeError:
                return None

        else:
            # Regular file URL for local storage
            return self.file.url if self.file else None
