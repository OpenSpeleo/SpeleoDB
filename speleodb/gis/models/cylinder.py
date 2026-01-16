# -*- coding: utf-8 -*-

from __future__ import annotations

import logging
import uuid
from datetime import date
from datetime import timedelta
from typing import TYPE_CHECKING

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import CheckConstraint
from django.db.models import F
from django.db.models import Q
from django.db.models import QuerySet
from django.utils import timezone

from speleodb.common.enums import InstallStatus
from speleodb.common.enums import OperationalStatus
from speleodb.common.enums import PermissionLevel
from speleodb.common.enums import UnitSystem
from speleodb.surveys.models import Project
from speleodb.users.models import User

if TYPE_CHECKING:
    from django_stubs_ext import StrOrPromise


logger = logging.getLogger(__name__)


class CylinderFleet(models.Model):
    cylinders: models.QuerySet[Cylinder]
    user_permissions: models.QuerySet[CylinderFleetUserPermission]

    id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        primary_key=True,
    )

    name = models.CharField(
        max_length=50,
        help_text="Cylinder Fleet name (e.g., 'Wakulla Project Cylinders')",
    )

    description = models.TextField(
        blank=True,
        default="",
        help_text="Optional description of the cylinder fleet",
    )

    is_active = models.BooleanField(default=True)

    # Metadata
    created_by = models.EmailField(
        null=False,
        blank=False,
        help_text="User who created the cylinder fleet.",
    )

    creation_date = models.DateTimeField(auto_now_add=True)
    modified_date = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Cylinder Fleet"
        verbose_name_plural = "Cylinder Fleets"
        ordering = ["-modified_date"]
        indexes = [
            models.Index(fields=["is_active"]),
        ]

    def __str__(self) -> str:
        return f"Cylinder Fleet: {self.name}"


class Cylinder(models.Model):
    installs: models.QuerySet[CylinderInstall]

    id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        primary_key=True,
    )

    name = models.CharField(
        max_length=50,
        help_text="Cylinder name (e.g., 'Cylinder #023')",
        blank=True,
    )

    serial = models.CharField(
        max_length=15,
        help_text="Cylinder Serial Number",
        blank=True,
    )

    brand = models.CharField(
        max_length=50,
        help_text="Cylinder Brand: Luxfer, Catalina, etc.",
        blank=True,
    )

    owner = models.CharField(
        max_length=255,
        blank=True,
        help_text="Cylinder owner (e.g., 'John Doe')",
    )

    notes = models.TextField(
        blank=True,
        help_text="Optional notes for the cylinder",
    )

    type = models.CharField(
        max_length=100,
        blank=True,
        help_text="Cylinder type/model (e.g., 'AL80, AL40')",
    )

    o2_percentage = models.IntegerField(
        null=False,
        blank=False,
        help_text="O2 percentage (e.g., '21%')",
        validators=[MinValueValidator(0.0), MaxValueValidator(100.0)],
    )

    he_percentage = models.IntegerField(
        null=False,
        blank=False,
        help_text="He percentage (e.g., '79%')",
        validators=[MinValueValidator(0.0), MaxValueValidator(100.0)],
    )

    pressure = models.IntegerField(
        null=False,
        blank=False,
        help_text="Cylinder pressure in PSI or BARs (e.g., '3000')",
        validators=[MinValueValidator(0)],
    )

    unit_system = models.CharField(
        max_length=10,
        null=False,
        blank=False,
        choices=UnitSystem.choices,
        help_text="Cylinder pressure unit Imperial (PSI) or Metric (BAR)",
    )

    fleet = models.ForeignKey(
        CylinderFleet,
        related_name="cylinders",
        on_delete=models.CASCADE,
        blank=False,
        null=False,
    )

    use_anode = models.BooleanField(default=False)

    last_visual_inspection_date = models.DateField(null=True, blank=True)
    last_hydrostatic_test_date = models.DateField(null=True, blank=True)

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
        help_text="User who created the cylinder fleet.",
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
            models.CheckConstraint(
                # Convoluted and only way to do: (O2 + He) <= 100%
                condition=Q(o2_percentage__lte=100 - F("he_percentage")),
                name="o2_he_sum_lte_100",
            ),
            CheckConstraint(
                condition=(
                    Q(unit_system=UnitSystem.METRIC, pressure__lte=400)
                    | Q(unit_system=UnitSystem.IMPERIAL, pressure__lte=5000)
                ),
                name="pressure_matches_unit_system",
            ),
        ]

    def __str__(self) -> str:
        return f"Cylinder: {self.name} [Status: {self.status.upper()}]"

    def clean(self) -> None:
        super().clean()

        match self.unit_system:
            case UnitSystem.METRIC:
                if self.pressure > 400:  # noqa: PLR2004
                    raise ValidationError(
                        {"pressure": "Maximum pressure for BAR is 400."}
                    )

            case UnitSystem.IMPERIAL:
                if self.pressure > 5000:  # noqa: PLR2004
                    raise ValidationError(
                        {"pressure": "Maximum pressure for PSI is 5000."}
                    )

            case _:
                raise ValidationError({"unit_system": "Invalid unit system."})

    @property
    def n2_percentage(self) -> int:
        return 100 - self.o2_percentage - self.he_percentage


class CylinderInstallQuerySet(models.QuerySet["CylinderInstall"]):
    def due_for_retrieval(self, days: int | None = None) -> QuerySet[CylinderInstall]:
        """
        Returns CylinderInstalls that are due for retrieval.

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


class CylinderInstallManager(models.Manager["CylinderInstall"]):
    def due_for_retrieval(self, days: int | None = None) -> QuerySet[CylinderInstall]:
        return CylinderInstallQuerySet(self.model, using=self._db).due_for_retrieval(
            days=days
        )


class CylinderInstall(models.Model):
    pressure_checks: QuerySet[CylinderPressureCheck]

    id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        primary_key=True,
    )

    cylinder = models.ForeignKey(
        Cylinder,
        related_name="installs",
        on_delete=models.CASCADE,
        blank=False,
        null=False,
    )

    # Cylinder Coordinates
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

    notes = models.TextField(
        blank=True,
        default="",
        help_text="Optional notes for the cylinder install",
    )

    location_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Name of the location where the cylinder is installed",
    )

    project = models.ForeignKey(
        Project,
        related_name="cylinder_installs",
        on_delete=models.CASCADE,
        null=False,
        blank=False,
        help_text="Project where the cylinder is installed",
    )

    distance_from_entry = models.IntegerField(
        default=None,
        null=True,
        blank=True,
        help_text="Distance from the entry of the location",
    )

    unit_system = models.CharField(
        max_length=10,
        null=False,
        blank=False,
        default=UnitSystem.METRIC,
        choices=UnitSystem.choices,
        help_text="Distance unit. Imperial: Feet, Metric: Meters",
    )

    install_date = models.DateField(null=False, blank=False)
    install_user = models.EmailField(
        null=False,
        blank=False,
        help_text="User who installed the cylinder.",
    )

    uninstall_date = models.DateField(null=True, blank=True, default=None)
    uninstall_user = models.EmailField(  # noqa: DJ001
        # must be null not blank to not fail DB conditions
        null=True,
        blank=True,
        default=None,
        help_text="User who retrieved the cylinder.",
    )

    status = models.CharField(
        max_length=20,
        choices=InstallStatus,
        default=InstallStatus.INSTALLED,
    )

    # Metadata
    created_by = models.EmailField(
        null=False,
        blank=False,
        help_text="User who created the cylinder fleet.",
    )

    creation_date = models.DateTimeField(auto_now_add=True)
    modified_date = models.DateTimeField(auto_now=True)

    objects = CylinderInstallManager()

    class Meta:
        verbose_name = "Cylinder Install"
        verbose_name_plural = "Cylinder Installs"
        ordering = ["-modified_date"]

        indexes = [
            # models.Index(fields=["status"]),  # we never filter only by status
            models.Index(fields=["cylinder"]),
            models.Index(fields=["latitude", "longitude"]),
            models.Index(fields=["cylinder", "status"]),
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
                name="cylinder_uninstall_fields_match_is_installed",
            ),
            # install_date <= uninstall_date
            CheckConstraint(
                condition=Q(uninstall_date__isnull=True)
                | Q(install_date__lte=F("uninstall_date")),
                name="cylinder_install_before_or_equal_retrieval",
            ),
            # only one installed cylinder per cylinder at a time
            models.UniqueConstraint(
                fields=["cylinder"],
                condition=Q(status=InstallStatus.INSTALLED),
                name="%(app_label)s_%(class)s_installed_per_cylinder_unique",
            ),
        ]

    def __str__(self) -> str:
        return f"[STATUS: {self.status.upper()}]: Cylinder: {self.cylinder.id}"


class CylinderPressureCheck(models.Model):
    id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        primary_key=True,
    )

    user = models.EmailField(
        blank=True,
        help_text="User who did the pressure check.",
    )

    notes = models.TextField(
        blank=True,
        default="",
        help_text="Optional notes for the cylinder pressure check",
    )

    pressure = models.IntegerField(
        null=False,
        blank=False,
        help_text="Cylinder pressure in PSI or BARs (e.g., '3000')",
        validators=[MinValueValidator(0)],
    )

    unit_system = models.CharField(
        max_length=10,
        null=False,
        blank=False,
        choices=UnitSystem.choices,
        help_text="Cylinder pressure unit Imperial (PSI) or Metric (BAR)",
    )

    check_date = models.DateField(null=False, blank=False)

    install = models.ForeignKey(
        CylinderInstall,
        related_name="pressure_checks",
        on_delete=models.CASCADE,
        blank=False,
        null=False,
    )

    creation_date = models.DateTimeField(auto_now_add=True)
    modified_date = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return (
            f"[Pressure Check]: Cylinder <{self.install.cylinder_id}>: {self.pressure} "
            f"{'PSI' if self.unit_system == UnitSystem.IMPERIAL else 'BAR'}"
        )


class CylinderFleetUserPermission(models.Model):
    id: int

    user = models.ForeignKey(
        User,
        related_name="cylinderfleet_permissions",
        on_delete=models.CASCADE,
        blank=False,
        null=False,
    )

    cylinder_fleet = models.ForeignKey(
        CylinderFleet,
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
        verbose_name = "Cylinder Fleet - User Permission"
        verbose_name_plural = "Cylinder Fleet - User Permissions"
        indexes = [
            models.Index(fields=["user", "is_active"]),
            models.Index(fields=["cylinder_fleet", "is_active"]),
            models.Index(fields=["user", "cylinder_fleet", "is_active"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "cylinder_fleet"],
                name="unique_user_fleet_permission",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user} => {self.cylinder_fleet} [{self.level}]"

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
