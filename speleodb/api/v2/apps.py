# -*- coding: utf-8 -*-

from __future__ import annotations

from importlib import import_module

from django.apps import AppConfig


class APIV1Config(AppConfig):
    name = "speleodb.api.v2"
    verbose_name = "API V1"

    def ready(self) -> None:
        import_module("speleodb.api.schema_extensions")
