# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

from django.core.exceptions import ValidationError
from django.db import models

from speleodb.surveys.models import Project
from speleodb.surveys.models import ProjectCommit
from speleodb.utils.storages import GeoJSONStorage
from speleodb.utils.validators import GeoJsonValidator

if TYPE_CHECKING:
    from datetime import datetime


def get_geojson_upload_path(instance: ProjectGeoJSON, filename: str) -> str:
    return f"{instance.project.id}/{instance.commit.id}.json"


class ProjectGeoJSON(models.Model):
    commit = models.OneToOneField(
        ProjectCommit,
        related_name="geojson",
        on_delete=models.CASCADE,
        blank=False,
        null=False,
        editable=False,
        primary_key=True,
    )

    project = models.ForeignKey(
        Project,
        related_name="geojsons",
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

    creation_date = models.DateTimeField(auto_now_add=True, editable=False)
    modified_date = models.DateTimeField(auto_now=True, editable=False)

    class Meta:
        verbose_name = "Project GeoJSON"
        verbose_name_plural = "Project GeoJSONs"
        indexes = [
            models.Index(fields=["project"]),
            models.Index(fields=["commit"]),
        ]
        ordering = ["-commit__authored_date"]

    def __str__(self) -> str:
        return f"[ProjectGeoJSON] {self.project.name} @ {self.commit.id[:8]}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Enforce immutability: once created, cannot be updated."""
        self.full_clean()
        # Use _state.adding to check if this is a new object
        # (pk is always set due to OneToOneField)
        if not self._state.adding:
            raise ValidationError("ProjectGeoJSON objects are immutable once created.")
        return super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        self.file.delete(save=False)
        return super().delete(*args, **kwargs)

    # Backward-compatible properties for legacy code
    @property
    def commit_sha(self) -> str:
        """Return the commit SHA (backward compatibility)."""
        return self.commit.id

    @property
    def commit_date(self) -> datetime:
        """Return the commit authored date (backward compatibility)."""
        return self.commit.authored_date

    @property
    def commit_author_name(self) -> str:
        """Return the commit author name (backward compatibility)."""
        return self.commit.author_name

    @property
    def commit_author_email(self) -> str:
        """Return the commit author email (backward compatibility)."""
        return self.commit.author_email

    @property
    def commit_message(self) -> str:
        """Return the commit message (backward compatibility)."""
        return self.commit.message

    # Signed URL helper — delegates to django-storages which produces
    # CloudFront signed URLs in production or S3 presigned URLs in local dev.
    def get_signed_download_url(self, expires_in: int = 3600) -> str:
        if not self.file:
            raise ValidationError("No file to download.")
        return self.file.storage.url(self.file.name, expire=expires_in)  # type: ignore[no-any-return]
