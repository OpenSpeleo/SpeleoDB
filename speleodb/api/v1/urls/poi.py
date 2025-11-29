# -*- coding: utf-8 -*-

from __future__ import annotations

from django.urls import URLPattern
from django.urls import URLResolver
from django.urls import path

from speleodb.api.v1.views.poi import LandmarkAPIView
from speleodb.api.v1.views.poi import LandmarkGeoJSONView
from speleodb.api.v1.views.poi import LandmarkSpecificAPIView

urlpatterns: list[URLPattern | URLResolver] = [
    path("", LandmarkAPIView.as_view(), name="pois"),
    path("geojson/", LandmarkGeoJSONView.as_view(), name="pois-geojson"),
    path("<uuid:id>/", LandmarkSpecificAPIView.as_view(), name="poi-detail"),
]
