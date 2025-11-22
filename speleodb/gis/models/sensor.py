# -*- coding: utf-8 -*-

from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING

from django.db import models

from speleodb.common.enums import PermissionLevel
from speleodb.users.models import User

if TYPE_CHECKING:
    from django_stubs_ext import StrOrPromise


logger = logging.getLogger(__name__)


class SensorFleet(models.Model):
    sensors: models.QuerySet[Sensor]
    rel_user_permissions: models.QuerySet[SensorFleetUserPermission]

    id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        primary_key=True,
    )

    name = models.CharField(
        max_length=50,
        help_text="Sensor Fleet name (e.g., 'Flow Meters - Yucatan Peninsula')",
    )

    description = models.TextField(
        blank=True, default="", help_text="Optional description of the station"
    )

    is_active = models.BooleanField(default=True)

    # Metadata
    created_by = models.EmailField(
        null=False,
        blank=False,
        help_text="User who created the sensor fleet.",
    )

    creation_date = models.DateTimeField(auto_now_add=True)
    modified_date = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Sensor Fleet"
        verbose_name_plural = "Sensor Fleets"
        ordering = ["-modified_date"]

    def __str__(self) -> str:
        return f"Sensor Fleet: {self.name}"


class Sensor(models.Model):
    id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        primary_key=True,
    )

    name = models.CharField(
        max_length=50,
        help_text="Sensor name (e.g., 'Flow Meters #023')",
    )

    notes = models.TextField(
        blank=True,
        default="",
        help_text="Optional notes for the sensor",
    )

    fleet = models.ForeignKey(
        SensorFleet,
        related_name="sensors",
        on_delete=models.CASCADE,
        blank=False,
        null=False,
    )

    is_functional = models.BooleanField(default=True)

    # Metadata
    created_by = models.EmailField(
        null=False,
        blank=False,
        help_text="User who created the sensor fleet.",
    )

    creation_date = models.DateTimeField(auto_now_add=True)
    modified_date = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-modified_date"]

    def __str__(self) -> str:
        return (
            f"Sensor: {self.name} [Status: {'OK' if self.is_functional else 'NOT OK'}]"
        )


class SensorFleetUserPermission(models.Model):
    id: int

    user = models.ForeignKey(
        User,
        related_name="rel_sensorfleet_permissions",
        on_delete=models.CASCADE,
        blank=False,
        null=False,
    )

    sensor_fleet = models.ForeignKey(
        SensorFleet,
        related_name="rel_user_permissions",
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
        verbose_name = "Sensor Fleet - User Permission"
        verbose_name_plural = "Sensor Fleet - User Permissions"
        unique_together = ("user", "sensor_fleet")
        indexes = [
            models.Index(fields=["user", "is_active"]),
            models.Index(fields=["sensor_fleet", "is_active"]),
            models.Index(fields=["user", "sensor_fleet", "is_active"]),
        ]

    def __str__(self) -> str:
        return f"{self.user} => {self.sensor_fleet} [{self.level}]"

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
