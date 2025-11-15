# -*- coding: utf-8 -*-

from __future__ import annotations

import contextlib

from django.apps import AppConfig


class PluginsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "speleodb.plugins"
    verbose_name = "Plugins"

    def ready(self) -> None:
        with contextlib.suppress(ImportError):
            import speleodb.plugins.signals  # type: ignore  # noqa: F401, PGH003, PLC0415
