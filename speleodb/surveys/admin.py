#!/usr/bin/env python
# -*- coding: utf-8 -*-

# """Admin module for Django."""
from typing import Any

from django.contrib import admin
from django.db.models import F
from django.db.models import QuerySet
from django.http import HttpRequest

from speleodb.surveys.models import Format
from speleodb.surveys.models import Mutex
from speleodb.surveys.models import Project
from speleodb.surveys.models import TeamPermission
from speleodb.surveys.models import UserPermission


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
        return qs.annotate(project_name=F("project__name"))

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
