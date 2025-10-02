# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import TYPE_CHECKING

from django.urls import include
from django.urls import path

from speleodb.api.v1.views.resource import StationResourceApiView
from speleodb.api.v1.views.station import StationsApiView
from speleodb.api.v1.views.station import StationSpecificApiView

if TYPE_CHECKING:
    from django.urls import URLPattern
    from django.urls import URLResolver


station_urlpatterns: list[URLPattern | URLResolver] = [
    path("", StationsApiView.as_view(), name="station_apiview"),
    path(
        "<uuid:id>/",
        include(
            [
                path("", StationSpecificApiView.as_view(), name="one_station_apiview"),
                path(
                    "resources/",
                    StationResourceApiView.as_view(),
                    name="station_resource_apiview",
                ),
            ]
        ),
    ),
]
