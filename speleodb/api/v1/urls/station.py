# -*- coding: utf-8 -*-

from django.urls import path

from speleodb.api.v1.views.station import ProjectStationListView
from speleodb.api.v1.views.station import StationViewSet

# Direct station CRUD operations (no project nesting)
urlpatterns = [
    # Station CRUD
    path(
        "",
        StationViewSet.as_view({"get": "list", "post": "create"}),
        name="station-list-create",
    ),
    path(
        "<uuid:id>/",
        StationViewSet.as_view(
            {
                "get": "retrieve",
                "put": "update",
                "patch": "partial_update",
                "delete": "destroy",
            }
        ),
        name="station-detail",
    ),
    # Station map endpoint with query parameter filtering
    path(
        "map/",
        ProjectStationListView.as_view(),
        name="stations-map",
    ),
]
