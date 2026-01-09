from typing import TYPE_CHECKING

from django import forms
from django.contrib import admin

from speleodb.gis.models import ExplorationLead

if TYPE_CHECKING:
    from typing import Any


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
        "creation_date",
        "modified_date",
    )

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
