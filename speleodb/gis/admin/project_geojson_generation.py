"""Inspect failures and explicitly retry committed sources, including lost requests."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.contrib import admin
from django.contrib import messages
from django.forms import ModelForm
from django.forms import ValidationError

from speleodb.common.enums import ProjectType
from speleodb.gis.geojson_generation import retry_geojson_generation
from speleodb.gis.models import ProjectGeoJSONGeneration

if TYPE_CHECKING:
    from django.db.models import QuerySet
    from django.http import HttpRequest

    from speleodb.surveys.models import ProjectCommit


class GeoJSONGenerationForm(ModelForm):  # type: ignore[type-arg]
    class Meta:
        model = ProjectGeoJSONGeneration
        fields = ("commit",)

    def clean_commit(self) -> ProjectCommit:
        commit: ProjectCommit = self.cleaned_data["commit"]
        if commit.project.exclude_geojson:
            raise ValidationError("This project is excluded from GeoJSON generation.")
        if commit.project.type not in {ProjectType.ARIANE, ProjectType.COMPASS}:
            raise ValidationError("This project type has no GeoJSON exporter.")
        return commit


@admin.register(ProjectGeoJSONGeneration)
class ProjectGeoJSONGenerationAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    form = GeoJSONGenerationForm
    list_display = (
        "commit",
        "state",
        "attempts",
        "dispatch_attempts",
        "last_error_code",
        "updated_at",
    )
    list_filter = ("state", "last_error_code")
    search_fields = ("commit__id", "commit__project__name")
    list_select_related = ("commit__project",)
    raw_id_fields = ("commit",)
    actions = ("retry_generation",)

    def get_readonly_fields(
        self, request: HttpRequest, obj: ProjectGeoJSONGeneration | None = None
    ) -> tuple[str, ...]:
        fields = tuple(field.name for field in self.model._meta.fields)  # noqa: SLF001
        return fields if obj is not None else ()

    def get_fields(
        self, request: HttpRequest, obj: ProjectGeoJSONGeneration | None = None
    ) -> tuple[str, ...]:
        if obj is None:
            return ("commit",)
        return self.get_readonly_fields(request, obj)

    def has_add_permission(self, request: HttpRequest) -> bool:
        return request.user.is_superuser

    def has_change_permission(
        self, request: HttpRequest, obj: ProjectGeoJSONGeneration | None = None
    ) -> bool:
        return request.user.is_superuser

    def has_delete_permission(
        self, request: HttpRequest, obj: ProjectGeoJSONGeneration | None = None
    ) -> bool:
        return False

    def save_model(
        self,
        request: HttpRequest,
        obj: ProjectGeoJSONGeneration,
        form: ModelForm[ProjectGeoJSONGeneration],
        change: bool,
    ) -> None:
        if change:
            return
        # The add form only selects a committed revision. Service-owned state
        # prevents an operator accidentally publishing a stale execution token.
        generation = retry_geojson_generation(obj.commit)
        obj.__dict__.update(generation.__dict__)

    @admin.action(description="Retry selected GeoJSON generations")
    def retry_generation(
        self, request: HttpRequest, queryset: QuerySet[ProjectGeoJSONGeneration]
    ) -> None:
        for generation in queryset.select_related("commit__project"):
            try:
                retry_geojson_generation(generation.commit)
            except ValueError as error:
                self.message_user(request, str(error), level=messages.WARNING)
        self.message_user(
            request,
            "Eligible revisions are pending. The dispatcher will queue them.",
        )
