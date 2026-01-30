# -*- coding: utf-8 -*-

"""Admin module for Django."""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from speleodb.gis.models import GISProjectView
from speleodb.gis.models import GISView

if TYPE_CHECKING:
    from django.http import HttpRequest


class GISProjectViewInline(admin.TabularInline):  # type: ignore[type-arg]
    """Inline admin for managing projects within a GIS view."""

    model = GISProjectView
    extra = 1

    fields = [
        "project",
        "commit_sha",
        "use_latest",
        "creation_date",
    ]

    readonly_fields = ["creation_date"]

    raw_id_fields = ["project"]


@admin.register(GISView)
class GISViewAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    """Admin interface for managing GIS Views."""

    list_display = [
        "name",
        "owner",
        "token_preview",
        "allow_precise_zoom",
        "project_count",
        "creation_date",
    ]

    list_filter = [
        "allow_precise_zoom",
        "creation_date",
        "owner",
    ]

    search_fields = [
        "name",
        "description",
        "owner__email",
        "gis_token",
    ]

    readonly_fields = [
        "id",
        "gis_token",
        "creation_date",
        "modified_date",
        "api_url_display",
    ]

    fields = [
        "name",
        "description",
        "allow_precise_zoom",
        "owner",
        "id",
        "gis_token",
        "api_url_display",
        "creation_date",
        "modified_date",
    ]

    inlines = [GISProjectViewInline]

    autocomplete_fields = ["owner"]

    def get_fields(self, request: HttpRequest, obj: GISView | None = None) -> list[str]:  # type: ignore[override]
        """Hide readonly metadata fields when creating a new view."""
        if obj is None:  # Creating new object
            # Only show editable fields
            return ["name", "description", "allow_precise_zoom", "owner"]

        # Editing existing object - show all fields
        return super().get_fields(request, obj)  # type: ignore[return-value]

    def changeform_view(
        self,
        request: HttpRequest,
        object_id: str | None = None,
        form_url: str = "",
        extra_context: dict[str, Any] | None = None,
    ) -> Any:
        """Store request for use in readonly field display methods."""
        self._current_request = request
        return super().changeform_view(request, object_id, form_url, extra_context)

    @admin.display(description="Token")
    def token_preview(self, obj: GISView) -> str:
        """Show first 8 characters of token."""
        if obj and obj.gis_token:
            return f"{obj.gis_token[:8]}..."
        return "-"

    @admin.display(description="Projects")
    def project_count(self, obj: GISView) -> int:
        """Show number of projects in view."""
        if obj and obj.pk:
            return obj.project_views.count()
        return 0

    def api_url_display(self, obj: GISView) -> str:
        """Display the public API URL for easy copying."""
        if obj and obj.pk and obj.gis_token:
            path = reverse(
                "api:v1:gis-ogc:view-data",
                kwargs={"gis_token": obj.gis_token},
            )

            # Get request from stored instance variable
            request = getattr(self, "_current_request", None)

            url = f"{request.scheme}://{request.get_host()}{path}" if request else path

            return format_html(
                '<code style="background: var(--darkened-bg); '
                "color: var(--body-fg); padding: 6px 12px; border-radius: 4px; "
                "font-family: monospace; font-size: 0.9rem; "
                'border: 1px solid var(--border-color);">{}</code>',
                url,
            )

        return format_html(
            "{}",
            '<em style="color: var(--body-quiet-color);">Save to generate URL</em>',
        )


@admin.register(GISProjectView)
class GISProjectViewAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    """Admin interface for GIS View Projects."""

    list_display = [
        "gis_view",
        "project",
        "commit_display",
        "use_latest",
        "creation_date",
    ]

    list_filter = [
        "use_latest",
        "creation_date",
    ]

    search_fields = [
        "gis_view__name",
        "project__name",
        "commit_sha",
    ]

    readonly_fields = [
        "creation_date",
        "modified_date",
    ]

    autocomplete_fields = [
        "gis_view",
    ]

    raw_id_fields = [
        "project",
    ]

    @admin.display(description="Commit")
    def commit_display(self, obj: GISProjectView) -> str:
        """Display commit info in a readable format."""
        if obj.use_latest:
            return "latest"
        return obj.commit_sha[:8] if obj.commit_sha else "N/A"
