# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import cast

from django.contrib import admin
from django.core.exceptions import ValidationError
from django.utils.html import format_html

from speleodb.common.enums import PermissionLevel
from speleodb.gis.models import GPSTrack
from speleodb.gis.models import GPSTrackUserPermission

if TYPE_CHECKING:
    from django.http import HttpRequest

    from speleodb.users.models import User


@admin.register(GPSTrack)
class GPSTrackAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    """Admin interface for the lightweight GPS Track record."""

    # ─────────────────────────────────────────────
    # List view
    # ─────────────────────────────────────────────
    list_display = (
        "id",
        "name",
        "created_by",
        "is_active",
        "creation_date",
        "download_link",
    )
    list_filter = ("is_active", "created_by", "creation_date")
    search_fields = ("name", "created_by")
    ordering = ("-creation_date",)

    # ─────────────────────────────────────────────
    # Detail view
    # ─────────────────────────────────────────────
    readonly_fields = (
        "id",
        "created_by",
        "is_active",
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
                    "created_by",
                    "is_active",
                )
            },
        ),
        (
            "GeoJSON File",
            {
                "fields": (
                    "file",
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
    def get_readonly_fields(
        self,
        request: HttpRequest,
        obj: GPSTrack | None = None,
    ) -> tuple[str, ...]:
        fields = tuple(super().get_readonly_fields(request, obj))
        return (*fields, "file") if obj is not None else fields

    def save_model(
        self,
        request: HttpRequest,
        obj: GPSTrack,
        form: object,
        change: bool,
    ) -> None:
        user = cast("User", request.user)
        if not obj.created_by:
            obj.created_by = user.email
        super().save_model(request, obj, form, change)
        if not change:
            GPSTrackUserPermission.objects.get_or_create(
                gps_track=obj,
                user=user,
                defaults={"level": PermissionLevel.ADMIN},
            )

    def has_delete_permission(
        self,
        request: HttpRequest,
        obj: GPSTrack | None = None,
    ) -> bool:
        return False

    # ─────────────────────────────────────────────
    # Custom display helpers
    # ─────────────────────────────────────────────
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
