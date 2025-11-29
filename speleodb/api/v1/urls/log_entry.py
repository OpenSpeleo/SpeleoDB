# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import TYPE_CHECKING

from django.urls import path

from speleodb.api.v1.views.log_entry import StationLogEntrySpecificApiView

if TYPE_CHECKING:
    from django.urls import URLPattern
    from django.urls import URLResolver

urlpatterns: list[URLPattern | URLResolver] = [
    path("<uuid:id>/", StationLogEntrySpecificApiView.as_view(), name="log-detail"),
]
