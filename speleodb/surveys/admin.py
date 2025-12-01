# -*- coding: utf-8 -*-

"""Admin module for Django."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from typing import Any

from django import forms
from django.contrib import admin
from django.db.models import F
from django.db.models import QuerySet
from django.http import HttpRequest
from django.utils.html import format_html

from speleodb.common.enums import PermissionLevel
from speleodb.surveys.models import Format
from speleodb.surveys.models import Project
from speleodb.surveys.models import ProjectCommit
from speleodb.surveys.models import ProjectMutex
from speleodb.utils.admin_filters import ProjectCountryFilter

if TYPE_CHECKING:
    from django import forms
    from django.http import HttpRequest
    from django.utils.safestring import SafeString


@admin.register(Format)
class FormatAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("project", "format", "creation_date")
    ordering = ("-creation_date",)
    list_filter = ["_format"]

    def has_change_permission(
        self, request: HttpRequest, obj: Format | None = None
    ) -> bool:
        return True

    def save_model(
        self,
        request: HttpRequest,
        obj: Format,
        form: forms.ModelForm[Format],
        change: bool,
    ) -> None:
        obj.save(_from_admin=True)


@admin.register(ProjectMutex)
class MutexAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = (
        "project",
        "user",
        "is_active",
        "creation_date",
        "modified_date",
        "closing_user",
        "closing_comment",
    )
    ordering = (
        "-is_active",
        "-modified_date",
    )
    list_filter = ["is_active"]

    def get_queryset(self, request: HttpRequest) -> QuerySet[Any, Any]:
        # Annotate the queryset with project name for sorting
        qs = super().get_queryset(request)
        return qs.annotate(project_name=F("project__name"))  # type: ignore[no-any-return]


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = (
        "name",
        "country",
        "type",
        "created_by",
        "is_active",
        "admin_count",
        "creation_date",
        "modified_date",
        "fork_from",
        "latitude",
        "longitude",
        "short_description",
    )
    ordering = ("name",)
    readonly_fields = ("created_by", "creation_date", "modified_date")

    list_filter = [ProjectCountryFilter, "type", "created_by", "is_active"]

    @admin.display(description="Description")
    def short_description(self, obj: Project) -> str:
        # Truncate the text, e.g., to 50 characters
        if desc := obj.description:
            if len(desc) > 50:  # noqa: PLR2004
                return f"{desc[:50]} ..."
            return desc

        return ""

    @admin.display(description="Admins")
    def admin_count(self, obj: Project) -> int:
        """Display the number of data collection fields defined."""
        return obj.rel_user_permissions.filter(
            level=PermissionLevel.ADMIN,
            is_active=True,
        ).count()

    def save_model(
        self,
        request: HttpRequest,
        obj: Project,
        form: forms.ModelForm[Project],
        change: bool,
    ) -> None:
        # Auto-populate created_by field when creating a new project
        if not change:  # Only on creation, not on edit
            obj.created_by = request.user.email  # type: ignore[union-attr]
        super().save_model(request, obj, form, change)


@admin.register(ProjectCommit)
class ProjectCommitAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("oid", "project", "author_name", "author_email", "datetime")
    search_fields = ("oid", "author_name", "author_email", "message")
    list_filter = ("project",)
    ordering = ("-datetime",)

    fields = (
        "oid",
        "project",
        "author_name",
        "author_email",
        "datetime",
        "message",
        "pretty_tree",
    )

    # Prevent edits
    def has_change_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False

    @admin.display(description="Tree")
    def pretty_tree(self, obj: ProjectCommit) -> SafeString:
        """Return indented JSON in a <pre> tag."""
        formatted = json.dumps(obj.tree, indent=2, sort_keys=True)

        return format_html("<pre>{}</pre>", formatted)
