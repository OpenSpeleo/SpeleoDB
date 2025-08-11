# -*- coding: utf-8 -*-

"""Admin module for Django."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING
from typing import Any

from django import forms
from django.contrib import admin
from django.contrib import messages
from django.db import models
from django.db.models import F
from django.db.models import QuerySet
from django.utils.html import format_html

from speleodb.surveys.models import Format
from speleodb.surveys.models import Mutex
from speleodb.surveys.models import PluginRelease
from speleodb.surveys.models import PointOfInterest
from speleodb.surveys.models import Project
from speleodb.surveys.models import PublicAnnoucement
from speleodb.surveys.models import Station
from speleodb.surveys.models import StationResource
from speleodb.surveys.models import TeamPermission
from speleodb.surveys.models import UserPermission
from speleodb.utils.admin_filters import ProjectCountryFilter
from speleodb.utils.admin_filters import StationProjectFilter

if TYPE_CHECKING:
    from django.http import HttpRequest


@admin.register(Format)
class FormatAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("project", "format", "creation_date")
    ordering = ("-creation_date",)
    list_filter = ["project"]

    def has_change_permission(
        self, request: HttpRequest, obj: Format | None = None
    ) -> bool:
        return True

    def save_model(
        self,
        request: HttpRequest,
        obj: Format,
        form: forms.ModelForm[Format],
        change: bool,
    ) -> None:
        obj.save(_from_admin=True)


@admin.register(Mutex)
class MutexAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = (
        "project",
        "user",
        "is_active",
        "creation_date",
        "modified_date",
        "closing_user",
        "closing_comment",
    )
    ordering = (
        "-is_active",
        "-modified_date",
    )
    list_filter = ["is_active"]

    def get_queryset(self, request: HttpRequest) -> QuerySet[Any, Any]:
        # Annotate the queryset with project name for sorting
        qs = super().get_queryset(request)
        return qs.annotate(project_name=F("project__name"))  # type: ignore[no-any-return]


@admin.register(TeamPermission)
@admin.register(UserPermission)
class PermissionAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = (
        "project",
        "target",
        "level",
        "creation_date",
        "modified_date",
        "is_active",
    )
    ordering = ("project",)
    list_filter = ["is_active", "level"]


@admin.register(PointOfInterest)
class PointOfInterestAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = (
        "name",
        "description_preview",
        "latitude",
        "longitude",
        "created_by",
        "creation_date",
        "modified_date",
    )
    ordering = ("name",)
    list_filter = ["creation_date", "modified_date"]
    search_fields = ["name", "description"]
    readonly_fields = ("id", "creation_date", "modified_date", "coordinates")

    fieldsets = (
        ("Basic Information", {"fields": ("name", "description")}),
        (
            "Location",
            {
                "fields": ("latitude", "longitude", "coordinates"),
                "description": "GPS coordinates for the Point of Interest",
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

    @admin.display(description="Description")
    def description_preview(self, obj: PointOfInterest) -> str:
        """Show a preview of the description in the list view."""
        if obj.description:
            return (
                obj.description[:50] + "..."
                if len(obj.description) > 50  # noqa: PLR2004
                else obj.description
            )
        return "-"

    @admin.display(description="Coordinates (Lat, Lon)")
    def coordinates(self, obj: PointOfInterest) -> str:
        """Display coordinates in a readable format."""
        if obj.coordinates:
            return f"{obj.coordinates[1]:.7f}, {obj.coordinates[0]:.7f}"
        return "-"


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = (
        "name",
        "short_description",
        "creation_date",
        "modified_date",
        "country",
        "latitude",
        "longitude",
        "fork_from",
        "created_by",
    )
    ordering = ("name",)

    list_filter = [ProjectCountryFilter]

    @admin.display(description="Description")
    def short_description(self, obj: Project) -> str:
        # Truncate the text, e.g., to 50 characters
        if desc := obj.description:
            if len(desc) > 50:  # noqa: PLR2004
                return f"{desc[:50]} ..."
            return desc

        return ""


@admin.register(PublicAnnoucement)
class PublicAnnouncementAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = (
        "id",
        "title",
        "is_active",
        "software",
        "version",
        "creation_date",
        "modified_date",
        "expiracy_date",
    )

    ordering = ("-creation_date",)
    list_filter = ["is_active", "software", "version"]

    formfield_overrides = {
        models.TextField: {
            "widget": forms.Textarea(
                attrs={"cols": 100, "rows": 20, "style": "font-family: monospace;"}
            )
        },
    }

    def get_form(  # type: ignore[override]
        self,
        request: HttpRequest,
        obj: PublicAnnoucement | None = None,
        **kwargs: Any,
    ) -> type[forms.ModelForm[PublicAnnoucement]]:
        form = super().get_form(request, obj, **kwargs)

        # Disable UUID field and add regenerate button help_text
        form.base_fields["uuid"].disabled = True
        form.base_fields["uuid"].widget.attrs.update(
            {
                "style": "width: 28rem; font-family: monospace; font-size: 0.9rem;",
            }
        )
        form.base_fields["uuid"].help_text = format_html(
            '<input type="submit" value="Regenerate UUID" name="_regenerate_uuid">'
        )
        return form


@admin.register(PluginRelease)
class PluginReleaseAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = (
        "id",
        "plugin_version",
        "software",
        "min_software_version",
        "max_software_version",
        "operating_system",
        "creation_date",
        "modified_date",
    )

    ordering = ("-creation_date",)
    list_filter = ["software", "operating_system", "plugin_version"]

    formfield_overrides = {
        models.TextField: {
            "widget": forms.Textarea(
                attrs={"cols": 100, "rows": 20, "style": "font-family: monospace;"}
            )
        },
    }

    def get_form(  # type: ignore[override]
        self,
        request: HttpRequest,
        obj: PluginRelease | None = None,
        **kwargs: Any,
    ) -> type[forms.ModelForm[PluginRelease]]:
        form = super().get_form(request, obj, **kwargs)

        form.base_fields["sha256_hash"].widget.attrs.update(
            {
                "style": "width: 36rem; font-family: monospace; font-size: 0.9rem;",
            }
        )

        form.base_fields["download_url"].widget.attrs.update(
            {
                "style": "width: 80rem; font-family: monospace; font-size: 0.9rem;",
            }
        )

        return form


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


@admin.register(Station)
class StationAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = (
        "name",
        "project",
        "latitude",
        "longitude",
        "created_by",
        "creation_date",
        "modified_date",
        "resource_count",
    )
    ordering = ("project", "name")
    list_filter = [StationProjectFilter, "creation_date"]
    search_fields = ["name", "description", "project__name"]
    readonly_fields = ("id", "creation_date", "modified_date", "resource_count")
    inlines = [StationResourceInline]

    fieldsets = (
        ("Basic Information", {"fields": ("project", "name", "description")}),
        (
            "Location",
            {
                "fields": ("latitude", "longitude"),
                "description": "GPS coordinates for the station location",
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
        self, request: HttpRequest, obj: PublicAnnoucement, form: Any, change: Any
    ) -> None:
        if "_regenerate_uuid" in request.POST:
            obj.uuid = uuid.uuid4()
            self.message_user(
                request, "UUID has been regenerated.", level=messages.SUCCESS
            )
        super().save_model(request, obj, form, change)
