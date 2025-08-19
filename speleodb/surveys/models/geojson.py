# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import Any

import boto3
from botocore.exceptions import BotoCoreError
from botocore.exceptions import NoCredentialsError
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models

from speleodb.surveys.models import Project
from speleodb.utils.storages import GeoJSONStorage
from speleodb.utils.validators import GeoJsonValidator


def get_geojson_upload_path(instance: GeoJSON, filename: str) -> str:
    return f"{instance.project.id}/{instance.commit_sha}.json"


class GeoJSON(models.Model):
    id: int

    project = models.ForeignKey(
        Project,
        related_name="rel_geojsons",
        on_delete=models.CASCADE,
        blank=False,
        null=False,
        editable=True,
    )

    # GeoJSON file
    file = models.FileField(
        upload_to=get_geojson_upload_path,
        blank=False,
        null=False,
        editable=True,
        storage=GeoJSONStorage(),  # type: ignore[no-untyped-call]
        validators=[GeoJsonValidator()],
    )

    commit_sha = models.CharField(
        max_length=40,
        unique=True,
        editable=True,
        validators=[
            RegexValidator(regex=r"^[0-9a-f]{40}$", message="Enter a valid sha1 value")
        ],
    )

    commit_date = models.DateTimeField(null=False, blank=False)

    creation_date = models.DateTimeField(auto_now_add=True, editable=False)
    modified_date = models.DateTimeField(auto_now=True, editable=False)

    class Meta:
        verbose_name = "GeoJSON"
        verbose_name_plural = "GeoJSONs"

    def __str__(self) -> str:
        return f"[GeoJSON] {self.project.name} @ {self.commit_sha[:8]}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Enforce immutability: once created, cannot be updated."""
        self.full_clean()
        if self.pk:
            raise ValidationError("GeoJSON objects are immutable once created.")
        return super().save(*args, **kwargs)

    # S3 signed URL helper
    def get_signed_download_url(self, expires_in: int = 3600) -> str:
        if not self.file:
            raise ValidationError("No file to download.")

        s3_client = boto3.client(  # type: ignore[no-untyped-call]
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_S3_REGION_NAME,
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
