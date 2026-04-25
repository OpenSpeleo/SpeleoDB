# -*- coding: utf-8 -*-

"""Admin module for Django."""

from __future__ import annotations

from django.contrib import admin

from speleodb.gis.models import LandmarkCollectionUserPermission

# ruff: noqa: SLF001


class LandmarkCollectionUserPermissionProxy(LandmarkCollectionUserPermission):
    class Meta:
        proxy = True
        app_label = "permissions"
        verbose_name = LandmarkCollectionUserPermission._meta.verbose_name  # type: ignore[assignment]
        verbose_name_plural = LandmarkCollectionUserPermission._meta.verbose_name_plural  # type: ignore[assignment]


@admin.register(LandmarkCollectionUserPermissionProxy)
class LandmarkCollectionUserPermissionAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = (
        "user",
        "collection",
        "level",
        "is_active",
        "creation_date",
        "modified_date",
    )
    ordering = ("collection__name", "user__email")
    list_filter = ["level", "is_active", "creation_date", "modified_date"]
    search_fields = ["user__email", "collection__name"]
    readonly_fields = ("id", "creation_date", "modified_date")
