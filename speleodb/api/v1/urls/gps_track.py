# -*- coding: utf-8 -*-

from __future__ import annotations

from django.urls import URLPattern
from django.urls import URLResolver
from django.urls import path

from speleodb.api.v1.views.gps_track import GPSTrackSpecificAPIView
from speleodb.api.v1.views.gps_track import UserGPSTracks

urlpatterns: list[URLPattern | URLResolver] = [
    path("", UserGPSTracks.as_view(), name="gps-tracks"),
    path("<uuid:id>/", GPSTrackSpecificAPIView.as_view(), name="gps-track-detail"),
]
