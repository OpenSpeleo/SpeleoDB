#!/usr/bin/env python
# -*- coding: utf-8 -*-

# """Admin module for Django."""
from django.contrib import admin

from speleodb.surveys.models import Format
from speleodb.surveys.models import Mutex
from speleodb.surveys.models import Permission
from speleodb.surveys.models import Project


class FormatAdmin(admin.ModelAdmin):
    list_display = ("project", "format", "creation_date")
    ordering = ("-creation_date",)
    list_filter = ["project"]

    def has_change_permission(self, request, obj=None):
        return False


admin.site.register(Format, FormatAdmin)


class MutexAdmin(admin.ModelAdmin):
    list_display = (
        "project",
        "user",
        "creation_date",
        "modified_date",
        "closing_user",
        "closing_comment",
    )
    ordering = ("-modified_date",)
    list_filter = ["closing_user"]


admin.site.register(Mutex, MutexAdmin)


class PermissionAdmin(admin.ModelAdmin):
    list_display = (
        "project",
        "user",
        "level",
        "creation_date",
        "modified_date",
        "is_active",
    )
    ordering = ("project",)
    list_filter = ["is_active"]


admin.site.register(Permission, PermissionAdmin)


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
    )
    ordering = ("name",)


admin.site.register(Project, ProjectAdmin)
