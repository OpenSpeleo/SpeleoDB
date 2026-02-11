# -*- coding: utf-8 -*-

from __future__ import annotations

import hashlib
import uuid
from typing import Any

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import UniqueConstraint

from speleodb.surveys.fields import Sha256Field
from speleodb.users.models import User
from speleodb.utils.storages import GPSTrackStorage
from speleodb.utils.validators import GeoJsonValidator


def get_gps_track_upload_path(instance: GPSTrack, filename: str) -> str:
    return f"{instance.id}.json"


class GPSTrack(models.Model):
    """
    Represents a GPS Track on the map.
    GPSTrack are GeoJSON files not linked to any project.
    """

    id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        primary_key=True,
    )

    # Track name identification
    name = models.CharField(
        max_length=255,
        help_text="Track name",
    )

    # GeoJSON file
    file = models.FileField(
        upload_to=get_gps_track_upload_path,
        blank=False,
        null=False,
        editable=True,
        storage=GPSTrackStorage(),  # type: ignore[no-untyped-call]
        validators=[GeoJsonValidator()],
    )

    sha256_hash = Sha256Field(
        blank=False,
        null=False,
        verbose_name="SHA256 hash of the `geojson file`",
    )

    user = models.ForeignKey(
        User,
        related_name="gps_tracks",
        on_delete=models.CASCADE,
        blank=False,
        null=False,
    )

    creation_date = models.DateTimeField(auto_now_add=True, editable=False)
    modified_date = models.DateTimeField(auto_now=True, editable=False)

    class Meta:
        verbose_name = "GPS Track"
        verbose_name_plural = "GPS Tracks"
        indexes = [
            models.Index(fields=["user"]),
            models.Index(fields=["sha256_hash"]),
        ]
        ordering = ["-creation_date"]
        constraints = [
            UniqueConstraint(
                fields=["sha256_hash", "user"],
                name="%(app_label)s_%(class)s_gps_track_per_user_unique",
            )
        ]

    def __str__(self) -> str:
        return f"[GPS Track] {self.user.name} @ {self.creation_date}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        # Ensure the `hash` is properly set.
        self._set_file_hash()

        # Finish by cleaning after the hash is set
        self.full_clean()

        return super().save(*args, **kwargs)

    def _set_file_hash(self) -> None:
        if self.file is None:
            raise ValueError("File is `None`")

        sha256 = hashlib.sha256()

        # no need to open the file
        for chunk in self.file.chunks():
            sha256.update(chunk)

        # reset the pointer to beginning
        self.file.seek(0)

        self.sha256_hash = sha256.hexdigest()

    # Signed URL helper — delegates to django-storages which produces
    # CloudFront signed URLs in production or S3 presigned URLs in local dev.
    def get_signed_download_url(self, expires_in: int = 3600) -> str:
        if not self.file:
            raise ValidationError("No file to download.")
        return self.file.storage.url(self.file.name, expire=expires_in)  # type: ignore[no-any-return]
