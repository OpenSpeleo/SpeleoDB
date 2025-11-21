# -*- coding: utf-8 -*-

"""Admin module for Django."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from typing import Any

from django import forms
from django.contrib import admin
from django.forms import CheckboxInput
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from speleodb.gis.models import Experiment
from speleodb.gis.models import ExperimentRecord
from speleodb.gis.models import ExperimentUserPermission
from speleodb.gis.models import GISView
from speleodb.gis.models import GISViewProject
from speleodb.gis.models import LogEntry
from speleodb.gis.models import PointOfInterest
from speleodb.gis.models import ProjectGeoJSON
from speleodb.gis.models import Station
from speleodb.gis.models import StationResource
from speleodb.gis.models import StationTag
from speleodb.utils.admin_filters import GeoJSONProjectFilter
from speleodb.utils.admin_filters import StationProjectFilter

if TYPE_CHECKING:
    from django.http import HttpRequest


@admin.register(PointOfInterest)
class PointOfInterestAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = (
        "name",
        "description_preview",
        "latitude",
        "longitude",
        "user",
        "creation_date",
        "modified_date",
    )
    ordering = ("name",)
    list_filter = ["creation_date", "modified_date"]
    search_fields = ["name", "description"]
    readonly_fields = ("id", "coordinates", "creation_date", "modified_date", "user")

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
                    "user",
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

    def save_model(
        self,
        request: HttpRequest,
        obj: PointOfInterest,
        form: forms.ModelForm[PointOfInterest],
        change: bool,
    ) -> None:
        # Auto-populate user field when creating a new point of interest
        if not change:  # Only on creation, not on edit
            obj.user = request.user  # type: ignore[assignment]
        super().save_model(request, obj, form, change)


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
    readonly_fields = ("created_by", "creation_date", "modified_date", "created_by")
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
        "tag_display",
    )
    ordering = ("project", "name")
    list_filter = [StationProjectFilter, "creation_date", "tag"]
    search_fields = ["name", "description", "project__name"]
    readonly_fields = (
        "id",
        "created_by",
        "creation_date",
        "modified_date",
        "resource_count",
    )
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
            "Tag",
            {
                "fields": ("tag",),
                "description": "Assign a tag to categorize and organize this station",
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

    @admin.display(description="Tag")
    def tag_display(self, obj: Station) -> str:
        """Display the tag assigned to this station."""
        if obj.tag:
            return format_html(
                '<span style="background-color: {}; color: white; padding: 2px 8px; '
                'border-radius: 4px; font-size: 0.875rem;">{}</span>',
                obj.tag.color,
                obj.tag.name,
            )
        return "-"

    def save_model(
        self,
        request: HttpRequest,
        obj: Station,
        form: forms.ModelForm[Station],
        change: bool,
    ) -> None:
        # Auto-populate created_by field when creating a new station
        if not change:  # Only on creation, not on edit
            obj.created_by = request.user.email  # type: ignore[union-attr]
        super().save_model(request, obj, form, change)


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


@admin.register(StationTag)
class StationTagAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = (
        "name",
        "color_preview",
        "user",
        "station_count",
        "creation_date",
        "modified_date",
    )
    ordering = ("user", "name")
    list_filter = ["user", "creation_date"]
    search_fields = ["name", "color", "user__email"]
    readonly_fields = (
        "id",
        "creation_date",
        "modified_date",
        "station_count",
        "color_preview",
    )

    fieldsets = (
        ("Tag Information", {"fields": ("name", "color", "color_preview", "user")}),
        (
            "Metadata",
            {
                "fields": (
                    "id",
                    "creation_date",
                    "modified_date",
                    "station_count",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    @admin.display(description="Color")
    def color_preview(self, obj: StationTag) -> str:
        """Display a color preview swatch."""
        if obj and obj.color:
            return format_html(
                '<div style="display: inline-flex; align-items: center; gap: 8px;">'
                '<span style="display: inline-block; width: 24px; height: 24px; '
                'background-color: {}; border: 1px solid #ccc; border-radius: 4px;">'
                '</span><code style="font-family: monospace;">{}</code>'
                "</div>",
                obj.color,
                obj.color,
            )
        return "-"

    @admin.display(description="Stations")
    def station_count(self, obj: StationTag) -> int:
        """Display the number of stations with this tag."""
        return obj.stations.count()


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


@admin.register(LogEntry)
class LogEntryAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = (
        "id",
        "station",
        "created_by",
        "title",
        "creation_date",
        "modified_date",
    )
    list_filter = ("station", "creation_date", "modified_date")
    search_fields = (
        "title",
        "notes",
        "created_by",
        "station__name",
        "station__project__name",
    )
    readonly_fields = ("created_by", "creation_date", "modified_date")
    ordering = ("-creation_date",)
    fieldsets = (
        (None, {"fields": ("station", "created_by", "title", "notes")}),
        ("Attachment", {"fields": ("attachment",)}),
        ("Timestamps", {"fields": ("creation_date", "modified_date")}),
    )

    def save_model(
        self,
        request: HttpRequest,
        obj: LogEntry,
        form: forms.ModelForm[LogEntry],
        change: bool,
    ) -> None:
        # Auto-populate created_by field when creating a new log entry
        if not change:  # Only on creation, not on edit
            obj.created_by = request.user.email  # type: ignore[union-attr]
        super().save_model(request, obj, form, change)


class ExperimentAdminForm(forms.ModelForm):  # type: ignore[type-arg]
    """Custom form for Experiment with enhanced field management."""

    class Meta:
        model = Experiment
        fields = [
            "name",
            "code",
            "description",
            "created_by",
            "is_active",
            "start_date",
            "end_date",
        ]
        # Note: experiment_fields is now read-only, not editable in admin
        # Use the API to modify experiment fields

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        # Reorder fields to match desired order (name first)
        desired_order = [
            "name",
            "code",
            "description",
            "created_by",
            "is_active",
            "start_date",
            "end_date",
        ]

        # Reorder fields dict
        ordered_fields = {}
        for field_name in desired_order:
            if field_name in self.fields:
                ordered_fields[field_name] = self.fields.pop(field_name)
        # Add remaining fields
        ordered_fields.update(self.fields)
        self.fields = ordered_fields

        # Ensure is_active field is present and properly configured
        if "is_active" in self.fields:
            # Boolean fields should use CheckboxInput widget

            if not isinstance(self.fields["is_active"].widget, CheckboxInput):
                self.fields["is_active"].widget = CheckboxInput()

        # Custom field labels
        custom_labels = {
            "name": "Experiment Name",
            "is_active": "Active",
        }

        # Add red asterisk to required field labels
        # Fields that shouldn't show asterisks (readonly, auto-generated,
        # or special widgets)
        skip_fields = {
            "id",
            "creation_date",
            "modified_date",
            "raw_experiment_fields_json",  # Computed field
        }

        for field_name, field in self.fields.items():
            # Skip fields that shouldn't have asterisks
            if field_name in skip_fields:
                continue

            # Set custom label if defined
            if field_name in custom_labels:
                field.label = custom_labels[field_name]

            # Add asterisk to required fields
            if field.required:
                original_label = field.label or field_name.replace("_", " ").title()
                field.label = format_html(
                    '{} <span style="color: #dc2626; font-weight: bold;">*</span>',
                    original_label,
                )


@admin.register(Experiment)
class ExperimentAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    form = ExperimentAdminForm
    list_display = (
        "name",
        "code",
        "created_by",
        "is_active",
        "start_date",
        "end_date",
        "field_count",
        "creation_date",
        "modified_date",
    )
    list_filter = ("created_by", "is_active", "creation_date", "modified_date")
    search_fields = (
        "code",
        "name",
        "created_by",
        "description",
    )
    readonly_fields = (
        "id",
        "created_by",
        "creation_date",
        "modified_date",
        "raw_experiment_fields_json",
        "gis_token_with_refresh",
    )
    ordering = ("-creation_date",)
    fieldsets = (
        (
            "Basic Information",
            {
                "fields": (
                    "name",
                    "code",
                    "description",
                    "created_by",
                    "is_active",
                    "start_date",
                    "end_date",
                )
            },
        ),
        (
            "Metadata",
            {
                "fields": (
                    "id",
                    "gis_token_with_refresh",
                    "creation_date",
                    "modified_date",
                    "raw_experiment_fields_json",
                ),
            },
        ),
    )

    @admin.display(description="Fields")
    def field_count(self, obj: Experiment) -> int:
        """Display the number of data collection fields defined."""
        if obj.experiment_fields:
            return len(obj.experiment_fields)
        return 0

    @admin.display(description="Raw JSON (Read-Only)")
    def raw_experiment_fields_json(self, obj: Experiment) -> str:
        """Display raw experiment_fields JSON in a formatted, read-only way."""
        if not obj.experiment_fields:
            return mark_safe(
                '<em style="color: var(--body-quiet-color);">No fields defined</em>'
            )

        # Format JSON with indentation
        formatted_json = json.dumps(obj.experiment_fields, indent=2, sort_keys=False)

        # Wrap in a styled pre block for proper formatting
        html = (
            '<pre style="'
            "background: var(--darkened-bg); "
            "color: var(--body-fg); "
            "padding: 12px; "
            "border: 1px solid var(--border-color); "
            "border-radius: 4px; "
            "font-family: monospace; "
            "font-size: 0.85rem; "
            "overflow-x: auto; "
            "max-height: 400px; "
            "overflow-y: auto;"
            '">'
            f"{formatted_json}"
            "</pre>"
        )

        return mark_safe(html)  # noqa: S308

    @admin.display(description="GIS Token")
    def gis_token_with_refresh(self, obj: Experiment) -> str:
        """Display GIS token with a refresh button."""
        if not obj.pk:
            return mark_safe(
                '<em style="color: var(--body-quiet-color);">Save the experiment first '
                "to generate a token</em>"
            )

        token_html = (
            '<div style="display: flex; align-items: center; gap: 10px;">'
            '<code style="background: var(--darkened-bg); '
            "color: var(--body-fg); padding: 6px 12px; border-radius: 4px; "
            "font-family: monospace; font-size: 0.9rem; "
            f'border: 1px solid var(--border-color);">{obj.gis_token}</code>'
            '<input type="submit" value="Refresh Token" name="_refresh_token" '
            'style="padding: 6px 12px; background: #417690; color: white; '
            'border: none; border-radius: 4px; cursor: pointer; font-size: 0.875rem;">'
            "</div>"
        )
        return mark_safe(token_html)  # noqa: S308

    def response_change(self, request: HttpRequest, obj: Experiment) -> Any:
        """Handle refresh token button click."""
        if "_refresh_token" in request.POST:
            obj.refresh_gis_token()
            self.message_user(
                request, "GIS token has been refreshed successfully.", level="success"
            )
            # Redirect to the change page to show the updated token
            return redirect(
                reverse(
                    "admin:gis_experiment_change",
                    args=[obj.pk],
                )
            )
        return super().response_change(request, obj)

    def save_model(
        self,
        request: HttpRequest,
        obj: Experiment,
        form: forms.ModelForm[Experiment],
        change: bool,
    ) -> None:
        # Auto-populate created_by field when creating a new experiment
        if not change:  # Only on creation, not on edit
            obj.created_by = request.user.email  # type: ignore[union-attr]
        super().save_model(request, obj, form, change)


@admin.register(ExperimentRecord)
class ExperimentRecordAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = [
        "id",
        "experiment",
        "station",
        "creation_date",
        "modified_date",
        "data",
    ]
    ordering = ("-modified_date",)
    list_filter = ["experiment", "creation_date", "modified_date"]
    search_fields = ["name", "description", "experiment"]
    readonly_fields = (
        "id",
        "experiment",
        "station",
        "creation_date",
        "modified_date",
    )

    class Meta:
        model = ExperimentRecord


@admin.register(ExperimentUserPermission)
class ExperimentUserPermissionAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = (
        "experiment",
        "user",
        "level",
        "creation_date",
        "modified_date",
        "is_active",
    )
    ordering = ("experiment",)
    list_filter = ["is_active", "level"]


# ========================== GIS VIEWS ========================== #


class GISViewProjectInline(admin.TabularInline):  # type: ignore[type-arg]
    """Inline admin for managing projects within a GIS view."""

    model = GISViewProject
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
        "project_count",
        "creation_date",
    ]

    list_filter = [
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
        "owner",
        "id",
        "gis_token",
        "api_url_display",
        "creation_date",
        "modified_date",
    ]

    inlines = [GISViewProjectInline]

    autocomplete_fields = ["owner"]

    def get_fields(self, request: HttpRequest, obj: GISView | None = None) -> list[str]:  # type: ignore[override]
        """Hide readonly metadata fields when creating a new view."""
        if obj is None:  # Creating new object
            # Only show editable fields
            return ["name", "description", "owner"]

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
            return obj.rel_view_projects.count()
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

            return mark_safe(  # noqa: S308
                f'<code style="background: var(--darkened-bg); '
                f"color: var(--body-fg); padding: 6px 12px; border-radius: 4px; "
                f"font-family: monospace; font-size: 0.9rem; "
                f'border: 1px solid var(--border-color);">{url}</code>'
            )

        return mark_safe(
            '<em style="color: var(--body-quiet-color);">Save to generate URL</em>'
        )


@admin.register(GISViewProject)
class GISViewProjectAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
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
    def commit_display(self, obj: GISViewProject) -> str:
        """Display commit info in a readable format."""
        if obj.use_latest:
            return "latest"
        return obj.commit_sha[:8] if obj.commit_sha else "N/A"
