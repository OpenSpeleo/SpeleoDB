# -*- coding: utf-8 -*-

from __future__ import annotations

from django.urls import URLPattern
from django.urls import URLResolver
from django.urls import path

import speleodb.utils.url_converters  # noqa: F401  # Necessary to import the converters
from speleodb.api.v1.views.experiment import ExperimentGISApiView
from speleodb.api.v1.views.gis_view import OGCGISViewCollectionApiView
from speleodb.api.v1.views.gis_view import OGCGISViewCollectionItemApiView
from speleodb.api.v1.views.gis_view import OGCGISViewDataApiView
from speleodb.api.v1.views.gis_view import PublicGISViewGeoJSONApiView
from speleodb.api.v1.views.project_geojson import OGCGISUserCollectionApiView
from speleodb.api.v1.views.project_geojson import OGCGISUserCollectionItemApiView
from speleodb.api.v1.views.project_geojson import OGCGISUserProjectsApiView

app_name = "gis-ogc"

urlpatterns: list[URLPattern | URLResolver] = [
    path("experiment/<gis_token>/", ExperimentGISApiView.as_view(), name="experiment"),
    # OGC GIS - View endpoints
    path("view/<gis_token>", OGCGISViewDataApiView.as_view(), name="view-data"),
    path(
        "view/<gis_token>/geojson",
        PublicGISViewGeoJSONApiView.as_view(),
        name="view-geojson",
    ),
    path(
        "view/<gis_token>/<gitsha:commit_sha>",
        OGCGISViewCollectionApiView.as_view(),
        name="view-collection",
    ),
    path(
        "view/<gis_token>/<gitsha:commit_sha>/items",
        OGCGISViewCollectionItemApiView.as_view(),
        name="view-collection-items",
    ),
    # OGC GIS - User endpoints
    path(
        "user/<user_token:key>",
        OGCGISUserProjectsApiView.as_view(),
        name="user-data",
    ),
    path(
        "user/<user_token:key>/<gitsha:commit_sha>",
        OGCGISUserCollectionApiView.as_view(),
        name="user-collection",
    ),
    path(
        "user/<user_token:key>/<gitsha:commit_sha>/items",
        OGCGISUserCollectionItemApiView.as_view(),
        name="user-collection-items",
    ),
]
