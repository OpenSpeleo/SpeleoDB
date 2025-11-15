# -*- coding: utf-8 -*-

"""Admin module for Django."""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

from django import forms
from django.contrib import admin
from django.db import models
from django.utils.safestring import mark_safe

from speleodb.plugins.models import PluginRelease
from speleodb.plugins.models import PublicAnnoucement

if TYPE_CHECKING:
    from django.http import HttpRequest


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
        form.base_fields["uuid"].help_text = mark_safe(
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
