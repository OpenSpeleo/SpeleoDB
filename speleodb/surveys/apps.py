# -*- coding: utf-8 -*-

from __future__ import annotations

from django.apps import AppConfig


class SurveysConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "speleodb.surveys"
    verbose_name = "Surveys"

    def ready(self) -> None:
        import speleodb.surveys.signals  # noqa: F401, PLC0415
