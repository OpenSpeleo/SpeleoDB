# -*- coding: utf-8 -*-

from __future__ import annotations

from django.urls import URLPattern
from django.urls import URLResolver
from django.urls import include
from django.urls import path

from speleodb.api.v1.views.poi import PointOfInterestAPIView
from speleodb.api.v1.views.poi import PointOfInterestGeoJSONView
from speleodb.api.v1.views.poi import PointOfInterestSpecificAPIView

poi_specific_urlpatterns: list[URLPattern] = [
    path("", PointOfInterestSpecificAPIView.as_view(), name="one_poi_apiview"),
    path("geojson/", PointOfInterestGeoJSONView.as_view(), name="pois_geojson"),
]

urlpatterns: list[URLPattern | URLResolver] = [
    path("", PointOfInterestAPIView.as_view(), name="poi_api"),
    path("<uuid:id>/", include(poi_specific_urlpatterns)),
]
