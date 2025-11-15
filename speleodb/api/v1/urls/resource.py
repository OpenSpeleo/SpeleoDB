# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import TYPE_CHECKING

from django.urls import path

from speleodb.api.v1.views.resource import StationResourceSpecificApiView

if TYPE_CHECKING:
    from django.urls import URLPattern
    from django.urls import URLResolver

urlpatterns: list[URLPattern | URLResolver] = [
    path(
        "<uuid:id>/",
        StationResourceSpecificApiView.as_view(),
        name="resource-detail",
    ),
]
