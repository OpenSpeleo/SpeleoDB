# -*- coding: utf-8 -*-

"""Admin module for Django."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.contrib import admin

from speleodb.gis.models import StationResource

if TYPE_CHECKING:
    from django import forms
    from django.http import HttpRequest


@admin.register(StationResource)
class StationResourceAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = (
        "title",
        "station",
        "resource_type",
        "created_by",
        "creation_date",
        "has_file",
        "has_text_content",
    )
    ordering = ("station", "-modified_date")
    list_filter = ["resource_type", "creation_date", "modified_date"]
    search_fields = ["title", "description", "station__name", "text_content"]
    readonly_fields = (
        "id",
        "created_by",
        "creation_date",
        "modified_date",
        "is_file_based",
        "is_text_based",
    )

    @admin.display(
        description="Has File",
        boolean=True,
    )
    def has_file(self, obj: StationResource) -> bool:
        """Check if resource has a file attached."""
        return bool(obj.file)

    @admin.display(
        description="Has Text",
        boolean=True,
    )
    def has_text_content(self, obj: StationResource) -> bool:
        """Check if resource has text content."""
        return bool(obj.text_content)

    fieldsets = (
        (
            "Station Information",
            {"fields": ("station", "resource_type", "title", "description")},
        ),
        ("Content", {"fields": ("file", "text_content")}),
        (
            "Metadata",
            {
                "fields": (
                    "id",
                    "created_by",
                    "creation_date",
                    "modified_date",
                    "is_file_based",
                    "is_text_based",
                )
            },
        ),
    )

    def save_model(
        self,
        request: HttpRequest,
        obj: StationResource,
        form: forms.ModelForm[StationResource],
        change: bool,
    ) -> None:
        # Auto-populate created_by field when creating a new station resource
        if not change:  # Only on creation, not on edit
            obj.created_by = request.user.email  # type: ignore[union-attr]
        super().save_model(request, obj, form, change)
