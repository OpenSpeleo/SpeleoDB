# -*- coding: utf-8 -*-

"""Admin module for Django."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.contrib import admin

from speleodb.common.enums import UnitSystem
from speleodb.gis.models import Cylinder
from speleodb.gis.models import CylinderFleet
from speleodb.gis.models import CylinderFleetUserPermission
from speleodb.gis.models import CylinderInstall
from speleodb.gis.models import CylinderPressureCheck

if TYPE_CHECKING:
    from django import forms
    from django.http import HttpRequest


@admin.register(CylinderFleet)
class CylinderFleetAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    """Admin interface for managing Cylinder Fleets."""

    list_display = (
        "name",
        "created_by",
        "is_active",
        "cylinder_count",
        "permission_count",
        "creation_date",
        "modified_date",
    )

    list_filter = (
        "is_active",
        "creation_date",
        "modified_date",
    )

    search_fields = (
        "name",
        "description",
        "created_by",
    )

    readonly_fields = (
        "id",
        "created_by",
        "creation_date",
        "modified_date",
        "cylinder_count",
        "permission_count",
    )

    ordering = ("-modified_date",)

    fieldsets = (
        (
            "Basic Information",
            {
                "fields": (
                    "name",
                    "description",
                    "is_active",
                )
            },
        ),
        (
            "Metadata",
            {
                "fields": (
                    "id",
                    "created_by",
                    "creation_date",
                    "modified_date",
                    "cylinder_count",
                    "permission_count",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    @admin.display(description="Cylinders")
    def cylinder_count(self, obj: CylinderFleet) -> int:
        """Display the number of cylinders in this fleet."""
        if obj and obj.pk:
            return obj.cylinders.count()
        return 0

    @admin.display(description="User Permissions")
    def permission_count(self, obj: CylinderFleet) -> int:
        """Display the number of user permissions for this fleet."""
        if obj and obj.pk:
            return obj.user_permissions.count()
        return 0

    def save_model(
        self,
        request: HttpRequest,
        obj: CylinderFleet,
        form: forms.ModelForm[CylinderFleet],
        change: bool,
    ) -> None:
        # Auto-populate created_by field when creating a new cylinder fleet
        if not change:  # Only on creation, not on edit
            obj.created_by = request.user.email  # type: ignore[union-attr]
        super().save_model(request, obj, form, change)


@admin.register(Cylinder)
class CylinderAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    """Admin interface for managing Cylinders."""

    list_display = (
        "name",
        "serial",
        "brand",
        "fleet",
        "status",
        "gas_mix_display",
        "pressure_display",
        "manufactured_date",
        "last_visual_inspection_date",
        "last_hydrostatic_test_date",
        "use_anode",
        "created_by",
        "creation_date",
        "modified_date",
    )

    list_filter = (
        "fleet",
        "status",
        "unit_system",
        "use_anode",
        "manufactured_date",
        "last_visual_inspection_date",
        "last_hydrostatic_test_date",
        "creation_date",
        "modified_date",
    )

    search_fields = (
        "name",
        "serial",
        "brand",
        "owner",
        "type",
        "notes",
        "fleet__name",
        "created_by",
    )

    readonly_fields = (
        "id",
        "created_by",
        "creation_date",
        "modified_date",
        "n2_percentage",
    )

    ordering = ("-modified_date",)

    fieldsets = (
        (
            "Basic Information",
            {
                "fields": (
                    "name",
                    "serial",
                    "brand",
                    "fleet",
                    "owner",
                    "type",
                    "notes",
                    "status",
                    "use_anode",
                )
            },
        ),
        (
            "Gas Mix",
            {
                "fields": (
                    "o2_percentage",
                    "he_percentage",
                    "n2_percentage",
                )
            },
        ),
        (
            "Pressure",
            {
                "fields": (
                    "pressure",
                    "unit_system",
                )
            },
        ),
        (
            "Dates & Inspections",
            {
                "fields": (
                    "manufactured_date",
                    "last_visual_inspection_date",
                    "last_hydrostatic_test_date",
                )
            },
        ),
        (
            "Metadata",
            {
                "fields": (
                    "id",
                    "created_by",
                    "creation_date",
                    "modified_date",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    @admin.display(description="Gas Mix")
    def gas_mix_display(self, obj: Cylinder) -> str:
        """Display gas mix in a compact format."""
        if obj.o2_percentage is None or obj.he_percentage is None:
            return "-"

        # Trimix: He > 0 => O2/He format
        if obj.he_percentage > 0:
            return f"{obj.o2_percentage}/{obj.he_percentage}"

        # Air: 21% O2 and 0% He
        if obj.o2_percentage == 21:  # noqa: PLR2004
            return "Air"

        # Pure Oxygen
        if obj.o2_percentage == 100:  # noqa: PLR2004
            return "Oxygen"

        # Nitrox: NX{O2}
        return f"NX{obj.o2_percentage}"

    @admin.display(description="Pressure")
    def pressure_display(self, obj: Cylinder) -> str:
        """Display pressure with unit."""
        if obj.pressure is None or obj.unit_system is None:
            return "-"
        unit = "PSI" if obj.unit_system == UnitSystem.IMPERIAL else "BAR"
        return f"{obj.pressure} {unit}"

    @admin.display(description="N2 %")
    def n2_percentage(self, obj: Cylinder) -> int | str:
        """Display calculated N2 percentage."""
        if obj.o2_percentage is None or obj.he_percentage is None:
            return "-"
        return obj.n2_percentage

    def save_model(
        self,
        request: HttpRequest,
        obj: Cylinder,
        form: forms.ModelForm[Cylinder],
        change: bool,
    ) -> None:
        # Auto-populate created_by field when creating a new cylinder
        if not change:  # Only on creation, not on edit
            obj.created_by = request.user.email  # type: ignore[union-attr]
        super().save_model(request, obj, form, change)


@admin.register(CylinderInstall)
class CylinderInstallAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    """Admin interface for managing Cylinder Installs."""

    list_display = (
        "id",
        "cylinder",
        "status",
        "install_date",
        "uninstall_date",
        "install_user",
        "uninstall_user",
        "location_name",
        "distance_from_entry",
        "unit_system",
        "latitude",
        "longitude",
        "created_by",
        "creation_date",
        "modified_date",
    )

    list_filter = (
        "status",
        "install_date",
        "uninstall_date",
        "unit_system",
        "creation_date",
        "modified_date",
    )

    search_fields = (
        "cylinder__id",
        "cylinder__name",
        "location_name",
        "install_user",
        "uninstall_user",
        "created_by",
    )

    date_hierarchy = "install_date"

    readonly_fields = ("created_by", "creation_date", "modified_date")

    ordering = ("-modified_date",)

    fieldsets = (
        (
            "Cylinder",
            {
                "fields": (
                    "cylinder",
                    "notes",
                )
            },
        ),
        (
            "Installation Info",
            {
                "fields": (
                    "install_date",
                    "install_user",
                    "uninstall_date",
                    "uninstall_user",
                    "status",
                )
            },
        ),
        (
            "Location",
            {
                "fields": (
                    "location_name",
                    "distance_from_entry",
                    "unit_system",
                    "latitude",
                    "longitude",
                )
            },
        ),
        (
            "Metadata",
            {
                "fields": (
                    "created_by",
                    "creation_date",
                    "modified_date",
                )
            },
        ),
    )

    def save_model(
        self,
        request: HttpRequest,
        obj: CylinderInstall,
        form: forms.ModelForm[CylinderInstall],
        change: bool,
    ) -> None:
        # Auto-populate created_by field when creating a new cylinder install
        if not change:  # Only on creation, not on edit
            obj.created_by = request.user.email  # type: ignore[union-attr]
        super().save_model(request, obj, form, change)


@admin.register(CylinderPressureCheck)
class CylinderPressureCheckAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    """Admin interface for managing Cylinder Pressure Checks."""

    list_display = (
        "id",
        "install",
        "check_date",
        "pressure",
        "unit_system",
        "user",
        "creation_date",
        "modified_date",
    )

    list_filter = (
        "unit_system",
        "check_date",
        "creation_date",
        "modified_date",
    )

    search_fields = (
        "install__cylinder__id",
        "install__cylinder__name",
        "user",
        "notes",
    )

    readonly_fields = ("id", "creation_date", "modified_date")

    ordering = ("-check_date", "-modified_date")

    fieldsets = (
        (
            "Pressure Check",
            {
                "fields": (
                    "install",
                    "check_date",
                    "pressure",
                    "unit_system",
                    "user",
                    "notes",
                )
            },
        ),
        (
            "Timestamps",
            {
                "fields": (
                    "id",
                    "creation_date",
                    "modified_date",
                )
            },
        ),
    )


@admin.register(CylinderFleetUserPermission)
class CylinderFleetUserPermissionAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    """Admin interface for Cylinder Fleet User Permissions."""

    list_display = (
        "user",
        "cylinder_fleet",
        "level_label",
        "is_active",
        "creation_date",
        "modified_date",
        "deactivated_by",
    )

    list_filter = (
        "is_active",
        "level",
        "creation_date",
        "modified_date",
    )

    search_fields = (
        "user__email",
        "user__name",
        "cylinder_fleet__name",
    )

    readonly_fields = (
        "creation_date",
        "modified_date",
    )

    ordering = ("-modified_date",)

    fieldsets = (
        (
            "Permission",
            {
                "fields": (
                    "user",
                    "cylinder_fleet",
                    "level",
                    "is_active",
                )
            },
        ),
        (
            "Deactivation",
            {"fields": ("deactivated_by",)},
        ),
        (
            "Metadata",
            {
                "fields": (
                    "creation_date",
                    "modified_date",
                )
            },
        ),
    )

    @admin.display(description="Level")
    def level_label(self, obj: CylinderFleetUserPermission) -> str:
        """Display the permission level label."""
        return str(obj.level_label)
