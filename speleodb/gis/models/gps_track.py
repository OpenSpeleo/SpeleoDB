# -*- coding: utf-8 -*-

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.db import transaction
from django.utils import timezone

from speleodb.common.enums import ColorPalette
from speleodb.common.enums import PermissionLevel
from speleodb.users.models import User
from speleodb.utils.s3_storages import GPSTrackStorage
from speleodb.utils.validators import GeoJsonValidator

if TYPE_CHECKING:
    from django_stubs_ext import StrOrPromise


def get_gps_track_upload_path(instance: GPSTrack, filename: str) -> str:
    return f"{instance.id}.json"


class GPSTrack(models.Model):
    """
    Represents a GPS Track on the map.
    GPSTrack are GeoJSON files not linked to any project.
    """

    permissions: models.QuerySet[GPSTrackUserPermission]

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

    color = models.CharField(
        max_length=7,
        default=ColorPalette.random_color,
        validators=[
            RegexValidator(r"^#[0-9a-fA-F]{6}$", "Must be a #RRGGBB hex color")
        ],
        help_text="Hex color code for map rendering (e.g. #377eb8)",
    )

    created_by = models.EmailField(
        null=False,
        blank=False,
        help_text="User who created or submitted the entry.",
    )

    is_active = models.BooleanField(default=True)

    creation_date = models.DateTimeField(auto_now_add=True, editable=False)
    modified_date = models.DateTimeField(auto_now=True, editable=False)

    class Meta:
        verbose_name = "GPS Track"
        verbose_name_plural = "GPS Tracks"
        indexes = [
            models.Index(fields=["is_active"], name="gis_gpst_active_idx"),
        ]
        ordering = ["-creation_date"]

    def __str__(self) -> str:
        return f"[GPS Track] {self.created_by} @ {self.creation_date}"

    # Signed URL helper — delegates to django-storages which produces
    # CloudFront signed URLs in production or S3 presigned URLs in local dev.
    def get_signed_download_url(self, expires_in: int = 3600) -> str:
        if not self.file:
            raise ValidationError("No file to download.")
        return self.file.storage.url(self.file.name, expire=expires_in)  # type: ignore[call-arg]

    def deactivate(self, deactivated_by: User) -> None:
        """Soft-delete the track and its active permissions atomically."""
        timestamp = timezone.now()
        with transaction.atomic():
            self.permissions.filter(is_active=True).update(
                is_active=False,
                deactivated_by=deactivated_by,
                modified_date=timestamp,
            )
            self.is_active = False
            self.modified_date = timestamp
            super().save(update_fields=["is_active", "modified_date"])


class GPSTrackUserPermission(models.Model):
    """Durable direct-user permission row for one GPS Track."""

    user = models.ForeignKey(
        User,
        related_name="gps_track_permissions",
        on_delete=models.CASCADE,
        blank=False,
        null=False,
    )

    gps_track = models.ForeignKey(
        GPSTrack,
        related_name="permissions",
        on_delete=models.CASCADE,
        blank=False,
        null=False,
    )

    level = models.IntegerField(
        choices=PermissionLevel.choices_no_webviewer,
        default=PermissionLevel.READ_ONLY,
        null=False,
        blank=False,
    )

    is_active = models.BooleanField(default=True)

    creation_date = models.DateTimeField(auto_now_add=True, editable=False)
    modified_date = models.DateTimeField(auto_now=True, editable=False)

    deactivated_by = models.ForeignKey(
        User,
        on_delete=models.RESTRICT,
        blank=True,
        null=True,
        default=None,
    )

    class Meta:
        verbose_name = "GPS Track - User Permission"
        verbose_name_plural = "GPS Track - User Permissions"
        indexes = [
            models.Index(
                fields=["user", "is_active"],
                name="gis_gptup_user_active_idx",
            ),
            models.Index(
                fields=["gps_track", "is_active"],
                name="gis_gptup_track_active_idx",
            ),
            models.Index(
                fields=["user", "gps_track", "is_active"],
                name="gis_gptup_user_track_act_idx",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "gps_track"],
                name="gis_gptup_user_track_perm_uniq",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user} => {self.gps_track.name} [{self.level}]"

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {self}>"

    def deactivate(self, deactivated_by: User) -> None:
        self.is_active = False
        self.deactivated_by = deactivated_by
        self.save()

    def reactivate(self, level: PermissionLevel) -> None:
        self.is_active = True
        self.deactivated_by = None
        self.level = level
        self.save()

    @property
    def level_label(self) -> StrOrPromise:
        return PermissionLevel.from_value(self.level).label
