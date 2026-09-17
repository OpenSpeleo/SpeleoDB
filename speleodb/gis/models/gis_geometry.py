"""A small, editable private GIS shape and its direct-user access."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from django.core.validators import RegexValidator
from django.db import models
from django.db import transaction
from django.utils import timezone

from speleodb.common.enums import ColorPalette
from speleodb.common.enums import PermissionLevel
from speleodb.gis.geometry_validation import GIS_GEOMETRY_LIMIT_HELP
from speleodb.gis.geometry_validation import GIS_GEOMETRY_NAME_MAX_LENGTH
from speleodb.gis.geometry_validation import inspect_gis_geometry
from speleodb.gis.geometry_validation import validate_gis_geometry
from speleodb.users.models import User

if TYPE_CHECKING:
    from django_stubs_ext import StrOrPromise


class GISGeometry(models.Model):
    permissions: models.QuerySet[GISGeometryUserPermission]

    id = models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)
    name = models.CharField(
        max_length=GIS_GEOMETRY_NAME_MAX_LENGTH, help_text="GIS Geometry name"
    )
    color = models.CharField(
        max_length=7,
        default=ColorPalette.random_color,
        validators=[
            RegexValidator(r"^#[0-9a-fA-F]{6}$", "Must be a #RRGGBB hex color")
        ],
    )
    created_by = models.EmailField(help_text="Email of the creator; provenance only.")
    geojson = models.JSONField(
        validators=[validate_gis_geometry],
        help_text=(
            "A bare LineString or Polygon GeoJSON object using 2D "
            f"longitude/latitude coordinates. {GIS_GEOMETRY_LIMIT_HELP}"
        ),
    )
    revision = models.PositiveBigIntegerField(default=1, editable=False)
    is_active = models.BooleanField(default=True)
    creation_date = models.DateTimeField(auto_now_add=True, editable=False)
    modified_date = models.DateTimeField(auto_now=True, editable=False)

    class Meta:
        verbose_name = "GIS Geometry"
        verbose_name_plural = "GIS Geometries"
        ordering = ["-modified_date"]
        indexes = [models.Index(fields=["is_active"], name="gis_gisg_active_idx")]

    def __str__(self) -> str:
        return self.name

    @property
    def geometry_type(self) -> str:
        return str(self.geojson["type"])

    @property
    def bbox_area_m2(self) -> float:
        return inspect_gis_geometry(self.geojson).bbox_area_m2

    @property
    def vertex_count(self) -> int:
        return inspect_gis_geometry(self.geojson).vertex_count

    def deactivate(self, deactivated_by: User) -> None:
        """Retain the shape and access history while serializing with edits."""
        with transaction.atomic():
            type(self).objects.select_for_update().get(pk=self.pk)
            timestamp = timezone.now()
            self.permissions.filter(is_active=True).update(
                is_active=False,
                deactivated_by=deactivated_by,
                modified_date=timestamp,
            )
            self.is_active = False
            self.modified_date = timestamp
            type(self).objects.filter(pk=self.pk).update(
                is_active=False, modified_date=timestamp
            )


class GISGeometryUserPermission(models.Model):
    user = models.ForeignKey(
        User, related_name="gis_geometry_permissions", on_delete=models.CASCADE
    )
    gis_geometry = models.ForeignKey(
        GISGeometry, related_name="permissions", on_delete=models.CASCADE
    )
    level = models.IntegerField(
        choices=PermissionLevel.choices_no_webviewer,
        default=PermissionLevel.READ_ONLY,
    )
    is_active = models.BooleanField(default=True)
    creation_date = models.DateTimeField(auto_now_add=True, editable=False)
    modified_date = models.DateTimeField(auto_now=True, editable=False)
    deactivated_by = models.ForeignKey(
        User, on_delete=models.RESTRICT, blank=True, null=True, default=None
    )

    class Meta:
        verbose_name = "GIS Geometry - User Permission"
        verbose_name_plural = "GIS Geometry - User Permissions"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "gis_geometry"], name="gis_gisgup_user_geom_uniq"
            )
        ]
        indexes = [
            models.Index(
                fields=["user", "is_active"], name="gis_gisgup_user_active_idx"
            ),
            models.Index(
                fields=["gis_geometry", "is_active"], name="gis_gisgup_geom_active_idx"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user} => {self.gis_geometry.name} [{self.level}]"

    def deactivate(self, deactivated_by: User) -> None:
        self.is_active = False
        self.deactivated_by = deactivated_by
        self.save(update_fields=["is_active", "deactivated_by", "modified_date"])

    def reactivate(self, level: PermissionLevel) -> None:
        self.is_active = True
        self.deactivated_by = None
        self.level = level
        self.save(
            update_fields=["is_active", "deactivated_by", "level", "modified_date"]
        )

    @property
    def level_label(self) -> StrOrPromise:
        return PermissionLevel.from_value(self.level).label
