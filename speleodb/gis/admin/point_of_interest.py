# -*- coding: utf-8 -*-

"""Admin module for Django."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.contrib import admin

from speleodb.gis.models import Landmark

if TYPE_CHECKING:
    from django import forms
    from django.http import HttpRequest


@admin.register(Landmark)
class LandmarkAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = (
        "name",
        "description_preview",
        "latitude",
        "longitude",
        "user",
        "creation_date",
        "modified_date",
    )
    ordering = ("name",)
    list_filter = ["creation_date", "modified_date"]
    search_fields = ["name", "description"]
    readonly_fields = ("id", "coordinates", "creation_date", "modified_date", "user")

    fieldsets = (
        ("Basic Information", {"fields": ("name", "description")}),
        (
            "Location",
            {
                "fields": ("latitude", "longitude", "coordinates"),
                "description": "GPS coordinates for the Point of Interest",
            },
        ),
        (
            "Metadata",
            {
                "fields": (
                    "id",
                    "user",
                    "creation_date",
                    "modified_date",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    @admin.display(description="Description")
    def description_preview(self, obj: Landmark) -> str:
        """Show a preview of the description in the list view."""
        if obj.description:
            return (
                obj.description[:50] + "..."
                if len(obj.description) > 50  # noqa: PLR2004
                else obj.description
            )
        return "-"

    @admin.display(description="Coordinates (Lat, Lon)")
    def coordinates(self, obj: Landmark) -> str:
        """Display coordinates in a readable format."""
        if obj.coordinates:
            return f"{obj.coordinates[1]:.7f}, {obj.coordinates[0]:.7f}"
        return "-"

    def save_model(
        self,
        request: HttpRequest,
        obj: Landmark,
        form: forms.ModelForm[Landmark],
        change: bool,
    ) -> None:
        # Auto-populate user field when creating a new point of interest
        if not change:  # Only on creation, not on edit
            obj.user = request.user  # type: ignore[assignment]
        super().save_model(request, obj, form, change)
