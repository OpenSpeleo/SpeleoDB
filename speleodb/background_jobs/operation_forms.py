"""Server-side validation for superuser operation requests."""

from __future__ import annotations

from typing import Any
from typing import cast
from uuid import UUID

from django import forms
from django.contrib import admin
from django.contrib.admin.widgets import AutocompleteSelect

from speleodb.surveys.models import Project
from speleodb.surveys.models import ProjectCommit


class ProjectAutocompleteSelect(AutocompleteSelect):
    def format_value(self, value: Any) -> list[str]:
        # Django's autocomplete queries selected values while rendering even an
        # invalid bound form. Keep malformed IDs out of that UUID-field lookup;
        # the field still validates the original POST and shows its inline error.
        selected = []
        for candidate in super().format_value(value):
            try:
                selected.append(str(UUID(candidate)))
            except ValueError, TypeError, AttributeError:
                continue
        return selected


class ProjectChoiceField(forms.ModelChoiceField):  # type: ignore[type-arg]
    def label_from_instance(self, obj: Project) -> str:
        return f"{obj.name} ({obj.pk})"


class ProjectOperationForm(forms.Form):
    project_id = ProjectChoiceField(
        label="Project",
        queryset=Project.objects.all(),
        widget=ProjectAutocompleteSelect(
            ProjectCommit._meta.get_field("project"),  # noqa: SLF001 - Django field metadata API.
            admin.site,
            attrs={"data-placeholder": "Search by project name or UUID"},
        ),
        help_text="Type a project name or UUID to search, then select a project.",
    )

    def clean_project_id(self) -> Project:
        return cast("Project", self.cleaned_data["project_id"])


class ProjectGeoJSONForm(ProjectOperationForm):
    force = forms.BooleanField(
        label="Force recompute",
        required=False,
        initial=False,
        help_text=(
            "Generate missing GeoJSONs. "
            "Enabling force also replaces existing artifacts."
        ),
    )

    def clean_project_id(self) -> Project:
        project = super().clean_project_id()
        if project.exclude_geojson or not project.supports_geojson:
            raise forms.ValidationError(
                "This project is excluded from GeoJSON generation "
                "or uses an unsupported format."
            )
        return project


class AllGeoJSONForm(forms.Form):
    force = forms.BooleanField(
        label="Force recompute",
        required=False,
        initial=False,
        help_text=(
            "Generate missing GeoJSONs. "
            "Enabling force also replaces existing artifacts."
        ),
    )
