# -*- coding: utf-8 -*-

from __future__ import annotations

from django.urls import URLPattern
from django.urls import URLResolver
from django.urls import path

from speleodb.api.v2.views.landmark_collection import LandmarkCollectionApiView
from speleodb.api.v2.views.landmark_collection import (
    LandmarkCollectionLandmarksExportExcelApiView,
)
from speleodb.api.v2.views.landmark_collection import (
    LandmarkCollectionLandmarksExportGPXApiView,
)
from speleodb.api.v2.views.landmark_collection import (
    LandmarkCollectionPermissionApiView,
)
from speleodb.api.v2.views.landmark_collection import LandmarkCollectionSpecificApiView

urlpatterns: list[URLPattern | URLResolver] = [
    path("", LandmarkCollectionApiView.as_view(), name="landmark-collections"),
    path(
        "<uuid:collection_id>/landmarks/export/excel/",
        LandmarkCollectionLandmarksExportExcelApiView.as_view(),
        name="landmark-collection-landmarks-export-excel",
    ),
    path(
        "<uuid:collection_id>/landmarks/export/gpx/",
        LandmarkCollectionLandmarksExportGPXApiView.as_view(),
        name="landmark-collection-landmarks-export-gpx",
    ),
    path(
        "<uuid:collection_id>/permissions/",
        LandmarkCollectionPermissionApiView.as_view(),
        name="landmark-collection-permissions",
    ),
    path(
        "<uuid:collection_id>/",
        LandmarkCollectionSpecificApiView.as_view(),
        name="landmark-collection-detail",
    ),
]
