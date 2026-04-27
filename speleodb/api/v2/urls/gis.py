# -*- coding: utf-8 -*-

"""URL configuration for the SpeleoDB OGC API - Features endpoints.

The four OGC families (project gis-view, project user, landmark single,
landmark user) all expose the same canonical OGC URL surface:

* ``<base>/`` — landing page (the URL users copy into ArcGIS / QGIS)
* ``<base>/conformance`` — conformance declaration
* ``<base>/collections`` — collections list
* ``<base>/collections/<id>`` — single collection metadata
* ``<base>/collections/<id>/items`` — feature items
* ``<base>/collections/<id>/items/<feature_id>`` — single feature

The previous bare-token aliases (``view/<token>``, ``user/<token>``,
``landmark-collection/<token>/<id>`` and friends) are intentionally
removed: handing out a non-landing URL violated the OGC discovery
pattern and the project's own ``tasks/lessons/ogc-qgis-discovery.md``
lesson. Tests in ``test_legacy_bare_token_paths_are_404`` pin that
those URLs now return 404.

The non-OGC ``experiment`` endpoint and the frontend-helper
``view-geojson`` endpoint stay where they are, with documentation
clarifying that they are NOT OGC API Features services.

URL converter discipline: every ``gis_token`` segment uses the explicit
``<gis_token:gis_token>`` form so the registered converter's regex
(``[0-9a-fA-F]{40}``) is enforced at the routing layer. Writing
``<gis_token>`` (no colon) silently falls back to the default ``str``
converter and the regex never runs. Same rule applies to ``<user_token:key>``.
"""

from __future__ import annotations

from django.urls import URLPattern
from django.urls import URLResolver
from django.urls import path

import speleodb.utils.url_converters  # noqa: F401  # registers `gitsha` and `user_token`/`gis_token` converters
from speleodb.api.v2.views.experiment import ExperimentGISApiView
from speleodb.api.v2.views.gis_view import OGCGISViewCollectionApiView
from speleodb.api.v2.views.gis_view import OGCGISViewCollectionItemsApiView
from speleodb.api.v2.views.gis_view import OGCGISViewCollectionsApiView
from speleodb.api.v2.views.gis_view import OGCGISViewConformanceApiView
from speleodb.api.v2.views.gis_view import OGCGISViewLandingPageApiView
from speleodb.api.v2.views.gis_view import OGCGISViewSingleFeatureApiView
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
    LandmarkCollectionOGCSingleFeatureApiView,
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
from speleodb.api.v2.views.landmark_collection_ogc import (
    LandmarkCollectionUserOGCSingleFeatureApiView,
)
from speleodb.api.v2.views.ogc_base import OGCOpenAPIView
from speleodb.api.v2.views.project_geojson import OGCGISUserCollectionApiView
from speleodb.api.v2.views.project_geojson import OGCGISUserCollectionItemsApiView
from speleodb.api.v2.views.project_geojson import OGCGISUserConformanceApiView
from speleodb.api.v2.views.project_geojson import OGCGISUserLandingPageApiView
from speleodb.api.v2.views.project_geojson import OGCGISUserProjectsApiView
from speleodb.api.v2.views.project_geojson import OGCGISUserSingleFeatureApiView

app_name = "gis-ogc"

urlpatterns: list[URLPattern | URLResolver] = [
    # ------------------------------------------------------------------
    # OGC API definition (service-desc). Single static document shared
    # by every OGC family's landing page. ETag-based conditional
    # fetches keep the egress essentially free across deploys.
    # ------------------------------------------------------------------
    path(
        "openapi/",
        OGCOpenAPIView.as_view(),
        name="openapi",
    ),
    # ------------------------------------------------------------------
    # Experiment endpoint (NOT OGC API Features — single flat
    # FeatureCollection at one URL). Documented as such in
    # frontend_private/templates/pages/experiment/gis_integration.html
    # and tasks/.../ogc-arcgis-empty-layers.md.
    # ------------------------------------------------------------------
    path(
        "experiment/<gis_token:gis_token>/",
        ExperimentGISApiView.as_view(),
        name="experiment",
    ),
    # ------------------------------------------------------------------
    # OGC API - Features: Landmark Collection (public gis_token)
    # ------------------------------------------------------------------
    path(
        "landmark-collection/<gis_token:gis_token>/",
        LandmarkCollectionOGCLandingPageApiView.as_view(),
        name="landmark-collection-landing",
    ),
    path(
        "landmark-collection/<gis_token:gis_token>/conformance",
        LandmarkCollectionOGCConformanceApiView.as_view(),
        name="landmark-collection-conformance",
    ),
    path(
        "landmark-collection/<gis_token:gis_token>/collections",
        LandmarkCollectionOGCCollectionsApiView.as_view(),
        name="landmark-collection-collections",
    ),
    path(
        "landmark-collection/<gis_token:gis_token>/collections/<str:collection_id>",
        LandmarkCollectionOGCCollectionApiView.as_view(),
        name="landmark-collection-collection",
    ),
    path(
        (
            "landmark-collection/<gis_token:gis_token>/collections/"
            "<str:collection_id>/items"
        ),
        LandmarkCollectionOGCCollectionItemsApiView.as_view(),
        name="landmark-collection-collection-items",
    ),
    path(
        (
            "landmark-collection/<gis_token:gis_token>/collections/"
            "<str:collection_id>/items/<str:feature_id>"
        ),
        LandmarkCollectionOGCSingleFeatureApiView.as_view(),
        name="landmark-collection-collection-feature",
    ),
    # ------------------------------------------------------------------
    # OGC API - Features: Landmark Collections (user_token)
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
        ("landmark-collections/user/<user_token:key>/collections/<str:collection_id>"),
        LandmarkCollectionUserOGCCollectionApiView.as_view(),
        name="landmark-collections-user-collection",
    ),
    path(
        (
            "landmark-collections/user/<user_token:key>/collections/"
            "<str:collection_id>/items"
        ),
        LandmarkCollectionUserOGCCollectionItemsApiView.as_view(),
        name="landmark-collections-user-collection-items",
    ),
    path(
        (
            "landmark-collections/user/<user_token:key>/collections/"
            "<str:collection_id>/items/<str:feature_id>"
        ),
        LandmarkCollectionUserOGCSingleFeatureApiView.as_view(),
        name="landmark-collections-user-collection-feature",
    ),
    # ------------------------------------------------------------------
    # OGC API - Features: GIS-View (public gis_token)
    # ------------------------------------------------------------------
    path(
        "view/<gis_token:gis_token>/",
        OGCGISViewLandingPageApiView.as_view(),
        name="view-landing",
    ),
    path(
        "view/<gis_token:gis_token>/conformance",
        OGCGISViewConformanceApiView.as_view(),
        name="view-conformance",
    ),
    # NOT OGC: frontend map viewer GeoJSON helper.
    path(
        "view/<gis_token:gis_token>/geojson",
        PublicGISViewGeoJSONApiView.as_view(),
        name="view-geojson",
    ),
    path(
        "view/<gis_token:gis_token>/collections",
        OGCGISViewCollectionsApiView.as_view(),
        name="view-collections",
    ),
    path(
        "view/<gis_token:gis_token>/collections/<gitsha:collection_id>",
        OGCGISViewCollectionApiView.as_view(),
        name="view-collection",
    ),
    path(
        "view/<gis_token:gis_token>/collections/<gitsha:collection_id>/items",
        OGCGISViewCollectionItemsApiView.as_view(),
        name="view-collection-items",
    ),
    path(
        (
            "view/<gis_token:gis_token>/collections/<gitsha:collection_id>/"
            "items/<str:feature_id>"
        ),
        OGCGISViewSingleFeatureApiView.as_view(),
        name="view-collection-feature",
    ),
    # ------------------------------------------------------------------
    # OGC API - Features: User (user_token)
    # ------------------------------------------------------------------
    path(
        "user/<user_token:key>/",
        OGCGISUserLandingPageApiView.as_view(),
        name="user-landing",
    ),
    path(
        "user/<user_token:key>/conformance",
        OGCGISUserConformanceApiView.as_view(),
        name="user-conformance",
    ),
    path(
        "user/<user_token:key>/collections",
        OGCGISUserProjectsApiView.as_view(),
        name="user-collections",
    ),
    path(
        "user/<user_token:key>/collections/<gitsha:collection_id>",
        OGCGISUserCollectionApiView.as_view(),
        name="user-collection",
    ),
    path(
        "user/<user_token:key>/collections/<gitsha:collection_id>/items",
        OGCGISUserCollectionItemsApiView.as_view(),
        name="user-collection-items",
    ),
    path(
        (
            "user/<user_token:key>/collections/<gitsha:collection_id>/"
            "items/<str:feature_id>"
        ),
        OGCGISUserSingleFeatureApiView.as_view(),
        name="user-collection-feature",
    ),
]
