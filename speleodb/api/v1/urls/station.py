# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import TYPE_CHECKING

from django.urls import include
from django.urls import path

from speleodb.api.v1.views.log_entry import LogEntryApiView
from speleodb.api.v1.views.resource import StationResourceApiView
from speleodb.api.v1.views.station import StationsApiView
from speleodb.api.v1.views.station import StationsGeoJSONApiView
from speleodb.api.v1.views.station import StationSpecificApiView

if TYPE_CHECKING:
    from django.urls import URLPattern
    from django.urls import URLResolver


station_urlpatterns: list[URLPattern | URLResolver] = [
    path("", StationsApiView.as_view(), name="stations"),
    path("geojson/", StationsGeoJSONApiView.as_view(), name="stations-geojson"),
    path(
        "<uuid:id>/",
        include(
            [
                path("", StationSpecificApiView.as_view(), name="station-detail"),
                path(
                    "resources/",
                    StationResourceApiView.as_view(),
                    name="station-resources",
                ),
                path("logs/", LogEntryApiView.as_view(), name="station-logs"),
            ]
        ),
    ),
]
