# -*- coding: utf-8 -*-

"""Admin module for Django."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.contrib import admin

from speleodb.gis.models import ProjectGeoJSON
from speleodb.utils.admin_filters import GeoJSONProjectFilter

if TYPE_CHECKING:
    from django.http import HttpRequest


@admin.register(ProjectGeoJSON)
class ProjectGeoJSONAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = (
        "commit__id",
        "project",
        "commit__authored_date",
        "commit__author_name",
        "commit__author_email",
        "commit__message",
        "creation_date",
        "modified_date",
    )

    readonly_fields = (
        "commit",
        "creation_date",
        "modified_date",
    )

    search_fields = [
        "commit__id",
        "project__name",
        "commit__authored_date",
    ]

    fields = (
        "commit",
        "project",
        "file",
        "creation_date",
        "modified_date",
    )

    list_filter = [GeoJSONProjectFilter, "commit__authored_date"]

    @admin.display(description="File (S3 path)")
    def file_path(self, obj: ProjectGeoJSON) -> str:
        return obj.file.name if obj.file else "-"

    def get_fields(
        self, request: HttpRequest, obj: ProjectGeoJSON | None = None
    ) -> tuple[str, ...]:
        fields = self.fields
        assert fields is not None
        if not request.user.is_superuser:  # type: ignore[union-attr]
            return tuple("file_path" if f == "file" else f for f in fields)
        return fields

    def get_readonly_fields(
        self, request: HttpRequest, obj: ProjectGeoJSON | None = None
    ) -> tuple[str, ...]:
        base = self.readonly_fields
        assert base is not None
        if not request.user.is_superuser:  # type: ignore[union-attr]
            return (*base, "file_path")
        return base

    def has_change_permission(
        self, request: HttpRequest, obj: ProjectGeoJSON | None = None
    ) -> bool:
        # Immutable: no edits after creation
        if obj is not None:
            return False
        return super().has_change_permission(request, obj)
