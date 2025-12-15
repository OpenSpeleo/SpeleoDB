# -*- coding: utf-8 -*-

from __future__ import annotations

import logging
import uuid
from datetime import date
from datetime import timedelta
from typing import TYPE_CHECKING

from django.core.validators import MaxValueValidator
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import CheckConstraint
from django.db.models import F
from django.db.models import Q
from django.db.models import QuerySet
from django.utils import timezone

from speleodb.common.enums import PermissionLevel
from speleodb.gis.models.enums import InstallStatus
from speleodb.gis.models.enums import OperationalStatus
from speleodb.users.models import User

if TYPE_CHECKING:
    from django_stubs_ext import StrOrPromise


logger = logging.getLogger(__name__)


class TankFleet(models.Model):
    tanks: models.QuerySet[Tank]
    user_permissions: models.QuerySet[TankFleetUserPermission]

    id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        primary_key=True,
    )

    name = models.CharField(
        max_length=50,
        help_text="Tank Fleet name (e.g., 'Wakulla Project Tanks')",
    )

    description = models.TextField(
        blank=True,
        default="",
        help_text="Optional description of the tank fleet",
    )

    is_active = models.BooleanField(default=True)

    # Metadata
    created_by = models.EmailField(
        null=False,
        blank=False,
        help_text="User who created the tank fleet.",
    )

    creation_date = models.DateTimeField(auto_now_add=True)
    modified_date = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Tank Fleet"
        verbose_name_plural = "Tank Fleets"
        ordering = ["-modified_date"]
        indexes = [
            models.Index(fields=["is_active"]),
        ]

    def __str__(self) -> str:
        return f"Tank Fleet: {self.name}"


class Tank(models.Model):
    installs: models.QuerySet[TankInstall]

    id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        primary_key=True,
    )

    name = models.CharField(
        max_length=50,
        help_text="Tank name (e.g., 'Tank #023')",
    )

    owner = models.CharField(
        max_length=255,
        blank=True,
        help_text="Tank owner (e.g., 'John Doe')",
    )

    notes = models.TextField(
        blank=True,
        default="",
        help_text="Optional notes for the tank",
    )

    type = models.CharField(
        max_length=100,
        blank=True,
        help_text="Tank type/model (e.g., 'AL80, AL40')",
    )

    o2_percentage = models.DecimalField(
        max_digits=3,
        decimal_places=0,
        null=False,
        blank=False,
        help_text="O2 percentage (e.g., '21%')",
        validators=[MinValueValidator(0.0), MaxValueValidator(100.0)],
    )

    he_percentage = models.DecimalField(
        max_digits=3,
        decimal_places=0,
        null=False,
        blank=False,
        help_text="He percentage (e.g., '79%')",
        validators=[MinValueValidator(0.0), MaxValueValidator(100.0)],
    )

    pressure = models.IntegerField(
        null=False,
        blank=False,
        help_text="Tank pressure in PSI or BARs (e.g., '3000')",
        validators=[MinValueValidator(0)],
    )

    pressure_unit = models.CharField(
        max_length=10,
        null=False,
        blank=False,
        help_text="Tank pressure unit (e.g., 'PSI' or 'BAR')",
    )

    fleet = models.ForeignKey(
        TankFleet,
        related_name="tanks",
        on_delete=models.CASCADE,
        blank=False,
        null=False,
    )

    status = models.CharField(
        max_length=20,
        choices=OperationalStatus,
        default=OperationalStatus.FUNCTIONAL,
        null=False,
        blank=False,
    )

    # Metadata
    created_by = models.EmailField(
        null=False,
        blank=False,
        help_text="User who created the tank fleet.",
    )

    creation_date = models.DateTimeField(auto_now_add=True)
    modified_date = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-modified_date"]
        indexes = [
            models.Index(fields=["fleet"]),
            models.Index(fields=["status"]),
            models.Index(fields=["fleet", "status"]),
        ]
        constraints = [
            CheckConstraint(
                condition=F("o2_percentage") + F("he_percentage") <= 100,  # noqa: PLR2004  # pyright: ignore[reportOperatorIssue]
                name="o2_he_sum_lte_100",
            )
        ]

    def __str__(self) -> str:
        return f"Tank: {self.name} [Status: {self.status.upper()}]"


class TankFleetUserPermission(models.Model):
    id: int

    user = models.ForeignKey(
        User,
        related_name="tankfleet_permissions",
        on_delete=models.CASCADE,
        blank=False,
        null=False,
    )

    tank_fleet = models.ForeignKey(
        TankFleet,
        related_name="user_permissions",
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
        verbose_name = "Tank Fleet - User Permission"
        verbose_name_plural = "Tank Fleet - User Permissions"
        unique_together = ("user", "tank_fleet")
        indexes = [
            models.Index(fields=["user", "is_active"]),
            models.Index(fields=["tank_fleet", "is_active"]),
            models.Index(fields=["user", "tank_fleet", "is_active"]),
        ]

    def __str__(self) -> str:
        return f"{self.user} => {self.tank_fleet} [{self.level}]"

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


class TankInstallQuerySet(models.QuerySet["TankInstall"]):
    def due_for_retrieval(self, days: int | None = None) -> QuerySet[TankInstall]:
        """
        Returns TankInstalls that are due for retrieval.

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


class TankInstallManager(models.Manager["TankInstall"]):
    def due_for_retrieval(self, days: int | None = None) -> QuerySet[TankInstall]:
        return TankInstallQuerySet(self.model, using=self._db).due_for_retrieval(
            days=days
        )


class TankInstall(models.Model):
    id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        primary_key=True,
    )

    tank = models.ForeignKey(
        Tank,
        related_name="installs",
        on_delete=models.CASCADE,
        blank=False,
        null=False,
    )

    # Tank Coordinates
    latitude = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        null=False,
        blank=False,
        help_text="Station latitude coordinate",
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
    )

    longitude = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        null=False,
        blank=False,
        help_text="Station longitude coordinate",
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
    )

    last_check_date = models.DateField(null=False, blank=False)
    last_check_user = models.EmailField(
        null=False,
        blank=False,
        help_text="User who last checked the tank.",
    )

    install_date = models.DateField(null=False, blank=False)
    install_user = models.EmailField(
        null=False,
        blank=False,
        help_text="User who installed the tank.",
    )

    uninstall_date = models.DateField(null=True, blank=True, default=None)
    uninstall_user = models.EmailField(  # noqa: DJ001
        # must be null not blank to not fail the condition
        # `retrieval_fields_match_is_retrieved`
        null=True,
        blank=True,
        default=None,
        help_text="User who retrieved the tank.",
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
        help_text="User who created the tank fleet.",
    )

    creation_date = models.DateTimeField(auto_now_add=True)
    modified_date = models.DateTimeField(auto_now=True)

    objects = TankInstallManager()

    class Meta:
        verbose_name = "Tank Install"
        verbose_name_plural = "Tank Installs"
        ordering = ["-modified_date"]

        indexes = [
            # models.Index(fields=["status"]),  # we never filter only by status
            models.Index(fields=["tank"]),
            models.Index(fields=["station"]),
            models.Index(fields=["tank", "station"]),
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
            # only one installed tank per tank at a time
            models.UniqueConstraint(
                fields=["tank"],
                condition=Q(status=InstallStatus.INSTALLED),
                name="unique_installed_per_tank",
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
        return f"[STATUS: {self.status.upper()}]: Tank: {self.tank.id}"
