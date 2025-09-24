# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import TYPE_CHECKING

from django.urls import include
from django.urls import path

from speleodb.api.v1.views.resource import StationResourceApiView

if TYPE_CHECKING:
    from django.urls import URLPattern
    from django.urls import URLResolver

# from django.urls import path

# from speleodb.api.v1.views.station import ProjectStationListView
# from speleodb.api.v1.views.station import StationViewSet

# # Direct station CRUD operations (no project nesting)
# urlpatterns = [
#     # Station CRUD
#     path(
#         "",
#         StationViewSet.as_view({"get": "list", "post": "create"}),
#         name="station-list-create",
#     ),
#     path(
#         "<uuid:id>/",
#         StationViewSet.as_view(
#             {
#                 "get": "retrieve",
#                 "put": "update",
#                 "patch": "partial_update",
#                 "delete": "destroy",
#             }
#         ),
#         name="station-detail",
#     ),
#     # Station map endpoint with query parameter filtering
#     path(
#         "map/",
#         ProjectStationListView.as_view(),
#         name="stations-map",
#     ),
# ]

station_base_urlpatterns = [
    path(
        "resources/",
        StationResourceApiView.as_view(),
        name="station-resources-api",
    )
]

urlpatterns: list[URLPattern | URLResolver] = [
    path("<uuid:id>/", include(station_base_urlpatterns)),
]
