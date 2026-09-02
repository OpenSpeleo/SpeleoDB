# -*- coding: utf-8 -*-

"""Django admin integration for GPS Track user permissions."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.contrib import admin

from speleodb.gis.models import GPSTrackUserPermission

if TYPE_CHECKING:
    from django.http import HttpRequest

# ruff: noqa: SLF001


class GPSTrackUserPermissionProxy(GPSTrackUserPermission):
    class Meta:
        proxy = True
        app_label = "permissions"
        verbose_name = str(GPSTrackUserPermission._meta.verbose_name)
        verbose_name_plural = str(GPSTrackUserPermission._meta.verbose_name_plural)


@admin.register(GPSTrackUserPermissionProxy)
class GPSTrackUserPermissionAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    """Admin interface for GPS Track user permissions."""

    list_display = (
        "user",
        "gps_track",
        "level_label",
        "is_active",
        "creation_date",
        "modified_date",
        "deactivated_by",
    )
    list_filter = ("is_active", "level", "creation_date", "modified_date")
    search_fields = ("user__email", "user__name", "gps_track__name")
    readonly_fields = (
        "is_active",
        "deactivated_by",
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
                    "gps_track",
                    "level",
                    "is_active",
                )
            },
        ),
        ("Deactivation", {"fields": ("deactivated_by",)}),
        (
            "Metadata",
            {"fields": ("creation_date", "modified_date")},
        ),
    )

    @admin.display(description="Level")
    def level_label(self, obj: GPSTrackUserPermission) -> str:
        return str(obj.level_label)

    def get_readonly_fields(
        self,
        request: HttpRequest,
        obj: GPSTrackUserPermissionProxy | None = None,
    ) -> tuple[str, ...]:
        fields = tuple(super().get_readonly_fields(request, obj))
        return (*fields, "user", "gps_track") if obj is not None else fields

    def has_delete_permission(
        self,
        request: HttpRequest,
        obj: GPSTrackUserPermissionProxy | None = None,
    ) -> bool:
        return False
