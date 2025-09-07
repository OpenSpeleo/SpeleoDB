# -*- coding: utf-8 -*-

from __future__ import annotations

from django.urls import URLPattern
from django.urls import URLResolver
from django.urls import path

from speleodb.api.v1.views.poi import PointOfInterestAPIView
from speleodb.api.v1.views.poi import PointOfInterestGeoJSONView
from speleodb.api.v1.views.poi import PointOfInterestSpecificAPIView

urlpatterns: list[URLPattern | URLResolver] = [
    path("", PointOfInterestAPIView.as_view(), name="pois"),
    path("geojson/", PointOfInterestGeoJSONView.as_view(), name="pois-geojson"),
    path("<uuid:id>/", PointOfInterestSpecificAPIView.as_view(), name="poi-detail"),
]
