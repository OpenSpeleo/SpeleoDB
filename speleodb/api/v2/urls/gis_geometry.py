from __future__ import annotations

from django.urls import URLPattern
from django.urls import path

from speleodb.api.v2.views.gis_geometry import GISGeometryCollectionAPIView
from speleodb.api.v2.views.gis_geometry import GISGeometryPermissionAPIView
from speleodb.api.v2.views.gis_geometry import GISGeometrySpecificAPIView

urlpatterns: list[URLPattern] = [
    path("", GISGeometryCollectionAPIView.as_view(), name="gis-geometry-list"),
    path(
        "<uuid:id>/permissions/",
        GISGeometryPermissionAPIView.as_view(),
        name="gis-geometry-permissions",
    ),
    path(
        "<uuid:id>/", GISGeometrySpecificAPIView.as_view(), name="gis-geometry-detail"
    ),
]
