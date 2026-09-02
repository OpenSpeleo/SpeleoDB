# -*- coding: utf-8 -*-

from __future__ import annotations

from django.urls import URLPattern
from django.urls import URLResolver
from django.urls import path

from speleodb.api.v2.views.gis_layer import GISLayerCollectionAPIView
from speleodb.api.v2.views.gis_layer import GISLayerPermissionAPIView
from speleodb.api.v2.views.gis_layer import GISLayerSourceAPIView
from speleodb.api.v2.views.gis_layer import GISLayerSpecificAPIView

urlpatterns: list[URLPattern | URLResolver] = [
    path("", GISLayerCollectionAPIView.as_view(), name="gis-layers"),
    path(
        "<uuid:id>/permissions/",
        GISLayerPermissionAPIView.as_view(),
        name="gis-layer-permissions",
    ),
    path(
        "<uuid:id>/source/",
        GISLayerSourceAPIView.as_view(),
        name="gis-layer-source",
    ),
    path("<uuid:id>/", GISLayerSpecificAPIView.as_view(), name="gis-layer-detail"),
]
