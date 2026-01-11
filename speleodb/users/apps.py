# -*- coding: utf-8 -*-

from __future__ import annotations

from django.apps import AppConfig


class UsersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "speleodb.users"
    verbose_name = "Users"

    def ready(self) -> None:
        import speleodb.users.signals  # noqa: F401, PLC0415
