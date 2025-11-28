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

from speleodb.gis.models import Experiment
from speleodb.gis.models import ExperimentRecord

if TYPE_CHECKING:
    from django.http import HttpRequest


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
            return format_html(
                "{}",
                '<em style="color: var(--body-quiet-color);">No fields defined</em>',
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
            '">{}</pre>'
        )

        return format_html(html, formatted_json)

    @admin.display(description="GIS Token")
    def gis_token_with_refresh(self, obj: Experiment) -> str:
        """Display GIS token with a refresh button."""
        if not obj.pk:
            return format_html(
                "{}",
                '<em style="color: var(--body-quiet-color);">Save the experiment first '
                "to generate a token</em>",
            )

        token_html = (
            '<div style="display: flex; align-items: center; gap: 10px;">'  # noqa: S105
            '<code style="background: var(--darkened-bg); '
            "color: var(--body-fg); padding: 6px 12px; border-radius: 4px; "
            "font-family: monospace; font-size: 0.9rem; "
            'border: 1px solid var(--border-color);">{}</code>'
            '<input type="submit" value="Refresh Token" name="_refresh_token" '
            'style="padding: 6px 12px; background: #417690; color: white; '
            'border: none; border-radius: 4px; cursor: pointer; font-size: 0.875rem;">'
            "</div>"
        )
        return format_html(token_html, obj.gis_token)

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
