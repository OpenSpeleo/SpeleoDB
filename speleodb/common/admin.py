# -*- coding: utf-8 -*-

from __future__ import annotations

from django.contrib import admin

from speleodb.common.models import Option


# ==================== Option ============================
@admin.register(Option)
class OptionAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("name", "value")
    ordering = ("name",)

    search_fields = ("name",)
