# -*- coding: utf-8 -*-

"""Admin module for Django."""

from __future__ import annotations

from django.contrib import admin

from speleodb.gis.models import SurfaceMonitoringNetworkUserPermission

# ruff: noqa: SLF001


class SurfaceMonitoringNetworkUserPermissionProxy(
    SurfaceMonitoringNetworkUserPermission
):
    class Meta:
        proxy = True
        app_label = "permissions"
        verbose_name = SurfaceMonitoringNetworkUserPermission._meta.verbose_name  # type: ignore[assignment]
        verbose_name_plural = (
            SurfaceMonitoringNetworkUserPermission._meta.verbose_name_plural  # type: ignore[assignment]
        )


@admin.register(SurfaceMonitoringNetworkUserPermissionProxy)
class SurfaceMonitoringNetworkUserPermissionAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = (
        "network",
        "user",
        "level",
        "creation_date",
        "modified_date",
        "is_active",
    )
    ordering = ("network",)
    list_filter = ["is_active", "level"]
