# -*- coding: utf-8 -*-

from __future__ import annotations

from django.urls import URLPattern
from django.urls import URLResolver
from django.urls import path

from speleodb.api.v1.views.gpx_import import GPXImportView
from speleodb.api.v1.views.kml_kmz_import import KML_KMZ_ImportView

urlpatterns: list[URLPattern | URLResolver] = [
    path("gpx/", GPXImportView.as_view(), name="gpx-import"),
    path("kml_kmz/", KML_KMZ_ImportView.as_view(), name="kml-kmz-import"),
]
