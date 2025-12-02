# -*- coding: utf-8 -*-

from __future__ import annotations

from django.urls import URLPattern
from django.urls import URLResolver
from django.urls import path

from speleodb.api.v1.views.landmark import LandmarkAPIView
from speleodb.api.v1.views.landmark import LandmarkGeoJSONView
from speleodb.api.v1.views.landmark import LandmarkSpecificAPIView

urlpatterns: list[URLPattern | URLResolver] = [
    path("", LandmarkAPIView.as_view(), name="landmarks"),
    path("geojson/", LandmarkGeoJSONView.as_view(), name="landmarks-geojson"),
    path("<uuid:id>/", LandmarkSpecificAPIView.as_view(), name="landmark-detail"),
]
