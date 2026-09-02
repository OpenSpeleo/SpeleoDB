# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import TYPE_CHECKING

from django.contrib import admin
from django.core.exceptions import ValidationError
from django.utils.html import format_html

from speleodb.gis.models import GISLayer

if TYPE_CHECKING:
    from django.http import HttpRequest


@admin.register(GISLayer)
class GISLayerAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = (
        "id",
        "name",
        "created_by",
        "source_format",
        "is_active",
        "modified_date",
        "download_link",
    )
    list_filter = ("is_active", "creation_date", "modified_date")
    search_fields = ("id", "name", "created_by")
    ordering = ("-modified_date",)
    readonly_fields = (
        "id",
        "created_by",
        "is_active",
        "creation_date",
        "modified_date",
        "signed_download_url",
        "signed_source_url",
    )

    def has_add_permission(
        self,
        request: HttpRequest,
    ) -> bool:
        # Layer creation must compile the source and publish both file fields as
        # one unit. The plain model admin cannot provide that workflow safely.
        return False

    def has_delete_permission(
        self,
        request: HttpRequest,
        obj: GISLayer | None = None,
    ) -> bool:
        return False

    @admin.display(description="Data")
    def download_link(self, obj: GISLayer) -> str:
        try:
            return format_html(
                '<a href="{}" target="_blank" rel="noopener">Download</a>',
                obj.get_signed_download_url(),
            )
        except ValidationError:
            return "—"

    @admin.display(description="Signed data URL")
    def signed_download_url(self, obj: GISLayer) -> str:
        try:
            return obj.get_signed_download_url()
        except ValidationError:
            return "Unavailable"

    @admin.display(description="Signed source URL")
    def signed_source_url(self, obj: GISLayer) -> str:
        try:
            return obj.get_signed_source_url()
        except ValidationError:
            return "Unavailable"
