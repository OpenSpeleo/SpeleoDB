# -*- coding: utf-8 -*-

from django.urls import path

from speleodb.api.v1.views.poi import PointOfInterestMapView
from speleodb.api.v1.views.poi import PointOfInterestViewSet

# POI CRUD operations
urlpatterns = [
    # POI CRUD
    path(
        "pois/",
        PointOfInterestViewSet.as_view({"get": "list", "post": "create"}),
        name="poi-list-create",
    ),
    path(
        "pois/<uuid:id>/",
        PointOfInterestViewSet.as_view(
            {
                "get": "retrieve",
                "put": "update",
                "patch": "partial_update",
                "delete": "destroy",
            }
        ),
        name="poi-detail",
    ),
    # POI map endpoint for GeoJSON data
    path(
        "pois/map/",
        PointOfInterestMapView.as_view(),
        name="pois-map",
    ),
]
