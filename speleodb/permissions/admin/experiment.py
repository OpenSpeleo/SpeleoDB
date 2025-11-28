# -*- coding: utf-8 -*-

"""Admin module for Django."""

from __future__ import annotations

from django.contrib import admin

from speleodb.gis.models import ExperimentUserPermission

# ruff: noqa: SLF001


class ExperimentUserPermissionProxy(ExperimentUserPermission):
    class Meta:
        proxy = True
        app_label = "permissions"
        verbose_name = ExperimentUserPermission._meta.verbose_name  # type: ignore[assignment]
        verbose_name_plural = ExperimentUserPermission._meta.verbose_name_plural  # type: ignore[assignment]


@admin.register(ExperimentUserPermissionProxy)
class ExperimentUserPermissionAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = (
        "experiment",
        "user",
        "level",
        "creation_date",
        "modified_date",
        "is_active",
    )
    ordering = ("experiment",)
    list_filter = ["is_active", "level"]
