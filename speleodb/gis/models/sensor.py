# -*- coding: utf-8 -*-

from __future__ import annotations

import logging
import uuid
from datetime import date
from datetime import timedelta
from typing import TYPE_CHECKING

from django.db import models
from django.db.models import CheckConstraint
from django.db.models import F
from django.db.models import Q
from django.db.models import QuerySet
from django.utils import timezone

from speleodb.common.enums import PermissionLevel
from speleodb.gis.models import Station
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


class SensorStatus(models.TextChoices):
    FUNCTIONAL = "functional", "Functional"
    BROKEN = "broken", "Broken"
    LOST = "lost", "Lost"
    ABANDONED = "abandoned", "Abandoned"


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

    status = models.CharField(
        max_length=20,
        choices=SensorStatus,
        default=SensorStatus.FUNCTIONAL,
        null=False,
        blank=False,
    )

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
        return f"Sensor: {self.name} [Status: {self.status.upper()}]"


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


class InstallStatus(models.TextChoices):
    INSTALLED = "installed", "Installed"
    RETRIEVED = "retrieved", "Retrieved"
    LOST = "lost", "Lost"
    ABANDONED = "abandoned", "Abandoned"


class SensorInstallQuerySet(models.QuerySet["SensorInstall"]):
    def due_for_retrieval(self, days: int | None = None) -> QuerySet[SensorInstall]:
        """
        Returns SensorInstalls that are due for retrieval.

        Behavior:
        - days=None → STRICT: only dates strictly in the past (expired)
        - days=N → include items expiring within the next N days
        """

        today = timezone.localdate()

        qs = self.filter(status=InstallStatus.INSTALLED)

        cutoff_date: date
        match days:
            case None:
                # Strict expired only
                cutoff_date = today

            case int():
                # days >= 0 → grow the window
                cutoff_date = today + timedelta(days=days)

            case _:
                raise TypeError(
                    f"Unexpected type received: {type(days)}. Expects: int | None"
                )

        return qs.filter(
            models.Q(expiracy_battery_date__lt=cutoff_date)
            | models.Q(expiracy_memory_date__lt=cutoff_date)
        )


class SensorInstallManager(models.Manager["SensorInstall"]):
    def due_for_retrieval(self, days: int | None = None) -> QuerySet[SensorInstall]:
        return SensorInstallQuerySet(self.model, using=self._db).due_for_retrieval(
            days=days
        )


class SensorInstall(models.Model):
    id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        primary_key=True,
    )

    sensor = models.ForeignKey(
        Sensor,
        related_name="installs",
        on_delete=models.CASCADE,
        blank=False,
        null=False,
    )

    station = models.ForeignKey(
        Station,
        related_name="sensor_installs",
        on_delete=models.CASCADE,
        blank=False,
        null=False,
    )

    install_date = models.DateField(null=False, blank=False)
    install_user = models.EmailField(
        null=False,
        blank=False,
        help_text="User who installed the sensor.",
    )

    uninstall_date = models.DateField(null=True, blank=True, default=None)
    uninstall_user = models.EmailField(  # noqa: DJ001
        # must be null not blank to not fail the condition
        # `retrieval_fields_match_is_retrieved`
        null=True,
        blank=True,
        default=None,
        help_text="User who retrieved the sensor.",
    )

    status = models.CharField(
        max_length=20,
        choices=InstallStatus,
        default=InstallStatus.INSTALLED,
    )

    expiracy_memory_date = models.DateField(null=True, blank=True)
    expiracy_battery_date = models.DateField(null=True, blank=True)

    # Metadata
    created_by = models.EmailField(
        null=False,
        blank=False,
        help_text="User who created the sensor fleet.",
    )

    creation_date = models.DateTimeField(auto_now_add=True)
    modified_date = models.DateTimeField(auto_now=True)

    objects = SensorInstallManager()

    class Meta:
        verbose_name = "Sensor Install"
        verbose_name_plural = "Sensor Installs"
        ordering = ["-modified_date"]

        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["sensor", "status"]),
            models.Index(fields=["station", "status"]),
        ]

        constraints = [
            # uninstall_date/user fields match status
            CheckConstraint(
                condition=(
                    Q(
                        ~Q(status=InstallStatus.INSTALLED),
                        uninstall_date__isnull=False,
                        uninstall_user__isnull=False,
                    )
                    | Q(
                        status=InstallStatus.INSTALLED,
                        uninstall_date__isnull=True,
                        uninstall_user__isnull=True,
                    )
                ),
                name="uninstall_fields_match_is_installed",
            ),
            # install_date <= uninstall_date
            CheckConstraint(
                condition=Q(uninstall_date__isnull=True)
                | Q(install_date__lte=F("uninstall_date")),
                name="install_before_or_equal_retrieval",
            ),
            # only one installed sensor per sensor at a time
            models.UniqueConstraint(
                fields=["sensor"],
                condition=Q(status=InstallStatus.INSTALLED),
                name="unique_installed_per_sensor",
            ),
            # install_date <= expiracy_memory_date if set
            CheckConstraint(
                condition=Q(expiracy_memory_date__isnull=True)
                | Q(install_date__lte=F("expiracy_memory_date")),
                name="install_before_or_equal_memory_expiracy",
            ),
            # install_date <= expiracy_battery_date if set
            CheckConstraint(
                condition=Q(expiracy_battery_date__isnull=True)
                | Q(install_date__lte=F("expiracy_battery_date")),
                name="install_before_or_equal_battery_expiracy",
            ),
        ]

    def __str__(self) -> str:
        return f"[STATUS: {self.status.upper()}]: Sensor: {self.sensor.id}"
