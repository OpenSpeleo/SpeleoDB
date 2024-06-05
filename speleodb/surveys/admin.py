#!/usr/bin/env python
# -*- coding: utf-8 -*-

# """Admin module for Django."""
from django.contrib import admin

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
