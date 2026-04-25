# -*- coding: utf-8 -*-

"""Admin module for Django."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.contrib import admin

from speleodb.gis.models import Landmark
from speleodb.gis.models import LandmarkCollection

if TYPE_CHECKING:
    from typing import Any

    from django import forms
    from django.http import HttpRequest


@admin.register(Landmark)
class LandmarkAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = (
        "name",
        "description_preview",
        "collection",
        "created_by",
        "creation_date",
        "modified_date",
    )
    ordering = ("name",)
    list_filter = ["collection", "creation_date", "modified_date"]
    search_fields = ["name", "description", "created_by"]
    readonly_fields = (
        "id",
        "coordinates",
        "creation_date",
        "modified_date",
        "created_by",
    )

    # For confidentiality reason - these fields should only be visible to `superusers`
    _SUPERUSER_ONLY_FIELDS: frozenset[str] = frozenset({"latitude", "longitude"})

    fieldsets = (
        ("Basic Information", {"fields": ("name", "description")}),
        ("Collection", {"fields": ("collection",)}),
        (
            "Location",
            {
                "fields": ("latitude", "longitude", "coordinates"),
                "description": "GPS coordinates for the Landmark",
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

    def get_list_display(self, request: HttpRequest) -> list[Any]:
        base: list[Any] = list(super().get_list_display(request))
        if not request.user.is_superuser:
            return base
        return [*base, *self._SUPERUSER_ONLY_FIELDS]

    def get_fieldsets(  # type: ignore[override]
        self, request: HttpRequest, obj: Landmark | None = None
    ) -> list[tuple[str | None, dict[str, Any]]]:
        fieldsets = list(super().get_fieldsets(request, obj))
        user: Any = request.user
        if user.is_superuser:
            return fieldsets  # type: ignore[return-value]
        return [(title, opts) for title, opts in fieldsets if title != "Location"]  # type: ignore[misc]

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
        if not change and not obj.created_by and request.user.is_authenticated:
            obj.created_by = request.user.email
        super().save_model(request, obj, form, change)


@admin.register(LandmarkCollection)
class LandmarkCollectionAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = (
        "name",
        "collection_type",
        "color",
        "personal_owner",
        "created_by",
        "is_active",
        "creation_date",
        "modified_date",
    )
    ordering = ("name",)
    list_filter = ["collection_type", "is_active", "creation_date", "modified_date"]
    search_fields = ["name", "description", "created_by", "personal_owner__email"]
    readonly_fields = ("id", "gis_token", "creation_date", "modified_date")
