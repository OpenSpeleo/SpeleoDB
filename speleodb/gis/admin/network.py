# -*- coding: utf-8 -*-

"""Admin module for Django."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.contrib import admin

from speleodb.gis.models import SurfaceMonitoringNetwork

if TYPE_CHECKING:
    from django import forms
    from django.http import HttpRequest


@admin.register(SurfaceMonitoringNetwork)
class SurfaceMonitoringNetworkAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = (
        "name",
        "description",
        "is_active",
        "created_by",
        "creation_date",
        "modified_date",
    )

    list_filter = (
        "is_active",
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
                ),
                "classes": ("collapse",),
            },
        ),
    )

    def save_model(
        self,
        request: HttpRequest,
        obj: SurfaceMonitoringNetwork,
        form: forms.ModelForm[SurfaceMonitoringNetwork],
        change: bool,
    ) -> None:
        # Auto-populate created_by field when creating a new experiment
        if not change:  # Only on creation, not on edit
            obj.created_by = request.user.email  # type: ignore[union-attr]
        super().save_model(request, obj, form, change)
