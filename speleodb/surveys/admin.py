#!/usr/bin/env python
# -*- coding: utf-8 -*-

# """Admin module for Django."""
from django.contrib import admin
from django.db.models import F

from speleodb.surveys.models import Format
from speleodb.surveys.models import Mutex
from speleodb.surveys.models import Project
from speleodb.surveys.models import TeamPermission
from speleodb.surveys.models import UserPermission


@admin.register(Format)
class FormatAdmin(admin.ModelAdmin):
    list_display = ("project", "format", "creation_date")
    ordering = ("-creation_date",)
    list_filter = ["project"]

    def has_change_permission(self, request, obj=None) -> bool:
        return False


@admin.register(Mutex)
class MutexAdmin(admin.ModelAdmin):
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

    def get_queryset(self, request):
        # Annotate the queryset with project name for sorting
        qs = super().get_queryset(request)
        return qs.annotate(project_name=F("project__name"))

    @admin.display(ordering="project_name")
    def project_name(self, obj) -> str:
        return obj.project.name


@admin.register(TeamPermission)
@admin.register(UserPermission)
class PermissionAdmin(admin.ModelAdmin):
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
class ProjectAdmin(admin.ModelAdmin):
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
