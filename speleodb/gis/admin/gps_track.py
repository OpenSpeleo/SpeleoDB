# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import TYPE_CHECKING

from django.contrib import admin
from django.core.exceptions import ValidationError
from django.utils.html import format_html

from speleodb.gis.models import GPSTrack

if TYPE_CHECKING:
    from django.http import HttpRequest


@admin.register(GPSTrack)
class GPSTrackAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    """
    Admin interface for GPSTrack.

    GPSTrack objects are immutable:
    - No updates allowed
    - No file replacement
    """

    # ─────────────────────────────────────────────
    # List view
    # ─────────────────────────────────────────────
    list_display = (
        "id",
        "name",
        "user",
        "short_sha256",
        "creation_date",
        "download_link",
    )

    list_select_related = ("user",)
    list_filter = ("user", "creation_date")
    search_fields = ("name", "sha256_hash", "user__name")
    ordering = ("-creation_date",)

    # ─────────────────────────────────────────────
    # Detail view
    # ─────────────────────────────────────────────
    readonly_fields = (
        "id",
        "sha256_hash",
        "creation_date",
        "modified_date",
        "signed_download_url",
    )

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "id",
                    "name",
                    "user",
                )
            },
        ),
        (
            "GeoJSON File",
            {
                "fields": (
                    "file",
                    "sha256_hash",
                    "signed_download_url",
                )
            },
        ),
        (
            "Timestamps",
            {
                "fields": (
                    "creation_date",
                    "modified_date",
                )
            },
        ),
    )

    # ─────────────────────────────────────────────
    # Permissions (immutability enforcement)
    # ─────────────────────────────────────────────
    def has_change_permission(
        self,
        request: HttpRequest,
        obj: GPSTrack | None = None,
    ) -> bool:
        # Allow viewing but not editing existing objects
        if obj is not None:
            return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(
        self,
        request: HttpRequest,
        obj: GPSTrack | None = None,
    ) -> bool:
        # Optional: allow deletion (set to False to fully lock down)
        return True

    # ─────────────────────────────────────────────
    # Custom display helpers
    # ─────────────────────────────────────────────
    @admin.display(description="SHA256")
    def short_sha256(self, obj: GPSTrack) -> str:
        return f"{obj.sha256_hash[:12]}…"

    @admin.display(description="Download")
    def download_link(self, obj: GPSTrack) -> str:
        try:
            url = obj.get_signed_download_url()
            return format_html(
                '<a href="{}" target="_blank">Download</a>',
                url,
            )
        except ValidationError:
            return "—"

    @admin.display(description="Signed download URL")
    def signed_download_url(self, obj: GPSTrack) -> str:
        try:
            return obj.get_signed_download_url()
        except ValidationError:
            return "Unavailable"
