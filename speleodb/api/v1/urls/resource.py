# -*- coding: utf-8 -*-

from django.urls import path

from speleodb.api.v1.views.resource import StationResourceViewSet

# Direct resource CRUD operations (not nested under stations)
urlpatterns = [
    # Resource CRUD
    path(
        "",
        StationResourceViewSet.as_view({"get": "list", "post": "create"}),
        name="resource-list-create",
    ),
    path(
        "<uuid:id>/",
        StationResourceViewSet.as_view(
            {
                "get": "retrieve",
                "put": "update",
                "patch": "partial_update",
                "delete": "destroy",
            }
        ),
        name="resource-detail",
    ),
]
