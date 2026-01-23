# -*- coding: utf-8 -*-

"""Admin module for Django."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.contrib import admin
from django.utils.html import format_html

from speleodb.gis.models import Station
from speleodb.gis.models import StationResource
from speleodb.gis.models import SubSurfaceStation
from speleodb.gis.models import SurfaceStation
from speleodb.utils.admin_filters import StationProjectFilter

if TYPE_CHECKING:
    from django import forms
    from django.http import HttpRequest


class StationResourceInline(admin.TabularInline):  # type: ignore[type-arg]
    """Inline admin for StationResource to be displayed within Station admin."""

    model = StationResource
    extra = 0
    fields = (
        "resource_type",
        "title",
        "file",
        "created_by",
        "creation_date",
        "modified_date",
    )
    readonly_fields = ("creation_date", "modified_date", "created_by")
    ordering = ("-modified_date",)


class BaseStationAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = (
        "name",
        "latitude",
        "longitude",
        "created_by",
        "creation_date",
        "modified_date",
        "resource_count",
        "tag_display",
    )
    list_filter = [StationProjectFilter, "creation_date", "tag"]
    search_fields = ["name", "description"]
    readonly_fields = (
        "id",
        "created_by",
        "creation_date",
        "modified_date",
        "resource_count",
    )
    inlines = [StationResourceInline]

    fieldsets = (
        (
            "Location",
            {
                "fields": ("latitude", "longitude"),
                "description": "GPS coordinates for the station location",
            },
        ),
        (
            "Tag",
            {
                "fields": ("tag",),
                "description": "Assign a tag to categorize and organize this station",
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
                    "resource_count",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    @admin.display(description="Resources")
    def resource_count(self, obj: Station) -> int:
        """Display the number of resources for this station."""
        return obj.resources.count()

    @admin.display(description="Tag")
    def tag_display(self, obj: Station) -> str:
        """Display the tag assigned to this station."""
        if obj.tag:
            return format_html(
                '<span style="background-color: {}; color: white; padding: 2px 8px; '
                'border-radius: 4px; font-size: 0.875rem;">{}</span>',
                obj.tag.color,
                obj.tag.name,
            )
        return "-"

    def save_model(
        self,
        request: HttpRequest,
        obj: Station,
        form: forms.ModelForm[Station],
        change: bool,
    ) -> None:
        # Auto-populate created_by field when creating a new station
        if not change:  # Only on creation, not on edit
            obj.created_by = request.user.email  # type: ignore[union-attr]
        super().save_model(request, obj, form, change)


@admin.register(SurfaceStation)
class SurfaceStationAdmin(BaseStationAdmin):
    """Admin for SurfaceStation, inheriting from BaseStationAdmin."""

    list_display = (
        BaseStationAdmin.list_display[0],  # pyright: ignore[reportGeneralTypeIssues]
        "network",
        *BaseStationAdmin.list_display[1:],
    )  # type: ignore[assignment]
    ordering = ("network", "name")
    search_fields = (*BaseStationAdmin.search_fields, "network__name")  # type: ignore[assignment]
    fieldsets = (
        ("Basic Information", {"fields": ("network", "name", "description")}),
        *BaseStationAdmin.fieldsets,  # pyright: ignore[reportOptionalIterable]
    )  # type: ignore[assignment]


@admin.register(SubSurfaceStation)
class SubSurfaceStationAdmin(BaseStationAdmin):
    """Admin for SubSurfaceStation, inheriting from BaseStationAdmin."""

    list_display = (
        BaseStationAdmin.list_display[0],  # pyright: ignore[reportGeneralTypeIssues]
        "project",
        "type",
        *BaseStationAdmin.list_display[1:],
    )  # type: ignore[assignment]
    list_filter = ["type", *BaseStationAdmin.list_filter]
    ordering = ("project", "name")
    search_fields = (*BaseStationAdmin.search_fields, "project__name")  # type: ignore[assignment]

    fieldsets = (
        ("Basic Information", {"fields": ("project", "type", "name", "description")}),
        *BaseStationAdmin.fieldsets,  # pyright: ignore[reportOptionalIterable]
    )  # type: ignore[assignment]
