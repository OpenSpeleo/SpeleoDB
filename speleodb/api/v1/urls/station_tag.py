# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import TYPE_CHECKING

from django.urls import path

from speleodb.api.v1.views.station_tag import StationTagColorsApiView
from speleodb.api.v1.views.station_tag import StationTagsApiView
from speleodb.api.v1.views.station_tag import StationTagSpecificApiView

if TYPE_CHECKING:
    from django.urls import URLPattern

urlpatterns: list[URLPattern] = [
    path("", StationTagsApiView.as_view(), name="station-tags"),
    path("colors/", StationTagColorsApiView.as_view(), name="station-tag-colors"),
    path("<uuid:id>/", StationTagSpecificApiView.as_view(), name="station-tag-detail"),
]
