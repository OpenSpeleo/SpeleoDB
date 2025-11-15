# -*- coding: utf-8 -*-

from __future__ import annotations

import contextlib

from django.apps import AppConfig


class GISConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "speleodb.gis"
    verbose_name = "GIS"

    def ready(self) -> None:
        with contextlib.suppress(ImportError):
            import speleodb.gis.signals  # type: ignore  # noqa: F401, PGH003, PLC0415
