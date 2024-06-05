#!/usr/bin/env python
# -*- coding: utf-8 -*-

# """Admin module for Django."""
from django.contrib import admin

from speleodb.surveys.models import Mutex
from speleodb.surveys.models import Permission
from speleodb.surveys.models import Project

admin.site.register(Permission)


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


class MutexAdmin(admin.ModelAdmin):
    list_display = (
        "project",
        "user",
        "creation_dt",
        "heartbeat_dt",
        "closing_dt",
        "closing_user",
        "closing_comment",
    )
    ordering = ("-heartbeat_dt",)
    list_filter = ["closing_dt"]


admin.site.register(Mutex, MutexAdmin)
