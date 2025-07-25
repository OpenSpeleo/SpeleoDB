# -*- coding: utf-8 -*-

from __future__ import annotations

import uuid
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING

from django.core.files.base import ContentFile
from django.db import models
from django.db.models import F
from PIL import Image

from speleodb.utils.image_processing import ImageProcessor  # Import ImageProcessor
from speleodb.utils.storages import PersonPhotoStorage
from speleodb.utils.validators import ImageWithHeicSupportValidator

if TYPE_CHECKING:
    from collections.abc import Iterable


class PersonBase(models.Model):
    """Abstract base model for all person types."""

    id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        primary_key=True,
    )

    # Required fields
    full_name = models.CharField(
        max_length=200,
        help_text="Full name of the person",
    )

    title = models.CharField(
        max_length=200,
        help_text="Professional title or role",
    )

    description = models.TextField(
        help_text="Biography or description of the person's involvement",
    )

    # Optional link fields
    link_name = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="Display text for the link (e.g., 'LinkedIn', 'Personal Website')",
    )

    link_target = models.URLField(
        blank=True,
        default="",
        help_text="URL for the person's profile or website",
    )

    # Photo field with S3 storage
    photo = models.ImageField(
        upload_to="people/photos/",
        storage=PersonPhotoStorage(),  # type: ignore[no-untyped-call]
        validators=[
            ImageWithHeicSupportValidator(
                allowed_extensions=["jpg", "jpeg", "png", "webp"]
            )
        ],
        help_text="Photo of the person (JPEG, PNG, or WebP format)",
    )

    # Custom ordering
    order = models.IntegerField(
        null=True,
        blank=True,
        help_text="Custom order for display (lower numbers appear first)",
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = [F("order").asc(nulls_last=True), "full_name"]

    def __str__(self) -> str:
        return self.full_name

    def save(
        self,
        force_insert: bool | tuple[models.base.ModelBase, ...] = False,
        force_update: bool = False,
        using: str | None = None,
        update_fields: Iterable[str] | None = None,
    ) -> None:
        """Override save to process photo before saving."""
        # Check if photo is being added or changed
        if self.pk:
            try:
                old_instance = self.__class__.objects.get(pk=self.pk)  # type: ignore[attr-defined]
                photo_changed = old_instance.photo != self.photo
            except self.__class__.DoesNotExist:
                photo_changed = True
        else:
            photo_changed = bool(self.photo)

        # Process photo if it's new or changed
        if photo_changed and self.photo:
            self._process_photo()

        super().save(
            force_insert=force_insert,
            force_update=force_update,
            using=using,
            update_fields=update_fields,
        )

    @property
    def has_link(self) -> bool:
        """Check if this person has a link configured."""
        return bool(self.link_target)

    def get_photo_url(self) -> str | None:
        """Get the photo URL (public URL for S3, regular URL for local)."""
        if not self.photo:
            return None

        try:
            return self.photo.url  # type: ignore[no-any-return]
        except AttributeError:
            return None

    def _process_photo(self) -> None:
        """Process the uploaded photo to create a square 200x200 thumbnail."""
        # Check if the uploaded file is HEIC/HEIF
        original_extension = Path(
            self.photo.name or self.photo.file.name
        ).suffix.lower()
        is_heic = original_extension in {".heic", ".heif"}

        # Open the image and process it for web (handles EXIF orientation)
        img = ImageProcessor.process_image_for_web(self.photo.file)

        # Get the original filename
        original_filename = Path(self.photo.name or self.photo.file.name).name

        # If it's HEIC, change the extension to .jpg
        if is_heic:
            original_filename = Path(original_filename).stem + ".jpg"

        # Create thumbnail (200x200)
        # Calculate dimensions for center crop
        width, height = img.size
        min_dimension = min(width, height)

        # Calculate crop box for center square
        left = (width - min_dimension) // 2
        top = (height - min_dimension) // 2
        right = left + min_dimension
        bottom = top + min_dimension

        # Crop to square and resize
        img_cropped = img.crop((left, top, right, bottom))
        img_thumbnail = img_cropped.resize((200, 200), Image.Resampling.LANCZOS)

        # Save thumbnail to buffer
        thumb_buffer = BytesIO()
        img_thumbnail.save(thumb_buffer, format="JPEG", quality=85)
        thumb_buffer.seek(0)

        # Save the thumbnail through Django's file field
        self.photo.save(
            original_filename,
            ContentFile(thumb_buffer.read()),
            save=False,  # Don't save the model yet
        )


class BoardMember(PersonBase):
    """Board of Directors members."""

    class Meta:
        verbose_name = "Board Member"
        verbose_name_plural = "Board of Directors"
        ordering = [F("order").asc(nulls_last=True), "full_name"]


class TechnicalMember(PersonBase):
    """Technical Steering Committee members."""

    class Meta:
        verbose_name = "Technical Committee Member"
        verbose_name_plural = "Technical Steering Committee"
        ordering = [F("order").asc(nulls_last=True), "full_name"]


class ExplorerMember(PersonBase):
    """Explorer Advisory Board members."""

    class Meta:
        verbose_name = "Explorer Board Member"
        verbose_name_plural = "Explorer Advisory Board"
        ordering = [F("order").asc(nulls_last=True), "full_name"]
