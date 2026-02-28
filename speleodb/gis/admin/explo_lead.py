from __future__ import annotations

from typing import TYPE_CHECKING

from django import forms
from django.contrib import admin

from speleodb.gis.models import ExplorationLead

if TYPE_CHECKING:
    from typing import Any

    from django.http import HttpRequest


class ExplorationLeadAdminForm(forms.ModelForm):  # type: ignore[type-arg]
    class Meta:
        model = ExplorationLead
        fields = "__all__"  # noqa: DJ007

    def clean(self) -> dict[str, Any] | None:
        if cleaned_data := super().clean():
            latitude = cleaned_data.get("latitude")
            longitude = cleaned_data.get("longitude")

            # Defensive check (model validators already cover bounds)
            if latitude is None or longitude is None:
                raise forms.ValidationError(
                    "Both latitude and longitude must be provided."
                )

        return cleaned_data


@admin.register(ExplorationLead)
class ExplorationLeadAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    form = ExplorationLeadAdminForm

    # List view
    list_display = (
        "id",
        "project",
        "latitude",
        "longitude",
        "created_by",
        "modified_date",
    )
    list_filter = ("project",)
    search_fields = (
        "id",
        "project__name",
        "created_by",
        "description",
    )
    ordering = ("-modified_date",)

    # Read-only metadata
    readonly_fields = (
        "id",
        "coordinates",
        "creation_date",
        "modified_date",
    )

    _SUPERUSER_ONLY_FIELDS: frozenset[str] = frozenset({"latitude", "longitude"})

    # Detail view layout
    fieldsets = (
        (
            "Exploration Lead",
            {
                "fields": (
                    "project",
                    "description",
                )
            },
        ),
        (
            "Coordinates",
            {
                "fields": (
                    "latitude",
                    "longitude",
                    "coordinates",
                ),
                "description": "Geographic coordinates of the exploration lead.",
            },
        ),
        (
            "Metadata",
            {
                "fields": (
                    "created_by",
                    "creation_date",
                    "modified_date",
                ),
            },
        ),
    )

    def get_list_display(self, request: HttpRequest) -> list[Any]:
        base: list[Any] = list(super().get_list_display(request))
        if not request.user.is_superuser:
            return [f for f in base if f not in self._SUPERUSER_ONLY_FIELDS]
        return base

    def get_fieldsets(  # type: ignore[override]
        self, request: HttpRequest, obj: ExplorationLead | None = None
    ) -> list[tuple[str | None, dict[str, Any]]]:
        fieldsets = list(super().get_fieldsets(request, obj))
        if request.user.is_superuser:
            return fieldsets  # type: ignore[return-value]
        return [(title, opts) for title, opts in fieldsets if title != "Coordinates"]  # type: ignore[misc]

    @admin.display(description="Coordinates (Lat, Lon)")
    def coordinates(self, obj: ExplorationLead) -> str:
        """Display coordinates in a readable format."""
        if obj.coordinates:
            return f"{obj.latitude:.7f}, {obj.longitude:.7f}"
        return "-"
