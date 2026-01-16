# -*- coding: utf-8 -*-

"""Admin module for Django."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.contrib import admin

from speleodb.surveys.models import TeamProjectPermission
from speleodb.surveys.models import UserProjectPermission

if TYPE_CHECKING:
    from django import forms
    from django.http import HttpRequest


# ruff: noqa: SLF001


class UserProjectPermissionProxy(UserProjectPermission):
    class Meta:
        proxy = True
        app_label = "permissions"
        verbose_name = UserProjectPermission._meta.verbose_name  # type: ignore[assignment]
        verbose_name_plural = UserProjectPermission._meta.verbose_name_plural  # type: ignore[assignment]


class TeamProjectPermissionProxy(TeamProjectPermission):
    class Meta:
        proxy = True
        app_label = "permissions"
        verbose_name = TeamProjectPermission._meta.verbose_name  # type: ignore[assignment]
        verbose_name_plural = TeamProjectPermission._meta.verbose_name_plural  # type: ignore[assignment]


@admin.register(TeamProjectPermissionProxy)
@admin.register(UserProjectPermissionProxy)
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
    list_filter = ["is_active", "level"]

    def save_model(
        self,
        request: HttpRequest,
        obj: TeamProjectPermission | UserProjectPermission,
        form: forms.ModelForm[TeamProjectPermission | UserProjectPermission],
        change: bool,
    ) -> None:
        super().save_model(request, obj, form, change)

        # Refresh the `modified_date` field
        obj.project.save()
