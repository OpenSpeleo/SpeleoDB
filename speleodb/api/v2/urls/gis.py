# -*- coding: utf-8 -*-

from __future__ import annotations

from django.urls import URLPattern
from django.urls import URLResolver
from django.urls import path

import speleodb.utils.url_converters  # noqa: F401  # Necessary to import the converters
from speleodb.api.v2.views.experiment import ExperimentGISApiView
from speleodb.api.v2.views.gis_view import OGCGISViewCollectionApiView
from speleodb.api.v2.views.gis_view import OGCGISViewCollectionItemApiView
from speleodb.api.v2.views.gis_view import OGCGISViewCollectionsApiView
from speleodb.api.v2.views.gis_view import OGCGISViewConformanceApiView
from speleodb.api.v2.views.gis_view import OGCGISViewLandingPageApiView
from speleodb.api.v2.views.gis_view import PublicGISViewGeoJSONApiView
from speleodb.api.v2.views.landmark_collection_ogc import (
    LandmarkCollectionOGCCollectionApiView,
)
from speleodb.api.v2.views.landmark_collection_ogc import (
    LandmarkCollectionOGCCollectionItemsApiView,
)
from speleodb.api.v2.views.landmark_collection_ogc import (
    LandmarkCollectionOGCCollectionsApiView,
)
from speleodb.api.v2.views.landmark_collection_ogc import (
    LandmarkCollectionOGCConformanceApiView,
)
from speleodb.api.v2.views.landmark_collection_ogc import (
    LandmarkCollectionOGCLandingPageApiView,
)
from speleodb.api.v2.views.landmark_collection_ogc import (
    LandmarkCollectionUserOGCCollectionApiView,
)
from speleodb.api.v2.views.landmark_collection_ogc import (
    LandmarkCollectionUserOGCCollectionItemsApiView,
)
from speleodb.api.v2.views.landmark_collection_ogc import (
    LandmarkCollectionUserOGCCollectionsApiView,
)
from speleodb.api.v2.views.landmark_collection_ogc import (
    LandmarkCollectionUserOGCConformanceApiView,
)
from speleodb.api.v2.views.landmark_collection_ogc import (
    LandmarkCollectionUserOGCLandingPageApiView,
)
from speleodb.api.v2.views.project_geojson import OGCGISUserCollectionApiView
from speleodb.api.v2.views.project_geojson import OGCGISUserCollectionItemApiView
from speleodb.api.v2.views.project_geojson import OGCGISUserConformanceApiView
from speleodb.api.v2.views.project_geojson import OGCGISUserLandingPageApiView
from speleodb.api.v2.views.project_geojson import OGCGISUserProjectsApiView

app_name = "gis-ogc"

urlpatterns: list[URLPattern | URLResolver] = [
    path("experiment/<gis_token>/", ExperimentGISApiView.as_view(), name="experiment"),
    # ------------------------------------------------------------------
    # OGC API - Features: Landmark Collection endpoints (public token)
    # ------------------------------------------------------------------
    path(
        "landmark-collection/<gis_token>/",
        LandmarkCollectionOGCLandingPageApiView.as_view(),
        name="landmark-collection-landing",
    ),
    path(
        "landmark-collection/<gis_token>/conformance",
        LandmarkCollectionOGCConformanceApiView.as_view(),
        name="landmark-collection-conformance",
    ),
    path(
        "landmark-collection/<gis_token>/collections",
        LandmarkCollectionOGCCollectionsApiView.as_view(),
        name="landmark-collection-collections",
    ),
    path(
        "landmark-collection/<gis_token>/collections/<str:collection_id>",
        LandmarkCollectionOGCCollectionApiView.as_view(),
        name="landmark-collection-collection",
    ),
    path(
        "landmark-collection/<gis_token>/collections/<str:collection_id>/items",
        LandmarkCollectionOGCCollectionItemsApiView.as_view(),
        name="landmark-collection-collection-items",
    ),
    path(
        "landmark-collection/<gis_token>",
        LandmarkCollectionOGCCollectionsApiView.as_view(),
        name="landmark-collection-data",
    ),
    path(
        "landmark-collection/<gis_token>/<str:collection_id>",
        LandmarkCollectionOGCCollectionApiView.as_view(),
        name="landmark-collection-layer",
    ),
    path(
        "landmark-collection/<gis_token>/<str:collection_id>/items",
        LandmarkCollectionOGCCollectionItemsApiView.as_view(),
        name="landmark-collection-layer-items",
    ),
    # ------------------------------------------------------------------
    # OGC API - Features: Landmark Collections endpoints (user token)
    # ------------------------------------------------------------------
    path(
        "landmark-collections/user/<user_token:key>/",
        LandmarkCollectionUserOGCLandingPageApiView.as_view(),
        name="landmark-collections-user-landing",
    ),
    path(
        "landmark-collections/user/<user_token:key>/conformance",
        LandmarkCollectionUserOGCConformanceApiView.as_view(),
        name="landmark-collections-user-conformance",
    ),
    path(
        "landmark-collections/user/<user_token:key>/collections",
        LandmarkCollectionUserOGCCollectionsApiView.as_view(),
        name="landmark-collections-user-collections",
    ),
    path(
        "landmark-collections/user/<user_token:key>/collections/<uuid:collection_id>",
        LandmarkCollectionUserOGCCollectionApiView.as_view(),
        name="landmark-collections-user-collection",
    ),
    path(
        (
            "landmark-collections/user/<user_token:key>/collections/"
            "<uuid:collection_id>/items"
        ),
        LandmarkCollectionUserOGCCollectionItemsApiView.as_view(),
        name="landmark-collections-user-collection-items",
    ),
    # ------------------------------------------------------------------
    # OGC API - Features: View endpoints (public, gis_token-based)
    # ------------------------------------------------------------------
    # Landing page — QGIS service-discovery entry point
    path(
        "view/<gis_token>/",
        OGCGISViewLandingPageApiView.as_view(),
        name="view-landing",
    ),
    # Conformance declaration
    path(
        "view/<gis_token>/conformance",
        OGCGISViewConformanceApiView.as_view(),
        name="view-conformance",
    ),
    # Collections list (QGIS follows rel:data from the landing page here)
    path("view/<gis_token>", OGCGISViewCollectionsApiView.as_view(), name="view-data"),
    # Frontend map viewer (not OGC)
    path(
        "view/<gis_token>/geojson",
        PublicGISViewGeoJSONApiView.as_view(),
        name="view-geojson",
    ),
    # Single collection metadata
    path(
        "view/<gis_token>/<gitsha:commit_sha>",
        OGCGISViewCollectionApiView.as_view(),
        name="view-collection",
    ),
    # Collection items — proxy-served filtered GeoJSON
    path(
        "view/<gis_token>/<gitsha:commit_sha>/items",
        OGCGISViewCollectionItemApiView.as_view(),
        name="view-collection-items",
    ),
    # ------------------------------------------------------------------
    # OGC API - Features: User endpoints (public, user_token-based)
    # ------------------------------------------------------------------
    # Landing page
    path(
        "user/<user_token:key>/",
        OGCGISUserLandingPageApiView.as_view(),
        name="user-landing",
    ),
    # Conformance declaration
    path(
        "user/<user_token:key>/conformance",
        OGCGISUserConformanceApiView.as_view(),
        name="user-conformance",
    ),
    # Collections list
    path(
        "user/<user_token:key>",
        OGCGISUserProjectsApiView.as_view(),
        name="user-data",
    ),
    # Single collection metadata
    path(
        "user/<user_token:key>/<gitsha:commit_sha>",
        OGCGISUserCollectionApiView.as_view(),
        name="user-collection",
    ),
    # Collection items — proxy-served filtered GeoJSON
    path(
        "user/<user_token:key>/<gitsha:commit_sha>/items",
        OGCGISUserCollectionItemApiView.as_view(),
        name="user-collection-items",
    ),
]
