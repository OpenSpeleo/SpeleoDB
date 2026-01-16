# -*- coding: utf-8 -*-

from __future__ import annotations

from django.urls import URLPattern
from django.urls import URLResolver
from django.urls import include
from django.urls import path

from speleodb.api.v1.views.cylinder_fleet import CylinderApiView
from speleodb.api.v1.views.cylinder_fleet import CylinderFleetApiView
from speleodb.api.v1.views.cylinder_fleet import CylinderFleetExportExcelApiView
from speleodb.api.v1.views.cylinder_fleet import CylinderFleetPermissionApiView
from speleodb.api.v1.views.cylinder_fleet import CylinderFleetSpecificApiView
from speleodb.api.v1.views.cylinder_fleet import CylinderFleetWatchlistApiView
from speleodb.api.v1.views.cylinder_fleet import (
    CylinderFleetWatchlistExportExcelApiView,
)

# Nested routes under /cylinder-fleets/<uuid:fleet_id>/
cylinder_fleet_urlpatterns: list[URLPattern] = [
    path("", CylinderFleetSpecificApiView.as_view(), name="cylinder-fleet-detail"),
    # --------- CYLINDERS --------- #
    path(
        "cylinders/export/",
        CylinderFleetExportExcelApiView.as_view(),
        name="cylinder-fleet-cylinders-export",
    ),
    path(
        "cylinders/",
        CylinderApiView.as_view(),
        name="cylinder-fleet-cylinders",
    ),
    path(
        "cylinders/watchlist/",
        CylinderFleetWatchlistApiView.as_view(),
        name="cylinder-fleet-watchlist",
    ),
    path(
        "cylinders/watchlist/export/",
        CylinderFleetWatchlistExportExcelApiView.as_view(),
        name="cylinder-fleet-watchlist-export",
    ),
    # --------- PERMISSIONS --------- #
    path(
        "permissions/",
        CylinderFleetPermissionApiView.as_view(),
        name="cylinder-fleet-permissions",
    ),
]

urlpatterns: list[URLPattern | URLResolver] = [
    # Cylinder Fleet endpoints
    path("", CylinderFleetApiView.as_view(), name="cylinder-fleets"),
    path("<uuid:fleet_id>/", include(cylinder_fleet_urlpatterns)),
]
