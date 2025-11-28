# -*- coding: utf-8 -*-

"""Admin module for Django."""

from __future__ import annotations

from django.contrib import admin
from django.utils.html import format_html

from speleodb.gis.models import StationTag


@admin.register(StationTag)
class StationTagAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = (
        "name",
        "color_preview",
        "user",
        "station_count",
        "creation_date",
        "modified_date",
    )
    ordering = ("user", "name")
    list_filter = ["user", "creation_date"]
    search_fields = ["name", "color", "user__email"]
    readonly_fields = (
        "id",
        "creation_date",
        "modified_date",
        "station_count",
        "color_preview",
    )

    fieldsets = (
        ("Tag Information", {"fields": ("name", "color", "color_preview", "user")}),
        (
            "Metadata",
            {
                "fields": (
                    "id",
                    "creation_date",
                    "modified_date",
                    "station_count",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    @admin.display(description="Color")
    def color_preview(self, obj: StationTag) -> str:
        """Display a color preview swatch."""
        if obj and obj.color:
            return format_html(
                '<div style="display: inline-flex; align-items: center; gap: 8px;">'
                '<span style="display: inline-block; width: 24px; height: 24px; '
                'background-color: {}; border: 1px solid #ccc; border-radius: 4px;">'
                '</span><code style="font-family: monospace;">{}</code>'
                "</div>",
                obj.color,
                obj.color,
            )
        return "-"

    @admin.display(description="Stations")
    def station_count(self, obj: StationTag) -> int:
        """Display the number of stations with this tag."""
        return obj.stations.count()
