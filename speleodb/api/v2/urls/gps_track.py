# -*- coding: utf-8 -*-

from __future__ import annotations

from django.urls import URLPattern
from django.urls import URLResolver
from django.urls import path

from speleodb.api.v2.views.gps_track import GPSTrackPermissionAPIView
from speleodb.api.v2.views.gps_track import GPSTrackSpecificAPIView
from speleodb.api.v2.views.gps_track import UserGPSTracks
from speleodb.api.v2.views.gps_track_export import GPSTrackExportGPXAPIView

urlpatterns: list[URLPattern | URLResolver] = [
    path("", UserGPSTracks.as_view(), name="gps-tracks"),
    path(
        "<uuid:id>/permissions/",
        GPSTrackPermissionAPIView.as_view(),
        name="gps-track-permissions",
    ),
    path(
        "<uuid:id>/export/gpx/",
        GPSTrackExportGPXAPIView.as_view(),
        name="gps-track-export-gpx",
    ),
    path("<uuid:id>/", GPSTrackSpecificAPIView.as_view(), name="gps-track-detail"),
]
