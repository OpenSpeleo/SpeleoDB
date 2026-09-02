# -*- coding: utf-8 -*-

from __future__ import annotations

import uuid
from functools import partial
from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.core.validators import MaxLengthValidator
from django.core.validators import RegexValidator
from django.db import models
from django.db import transaction
from django.utils import timezone

from speleodb.common.enums import ColorPalette
from speleodb.common.enums import PermissionLevel
from speleodb.users.models import User
from speleodb.utils.s3_storages import GISLayerStorage

if TYPE_CHECKING:
    from django_stubs_ext import StrOrPromise

GIS_LAYER_SIGNED_URL_TTL_SECONDS = 600
GIS_LAYER_DESCRIPTION_MAX_LENGTH = 2_000
GIS_LAYER_SOURCE_EXTENSIONS = (
    "kml",
    "kmz",
    "json",
    "geojson",
    "topojson",
    "zip",
)
GIS_LAYER_DATA_EXTENSIONS = ("json", "geojson")


class GISLayerSourceFormat(models.TextChoices):
    KML = "KML", "KML"
    KMZ = "KMZ", "KMZ"
    GEOJSON = "GEOJSON", "GeoJSON"
    TOPOJSON = "TOPOJSON", "TopoJSON"
    SHAPEFILE = "SHAPEFILE", "Shapefile"


def get_gis_layer_upload_path(
    instance: GISLayer,
    filename: str,
    is_source: bool,
) -> str:
    return f"{instance.id}/{'source_' if is_source else ''}{filename}"


class GISLayer(models.Model):
    """A private GIS source and its directly renderable GeoJSON data."""

    permissions: models.QuerySet[GISLayerUserPermission]

    id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        primary_key=True,
    )

    name = models.CharField(
        max_length=255,
        help_text="GIS Layer name",
    )

    description = models.TextField(
        blank=True,
        default="",
        max_length=GIS_LAYER_DESCRIPTION_MAX_LENGTH,
        validators=[MaxLengthValidator(GIS_LAYER_DESCRIPTION_MAX_LENGTH)],
    )

    # Source file
    source_f = models.FileField(
        upload_to=partial(get_gis_layer_upload_path, is_source=True),
        blank=False,
        null=False,
        editable=False,
        storage=GISLayerStorage(),  # type: ignore[no-untyped-call]
        validators=[FileExtensionValidator(GIS_LAYER_SOURCE_EXTENSIONS)],
    )

    # Processed file
    data_f = models.FileField(
        upload_to=partial(get_gis_layer_upload_path, is_source=False),
        blank=False,
        null=False,
        editable=False,
        storage=GISLayerStorage(),  # type: ignore[no-untyped-call]
        validators=[FileExtensionValidator(GIS_LAYER_DATA_EXTENSIONS)],
    )

    color = models.CharField(
        max_length=7,
        default=ColorPalette.random_color,
        validators=[
            RegexValidator(r"^#[0-9a-fA-F]{6}$", "Must be a #RRGGBB hex color")
        ],
        help_text="Panel identity and fallback render color",
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
        verbose_name = "GIS Layer"
        verbose_name_plural = "GIS Layers"
        ordering = ["-modified_date"]
        indexes = [
            models.Index(fields=["is_active"], name="gis_gisl_active_idx"),
        ]

    def __str__(self) -> str:
        return self.name

    @property
    def source_format(self) -> GISLayerSourceFormat:
        source_name = self.source_f.name
        if source_name is None:
            raise ValidationError("GIS Layer source file is missing.")
        suffix = PurePosixPath(source_name).suffix.lower()
        match suffix:
            case ".kml":
                return GISLayerSourceFormat.KML
            case ".kmz":
                return GISLayerSourceFormat.KMZ
            case ".json" | ".geojson":
                return GISLayerSourceFormat.GEOJSON
            case ".topojson":
                return GISLayerSourceFormat.TOPOJSON
            case ".zip":
                return GISLayerSourceFormat.SHAPEFILE
            case _:
                raise ValidationError("Unsupported GIS Layer source format.")

    def get_signed_download_url(
        self,
        expires_in: int = GIS_LAYER_SIGNED_URL_TTL_SECONDS,
    ) -> str:
        if not self.data_f:
            raise ValidationError("No GIS Layer data file is available.")
        return self.data_f.storage.url(self.data_f.name, expire=expires_in)  # type: ignore[call-arg]

    def get_signed_source_url(
        self,
        expires_in: int = GIS_LAYER_SIGNED_URL_TTL_SECONDS,
    ) -> str:
        if not self.source_f:
            raise ValidationError("No GIS Layer source file is available.")
        return self.source_f.storage.url(self.source_f.name, expire=expires_in)  # type: ignore[call-arg]

    def deactivate(self, deactivated_by: User) -> None:
        """Soft-delete the layer and its active permissions atomically."""
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


class GISLayerUserPermission(models.Model):
    """Durable direct-user permission row for one GIS Layer."""

    user = models.ForeignKey(
        User,
        related_name="gis_layer_permissions",
        on_delete=models.CASCADE,
        blank=False,
        null=False,
    )

    gis_layer = models.ForeignKey(
        GISLayer,
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
        verbose_name = "GIS Layer - User Permission"
        verbose_name_plural = "GIS Layer - User Permissions"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "gis_layer"],
                name="gis_gislup_user_layer_uniq",
            )
        ]
        indexes = [
            models.Index(
                fields=["user", "is_active"],
                name="gis_gislup_user_active_idx",
            ),
            models.Index(
                fields=["gis_layer", "is_active"],
                name="gis_gislup_layer_active_idx",
            ),
            models.Index(
                fields=["user", "gis_layer", "is_active"],
                name="gis_gislup_user_layer_act_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user} => {self.gis_layer.name} [{self.level}]"

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
