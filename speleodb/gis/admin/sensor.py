# -*- coding: utf-8 -*-

"""Admin module for Django."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.contrib import admin

from speleodb.gis.models import Sensor
from speleodb.gis.models import SensorFleet
from speleodb.gis.models import SensorFleetUserPermission
from speleodb.gis.models import SensorInstall
from speleodb.gis.models import Station

if TYPE_CHECKING:
    from django import forms
    from django.http import HttpRequest


@admin.register(SensorFleet)
class SensorFleetAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    """Admin interface for managing Sensor Fleets."""

    list_display = (
        "name",
        "created_by",
        "is_active",
        "sensor_count",
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
        "sensor_count",
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
                    "sensor_count",
                    "permission_count",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    @admin.display(description="Sensors")
    def sensor_count(self, obj: SensorFleet) -> int:
        """Display the number of sensors in this fleet."""
        if obj and obj.pk:
            return obj.sensors.count()
        return 0

    @admin.display(description="User Permissions")
    def permission_count(self, obj: SensorFleet) -> int:
        """Display the number of user permissions for this fleet."""
        if obj and obj.pk:
            return obj.rel_user_permissions.count()
        return 0

    def save_model(
        self,
        request: HttpRequest,
        obj: SensorFleet,
        form: forms.ModelForm[SensorFleet],
        change: bool,
    ) -> None:
        # Auto-populate created_by field when creating a new sensor fleet
        if not change:  # Only on creation, not on edit
            obj.created_by = request.user.email  # type: ignore[union-attr]
        super().save_model(request, obj, form, change)


@admin.register(Sensor)
class SensorAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    """Admin interface for managing Sensors."""

    list_display = (
        "name",
        "fleet",
        "status",
        "created_by",
        "creation_date",
        "modified_date",
    )

    list_filter = (
        "fleet",
        "status",
        "creation_date",
        "modified_date",
    )

    search_fields = (
        "fleet__name",
        "name",
        "notes",
        "created_by",
    )

    readonly_fields = (
        "id",
        "created_by",
        "creation_date",
        "modified_date",
    )

    ordering = ("-modified_date",)

    fieldsets = (
        (
            "Basic Information",
            {
                "fields": (
                    "name",
                    "fleet",
                    "notes",
                    "status",
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

    def save_model(
        self,
        request: HttpRequest,
        obj: Sensor,
        form: forms.ModelForm[Sensor],
        change: bool,
    ) -> None:
        # Auto-populate created_by field when creating a new sensor
        if not change:  # Only on creation, not on edit
            obj.created_by = request.user.email  # type: ignore[union-attr]
        super().save_model(request, obj, form, change)


@admin.register(SensorFleetUserPermission)
class SensorFleetUserPermissionAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    """Admin interface for managing Sensor Fleet User Permissions."""

    list_display = (
        "sensor_fleet",
        "user",
        "level_display",
        "is_active",
        "creation_date",
        "modified_date",
    )

    list_filter = (
        "is_active",
        "level",
        "creation_date",
        "modified_date",
    )

    search_fields = (
        "user__email",
        "sensor_fleet__name",
    )

    readonly_fields = (
        "creation_date",
        "modified_date",
    )

    ordering = ("sensor_fleet", "user")

    fieldsets = (
        (
            "Permission Information",
            {
                "fields": (
                    "sensor_fleet",
                    "user",
                    "level",
                    "is_active",
                )
            },
        ),
        (
            "Deactivation",
            {
                "fields": ("deactivated_by",),
                "classes": ("collapse",),
            },
        ),
        (
            "Metadata",
            {
                "fields": (
                    "creation_date",
                    "modified_date",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    @admin.display(description="Permission Level")
    def level_display(self, obj: SensorFleetUserPermission) -> str:
        """Display the permission level label."""
        if obj:
            return obj.level_label  # type: ignore[return-value]
        return "-"


@admin.register(SensorInstall)
class SensorInstallAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    # Columns to display in the list view
    list_display = (
        "id",
        "sensor",
        "station",
        "status",
        "install_date",
        "uninstall_date",
        "install_user",
        "uninstall_user",
        "expiracy_memory_date",
        "expiracy_battery_date",
        "created_by",
        "creation_date",
        "modified_date",
    )

    # Filters on the right sidebar
    list_filter = (
        "status",
        "install_date",
        "uninstall_date",
        "expiracy_memory_date",
        "expiracy_battery_date",
    )

    # Fields you can search by
    search_fields = (
        "sensor__id",
        "sensor__name",  # if your Sensor model has a name
        "station__name",  # if your Station model has a name
        "install_user",
        "uninstall_user",
        "created_by",
    )

    # Makes the install and retrieval dates navigable by date hierarchy
    date_hierarchy = "install_date"

    # Readonly fields (cannot be edited in admin)
    readonly_fields = ("creation_date", "modified_date", "created_by")

    # Ordering in the list view (optional, already set in Meta)
    ordering = ("-modified_date",)

    # Optional: grouping fields in the edit form
    fieldsets = (
        ("Sensor & Station", {"fields": ("sensor", "station")}),
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
            "Expiry Info",
            {"fields": ("expiracy_memory_date", "expiracy_battery_date")},
        ),
        ("Metadata", {"fields": ("created_by", "creation_date", "modified_date")}),
    )

    def save_model(
        self,
        request: HttpRequest,
        obj: Station,
        form: forms.ModelForm[Station],
        change: bool,
    ) -> None:
        # Auto-populate created_by field when creating a new station
        if not change:  # Only on creation, not on edit
            obj.created_by = request.user.email  # type: ignore[union-attr]
        super().save_model(request, obj, form, change)
