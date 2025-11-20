# -*- coding: utf-8 -*-

from __future__ import annotations

from django.urls import URLPattern
from django.urls import URLResolver
from django.urls import include
from django.urls import path

from speleodb.api.v1.views.gis_view import GISViewDataApiView

app_name = "gis"

gis_views_urlpatterns: list[URLPattern | URLResolver] = [
    path("", GISViewDataApiView.as_view(), name="gis-view-data"),
]


urlpatterns: list[URLPattern | URLResolver] = [
    # GIS View Specific URLs
    path("<uuid:id>/", include(gis_views_urlpatterns)),
]
