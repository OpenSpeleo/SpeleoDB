# -*- coding: utf-8 -*-

from __future__ import annotations

from django.urls import path

from speleodb.api.v1.views.surface_network import SurfaceMonitoringNetworkApiView
from speleodb.api.v1.views.surface_network import (
    SurfaceMonitoringNetworkPermissionApiView,
)
from speleodb.api.v1.views.surface_network import (
    SurfaceMonitoringNetworkSpecificApiView,
)

urlpatterns = [
    path(
        "",
        SurfaceMonitoringNetworkApiView.as_view(),
        name="surface-networks",
    ),
    path(
        "<uuid:network_id>/",
        SurfaceMonitoringNetworkSpecificApiView.as_view(),
        name="surface-network",
    ),
    path(
        "<uuid:network_id>/permissions/",
        SurfaceMonitoringNetworkPermissionApiView.as_view(),
        name="surface-network-permissions",
    ),
]
