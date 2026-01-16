# -*- coding: utf-8 -*-

from __future__ import annotations

import hashlib
import uuid
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError
from botocore.exceptions import NoCredentialsError
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import UniqueConstraint

from speleodb.surveys.fields import Sha256Field
from speleodb.users.models import User
from speleodb.utils.storages import GPSTrackStorage
from speleodb.utils.validators import GeoJsonValidator


def get_geojson_upload_path(instance: GPSTrack, filename: str) -> str:
    return f"gps_tracks/{instance.id}.json"


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
        upload_to=get_geojson_upload_path,
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

    # S3 signed URL helper
    def get_signed_download_url(self, expires_in: int = 3600) -> str:
        if not self.file:
            raise ValidationError("No file to download.")

        s3_client = boto3.client(  # type: ignore[no-untyped-call]
            "s3",
            endpoint_url=getattr(settings, "AWS_S3_ENDPOINT_URL", None),
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_S3_REGION_NAME,
            use_ssl=getattr(settings, "AWS_S3_USE_SSL", True),
            verify=getattr(settings, "AWS_S3_VERIFY", True),
        )

        try:
            return s3_client.generate_presigned_url(  # type: ignore[no-any-return]
                ClientMethod="get_object",
                Params={
                    "Bucket": settings.AWS_STORAGE_BUCKET_NAME,
                    "Key": f"{self.file.storage.location}/{self.file.name}",
                },
                ExpiresIn=expires_in,
            )
        except (NoCredentialsError, BotoCoreError) as exc:  # pragma: no cover - env
            raise ValidationError("AWS credentials error when signing URL.") from exc
