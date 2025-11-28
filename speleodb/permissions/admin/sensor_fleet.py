# -*- coding: utf-8 -*-

"""Admin module for Django."""

from __future__ import annotations

from django.contrib import admin

from speleodb.gis.models import SensorFleetUserPermission

# ruff: noqa: SLF001


class SensorFleetUserPermissionProxy(SensorFleetUserPermission):
    class Meta:
        proxy = True
        app_label = "permissions"
        verbose_name = SensorFleetUserPermission._meta.verbose_name  # type: ignore[assignment]
        verbose_name_plural = SensorFleetUserPermission._meta.verbose_name_plural  # type: ignore[assignment]


@admin.register(SensorFleetUserPermissionProxy)
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
