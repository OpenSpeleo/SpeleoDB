# -*- coding: utf-8 -*-

"""Admin module for Django."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.contrib import admin

from speleodb.gis.models import MonitoringNetwork
from speleodb.gis.models import MonitoringNetworkUserPermission

if TYPE_CHECKING:
    from django import forms
    from django.http import HttpRequest


@admin.register(MonitoringNetwork)
class MonitoringNetworkAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = (
        "name",
        "description",
        "created_by",
        "creation_date",
        "modified_date",
    )

    list_filter = (
        "created_by",
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
    )

    ordering = ("-modified_date",)

    fieldsets = (
        (
            "Basic Information",
            {
                "fields": (
                    "name",
                    "description",
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
        obj: MonitoringNetwork,
        form: forms.ModelForm[MonitoringNetwork],
        change: bool,
    ) -> None:
        # Auto-populate created_by field when creating a new experiment
        if not change:  # Only on creation, not on edit
            obj.created_by = request.user.email  # type: ignore[union-attr]
        super().save_model(request, obj, form, change)


@admin.register(MonitoringNetworkUserPermission)
class MonitoringNetworkUserPermissionAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
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
