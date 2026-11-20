from __future__ import annotations

from typing import TYPE_CHECKING

from django import forms
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import UploadedFile
from import_export import resources
from import_export.admin import ImportExportModelAdmin
from import_export.tmp_storages import CacheStorage

from frontend_public.models import OrganizationSupporter
from frontend_public.models import PersonSupporter

if TYPE_CHECKING:
    from django.db.models.fields.files import ImageFieldFile
    from django.http import HttpRequest


class OrganizationSupporterForm(forms.ModelForm):  # type: ignore[type-arg]
    class Meta:
        model = OrganizationSupporter
        fields = ("name", "logo", "website", "order")

    def clean_logo(self) -> UploadedFile[bytes] | ImageFieldFile:
        logo: UploadedFile[bytes] | ImageFieldFile = self.cleaned_data["logo"]
        # Django's ImageField sets the MIME type from the verified image data.
        if isinstance(logo, UploadedFile) and logo.content_type not in {
            "image/png",
            "image/jpeg",
            "image/webp",
            "image/heic",
            "image/heif",
        }:
            raise ValidationError("Upload a PNG, JPEG, or WebP logo.")
        return logo


class PersonSupporterResource(resources.ModelResource):
    class Meta:
        model = PersonSupporter
        fields = ("id", "name", "website")
        clean_model_instances = True

    def before_import_row(self, row: dict[str, object], **kwargs: object) -> None:
        # Match the admin form's whitespace handling before model validation.
        for field in ("name", "website"):
            value = row.get(field)
            if isinstance(value, str):
                row[field] = value.strip()


@admin.register(PersonSupporter)
class PersonSupporterAdmin(ImportExportModelAdmin):
    resource_classes = [PersonSupporterResource]
    import_export_change_list_template = (
        "admin/frontend_public/personsupporter/change_list.html"
    )
    import_template_name = "admin/frontend_public/personsupporter/import.html"
    export_template_name = "admin/frontend_public/personsupporter/export.html"
    fields = ("name", "website")
    list_display = ("name", "website")
    search_fields = ("name",)

    def get_tmp_storage_class(self) -> type[CacheStorage]:
        return CacheStorage

    def has_import_permission(self, request: HttpRequest) -> bool:
        return self.has_add_permission(request) and self.has_change_permission(request)

    def has_export_permission(self, request: HttpRequest) -> bool:
        return self.has_view_permission(request)


@admin.register(OrganizationSupporter)
class OrganizationSupporterAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    form = OrganizationSupporterForm
    list_display = ("name", "website", "order")
    list_editable = ("order",)
    search_fields = ("name",)
