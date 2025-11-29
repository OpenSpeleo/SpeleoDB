# -*- coding: utf-8 -*-

"""Admin module for Django."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.contrib import admin

from speleodb.gis.models import StationLogEntry

if TYPE_CHECKING:
    from django import forms
    from django.http import HttpRequest


@admin.register(StationLogEntry)
class StationLogEntryAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = (
        "id",
        "station",
        "created_by",
        "title",
        "creation_date",
        "modified_date",
    )
    list_filter = ("station", "creation_date", "modified_date")
    search_fields = ("title", "notes", "created_by", "station__name")
    readonly_fields = ("created_by", "creation_date", "modified_date")
    ordering = ("-creation_date",)
    fieldsets = (
        (None, {"fields": ("station", "created_by", "title", "notes")}),
        ("Attachment", {"fields": ("attachment",)}),
        ("Timestamps", {"fields": ("creation_date", "modified_date")}),
    )

    def save_model(
        self,
        request: HttpRequest,
        obj: StationLogEntry,
        form: forms.ModelForm[StationLogEntry],
        change: bool,
    ) -> None:
        # Auto-populate created_by field when creating a new log entry
        if not change:  # Only on creation, not on edit
            obj.created_by = request.user.email  # type: ignore[union-attr]
        super().save_model(request, obj, form, change)
