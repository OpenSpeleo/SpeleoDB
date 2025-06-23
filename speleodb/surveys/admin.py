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
from django.utils.safestring import mark_safe

from speleodb.surveys.models import Format
from speleodb.surveys.models import Mutex
from speleodb.surveys.models import Project
from speleodb.surveys.models import PublicAnnoucement
from speleodb.surveys.models import TeamPermission
from speleodb.surveys.models import UserPermission

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
        return False


@admin.register(Mutex)
class MutexAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = (
        "project_name",
        "user",
        "creation_date",
        "modified_date",
        "closing_user",
        "closing_comment",
    )
    ordering = ("-modified_date",)
    list_filter = ["closing_user", "project__name"]

    def get_queryset(self, request: HttpRequest) -> QuerySet[Any, Any]:
        # Annotate the queryset with project name for sorting
        qs = super().get_queryset(request)
        return qs.annotate(project_name=F("project__name"))  # type: ignore[no-any-return]

    @admin.display(ordering="project_name")
    def project_name(self, obj: Mutex) -> str:
        return obj.project.name


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
    list_filter = ["is_active"]


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = (
        "name",
        "description",
        "creation_date",
        "modified_date",
        "country",
        "latitude",
        "longitude",
        "fork_from",
        "created_by",
    )
    ordering = ("name",)


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

    def save_model(
        self, request: HttpRequest, obj: PublicAnnoucement, form: Any, change: Any
    ) -> None:
        if "_regenerate_uuid" in request.POST:
            obj.uuid = uuid.uuid4()
            self.message_user(
                request, "UUID has been regenerated.", level=messages.SUCCESS
            )
        super().save_model(request, obj, form, change)
