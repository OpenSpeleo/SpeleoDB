"""JSON authoring in Django admin uses the same validation and revisions as API."""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any
from typing import cast

from django import forms
from django.contrib import admin
from django.core.exceptions import ValidationError

from speleodb.gis.geometry_services import GIS_GEOMETRY_CONFLICT_MESSAGE
from speleodb.gis.geometry_services import create_gis_geometry
from speleodb.gis.geometry_services import update_gis_geometry
from speleodb.gis.models import GISGeometry
from speleodb.utils.sanitize import sanitize_text

if TYPE_CHECKING:
    from django.http import HttpRequest

    from speleodb.users.models import User


class GISGeometryAdminForm(forms.ModelForm):  # type: ignore[type-arg]
    expected_revision = forms.IntegerField(required=False, widget=forms.HiddenInput)

    class Meta:
        model = GISGeometry
        fields = ("name", "color", "geojson")
        widgets = {"geojson": forms.Textarea(attrs={"rows": 20, "cols": 90})}

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        if not self.instance._state.adding:  # noqa: SLF001
            self.fields["expected_revision"].initial = self.instance.revision
            self.fields["expected_revision"].required = True

    def clean(self) -> dict[str, Any]:
        data: dict[str, Any] = super().clean() or {}
        if not self.instance._state.adding:  # noqa: SLF001
            # ModelAdmin keeps the POST transaction open through save_model.
            current = GISGeometry.objects.select_for_update().get(pk=self.instance.pk)
            if not current.is_active:
                raise ValidationError("This geometry has been deleted.")
            if data.get("expected_revision") != current.revision:
                raise ValidationError(GIS_GEOMETRY_CONFLICT_MESSAGE)
        return data

    def clean_name(self) -> str:
        name: str = sanitize_text(self.cleaned_data["name"]).strip()
        if not name:
            raise ValidationError("A name is required.")
        return name


@admin.register(GISGeometry)
class GISGeometryAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    form = GISGeometryAdminForm
    list_display = (
        "id",
        "name",
        "created_by",
        "geometry_type",
        "is_active",
        "modified_date",
    )
    list_filter = ("is_active", "creation_date", "modified_date")
    search_fields = ("id", "name", "created_by")
    readonly_fields = (
        "id",
        "created_by",
        "revision",
        "is_active",
        "creation_date",
        "modified_date",
    )
    ordering = ("-modified_date",)

    def has_delete_permission(
        self, request: HttpRequest, obj: GISGeometry | None = None
    ) -> bool:
        return False

    def has_change_permission(
        self, request: HttpRequest, obj: GISGeometry | None = None
    ) -> bool:
        return (obj is None or obj.is_active) and super().has_change_permission(
            request, obj
        )

    def save_model(
        self,
        request: HttpRequest,
        obj: GISGeometry,
        form: forms.ModelForm[GISGeometry],
        change: bool,
    ) -> None:
        actor: User = cast("User", request.user)
        if not change:
            create_gis_geometry(obj, actor)
            return
        updated: GISGeometry = update_gis_geometry(
            geometry_id=obj.id,
            actor=actor,
            expected_revision=form.cleaned_data["expected_revision"],
            updates={"name": obj.name, "color": obj.color, "geojson": obj.geojson},
            administrative=True,
        )
        # Django continues to use the form's instance for its log and response.
        obj.name = updated.name
        obj.color = updated.color
        obj.geojson = updated.geojson
        obj.revision = updated.revision
        obj.modified_date = updated.modified_date
