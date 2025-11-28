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
        "commit_sha",
        "project",
        "commit_author_name",
        "commit_author_email",
        "commit_message",
        "commit_date",
        "creation_date",
        "modified_date",
    )

    readonly_fields = (
        "creation_date",
        "modified_date",
    )

    search_fields = ["commit_sha", "project__name", "commit_author_email"]

    fields = (
        "commit_sha",
        "project",
        "commit_author_name",
        "commit_author_email",
        "commit_message",
        "commit_date",
        "creation_date",
        "modified_date",
        "file",
    )

    list_filter = [GeoJSONProjectFilter, "commit_date"]

    def has_change_permission(
        self, request: HttpRequest, obj: ProjectGeoJSON | None = None
    ) -> bool:
        # Immutable: no edits after creation
        if obj is not None:
            return False
        return super().has_change_permission(request, obj)
