# -*- coding: utf-8 -*-

"""Admin module for Django."""

from __future__ import annotations

from django.contrib import admin

from speleodb.gis.models import CylinderFleetUserPermission

# ruff: noqa: SLF001


class CylinderFleetUserPermissionProxy(CylinderFleetUserPermission):
    class Meta:
        proxy = True
        app_label = "permissions"
        verbose_name = CylinderFleetUserPermission._meta.verbose_name  # type: ignore[assignment]
        verbose_name_plural = CylinderFleetUserPermission._meta.verbose_name_plural  # type: ignore[assignment]


@admin.register(CylinderFleetUserPermissionProxy)
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
