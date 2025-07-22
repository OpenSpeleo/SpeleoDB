# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import TYPE_CHECKING

from django.contrib import admin
from django.utils.html import format_html

from frontend_public.models import BoardMember
from frontend_public.models import ExplorerMember
from frontend_public.models import TechnicalMember

if TYPE_CHECKING:
    type AbstractPerson = BoardMember | TechnicalMember | ExplorerMember


class PersonAdminBase(admin.ModelAdmin):  # type: ignore[type-arg]
    """Base admin class for all person types."""

    list_display = [
        "photo_preview",
        "full_name",
        "title",
        "order",
        "has_link",
        "created_at",
    ]

    list_display_links = ["full_name"]

    list_editable = ["order"]

    list_filter = ["created_at", "updated_at"]

    search_fields = ["full_name", "title", "description"]

    readonly_fields = ["id", "created_at", "updated_at", "photo_preview_large"]

    fieldsets = (
        (
            None,
            {
                "fields": ("full_name", "title", "order"),
            },
        ),
        (
            "Details",
            {
                "fields": ("description",),
            },
        ),
        (
            "Link Information",
            {
                "fields": ("link_name", "link_target"),
                "classes": ("collapse",),
            },
        ),
        (
            "Photo",
            {
                "fields": ("photo", "photo_preview_large"),
            },
        ),
        (
            "Metadata",
            {
                "fields": ("id", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    @admin.display(description="Photo")
    def photo_preview(self, obj: AbstractPerson) -> str:
        """Display thumbnail in list view."""
        if obj.photo:
            return format_html(
                '<img src="{}" style="width: 50px; height: 50px; object-fit: cover; border-radius: 50%;" />',  # noqa: E501
                obj.get_photo_url(),
            )
        return "-"

    @admin.display(description="Preview")
    def photo_preview_large(self, obj: AbstractPerson) -> str:
        """Display larger preview in detail view."""
        if obj.photo:
            return format_html(
                '<img src="{}" style="max-width: 300px; max-height: 300px; object-fit: contain;" />',  # noqa: E501
                obj.get_photo_url(),
            )
        return "No photo uploaded"

    @admin.display(
        description="Has Link",
        ordering="link_target",
    )
    def has_link(self, obj: AbstractPerson) -> str:
        """Display whether person has a link."""
        return "✓" if obj.has_link else "-"


@admin.register(BoardMember)
class BoardMemberAdmin(PersonAdminBase):
    """Admin for Board of Directors members."""


@admin.register(TechnicalMember)
class TechnicalMemberAdmin(PersonAdminBase):
    """Admin for Technical Steering Committee members."""


@admin.register(ExplorerMember)
class ExplorerMemberAdmin(PersonAdminBase):
    """Admin for Explorer Advisory Board members."""
