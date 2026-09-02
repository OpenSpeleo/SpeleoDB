# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import TYPE_CHECKING

from django.contrib import admin

from speleodb.gis.models import GISLayerUserPermission

if TYPE_CHECKING:
    from django.http import HttpRequest

# ruff: noqa: SLF001


class GISLayerUserPermissionProxy(GISLayerUserPermission):
    class Meta:
        proxy = True
        app_label = "permissions"
        verbose_name = str(GISLayerUserPermission._meta.verbose_name)
        verbose_name_plural = str(GISLayerUserPermission._meta.verbose_name_plural)


@admin.register(GISLayerUserPermissionProxy)
class GISLayerUserPermissionAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = (
        "user",
        "gis_layer",
        "level_label",
        "is_active",
        "creation_date",
        "modified_date",
        "deactivated_by",
    )
    list_filter = ("is_active", "level", "creation_date", "modified_date")
    search_fields = ("user__email", "user__name", "gis_layer__name")
    readonly_fields = (
        "is_active",
        "deactivated_by",
        "creation_date",
        "modified_date",
    )
    ordering = ("-modified_date",)

    def get_readonly_fields(
        self,
        request: HttpRequest,
        obj: GISLayerUserPermissionProxy | None = None,
    ) -> tuple[str, ...]:
        fields = tuple(super().get_readonly_fields(request, obj))
        return (*fields, "user", "gis_layer") if obj is not None else fields

    @admin.display(description="Level")
    def level_label(self, obj: GISLayerUserPermission) -> str:
        return str(obj.level_label)

    def has_delete_permission(
        self,
        request: HttpRequest,
        obj: GISLayerUserPermissionProxy | None = None,
    ) -> bool:
        return False
