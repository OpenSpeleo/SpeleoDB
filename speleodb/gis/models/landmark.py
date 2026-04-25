# -*- coding: utf-8 -*-

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from django.core.validators import MaxValueValidator
from django.core.validators import MinValueValidator
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import UniqueConstraint

from speleodb.common.enums import ColorPalette
from speleodb.common.enums import PermissionLevel
from speleodb.gis.models.utils import generate_random_token
from speleodb.users.models import User

if TYPE_CHECKING:
    from django_stubs_ext import StrOrPromise


class LandmarkCollection(models.Model):
    """
    Shared, permissioned container for Landmark records.

    A LandmarkCollection exposes a public OGC token while using explicit user
    permissions for authenticated collaboration inside the application.
    """

    landmarks: models.QuerySet[Landmark]
    permissions: models.QuerySet[LandmarkCollectionUserPermission]

    class CollectionType(models.TextChoices):
        PERSONAL = "PERSONAL", "Personal"
        SHARED = "SHARED", "Shared"

    id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        primary_key=True,
    )

    name = models.CharField(
        max_length=100,
        help_text="Landmark collection name",
    )

    description = models.TextField(
        blank=True,
        default="",
        help_text="Optional description of the landmark collection",
    )

    color = models.CharField(
        max_length=7,
        default=ColorPalette.random_color,
        validators=[
            RegexValidator(
                r"^#[0-9a-fA-F]{6}$",
                "Must be a #RRGGBB hex color",
            )
        ],
        help_text="Hex color code for map rendering (e.g. #377eb8)",
    )

    is_active = models.BooleanField(default=True)

    collection_type = models.CharField(
        max_length=16,
        choices=CollectionType.choices,
        default=CollectionType.SHARED,
    )

    personal_owner = models.ForeignKey(
        User,
        related_name="personal_landmark_collections",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        default=None,
    )

    gis_token = models.CharField(
        "GIS Token",
        max_length=40,
        unique=True,
        blank=False,
        null=False,
        default=generate_random_token,
    )

    created_by = models.EmailField(
        null=False,
        blank=False,
        help_text="User who created the landmark collection.",
    )

    creation_date = models.DateTimeField(auto_now_add=True)
    modified_date = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Landmark Collection"
        verbose_name_plural = "Landmark Collections"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["is_active"], name="gis_lc_active_idx"),
            models.Index(fields=["created_by"], name="gis_lc_created_by_idx"),
            models.Index(
                fields=["collection_type", "is_active"],
                name="gis_lc_type_active_idx",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["personal_owner"],
                condition=models.Q(collection_type="PERSONAL"),
                name="gis_lc_one_personal_per_user",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        collection_type="PERSONAL",
                        personal_owner__isnull=False,
                    )
                    | models.Q(
                        collection_type="SHARED",
                        personal_owner__isnull=True,
                    )
                ),
                name="gis_lc_owner_matches_type",
            ),
        ]

    def __str__(self) -> str:
        return f"Landmark Collection: {self.name}"

    @property
    def is_personal(self) -> bool:
        return self.collection_type == self.CollectionType.PERSONAL

    def refresh_gis_token(self) -> None:
        self.gis_token = generate_random_token()
        self.save(update_fields=["gis_token", "modified_date"])


class LandmarkCollectionUserPermission(models.Model):
    user = models.ForeignKey(
        User,
        related_name="landmark_collection_permissions",
        on_delete=models.CASCADE,
        blank=False,
        null=False,
    )

    collection = models.ForeignKey(
        LandmarkCollection,
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
        verbose_name = "Landmark Collection - User Permission"
        verbose_name_plural = "Landmark Collection - User Permissions"
        indexes = [
            models.Index(fields=["user", "is_active"], name="gis_lcup_user_active_idx"),
            models.Index(
                fields=["collection", "is_active"],
                name="gis_lcup_coll_active_idx",
            ),
            models.Index(
                fields=["user", "collection", "is_active"],
                name="gis_lcup_user_coll_act_idx",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "collection"],
                name="gis_lcup_user_collection_perm_unique",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user} => {self.collection.name} [{self.level}]"

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


class Landmark(models.Model):
    """
    Represents a Landmark on the map.
    Landmarks are standalone markers not linked to any project.
    """

    id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        primary_key=True,
    )

    # Landmark identification
    name = models.CharField(
        max_length=100,
        help_text="Landmark name",
    )

    description = models.TextField(
        blank=True,
        default="",
        help_text="Optional description of the landmark",
    )

    # Landmark coordinates
    latitude = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        null=False,
        blank=False,
        help_text="Landmark latitude coordinate",
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
    )

    longitude = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        null=False,
        blank=False,
        help_text="Landmark longitude coordinate",
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
    )

    created_by = models.EmailField(
        null=False,
        blank=False,
        help_text="User who created the landmark.",
    )

    collection = models.ForeignKey(
        LandmarkCollection,
        related_name="landmarks",
        on_delete=models.CASCADE,
        blank=False,
        null=False,
    )

    creation_date = models.DateTimeField(auto_now_add=True)
    modified_date = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Landmark"
        verbose_name_plural = "Landmarks"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["latitude", "longitude"]),  # For spatial queries
            models.Index(fields=["name"]),  # For name lookups
            models.Index(fields=["creation_date"]),  # For recent Landmarks
            models.Index(fields=["collection"], name="gis_landmark_collection_idx"),
        ]
        constraints = [
            UniqueConstraint(
                fields=["collection", "latitude", "longitude"],
                name="gis_landmark_collection_coordinate_unique",
            )
        ]

    def __str__(self) -> str:
        return f"Landmark: {self.name}"

    @property
    def coordinates(self) -> tuple[float, float] | None:
        """Get current coordinates as (longitude, latitude) tuple."""
        if self.latitude is not None and self.longitude is not None:
            return (float(self.longitude), float(self.latitude))
        return None
