# -*- coding: utf-8 -*-

from __future__ import annotations

from django.urls import URLPattern
from django.urls import URLResolver
from django.urls import include
from django.urls import path

from speleodb.api.v1.views.sensor_fleet import SensorApiView
from speleodb.api.v1.views.sensor_fleet import SensorFleetApiView
from speleodb.api.v1.views.sensor_fleet import SensorFleetExportExcelApiView
from speleodb.api.v1.views.sensor_fleet import SensorFleetPermissionApiView
from speleodb.api.v1.views.sensor_fleet import SensorFleetSpecificApiView
from speleodb.api.v1.views.sensor_fleet import SensorFleetWatchlistApiView
from speleodb.api.v1.views.sensor_fleet import SensorFleetWatchlistExportExcelApiView

# Nested routes under /sensor-fleets/<uuid:fleet_id>/
sensor_fleet_urlpatterns: list[URLPattern] = [
    path("", SensorFleetSpecificApiView.as_view(), name="sensor-fleet-detail"),
    # --------- SENSORS --------- #
    path(
        "sensors/export/",
        SensorFleetExportExcelApiView.as_view(),
        name="sensor-fleet-sensors-export",
    ),
    path(
        "sensors/",
        SensorApiView.as_view(),
        name="sensor-fleet-sensors",
    ),
    path(
        "sensors/watchlist/",
        SensorFleetWatchlistApiView.as_view(),
        name="sensor-fleet-watchlist",
    ),
    path(
        "sensors/watchlist/export/",
        SensorFleetWatchlistExportExcelApiView.as_view(),
        name="sensor-fleet-watchlist-export",
    ),
    # --------- PERMISSIONS --------- #
    path(
        "permissions/",
        SensorFleetPermissionApiView.as_view(),
        name="sensor-fleet-permissions",
    ),
]

urlpatterns: list[URLPattern | URLResolver] = [
    # Sensor Fleet endpoints
    path("", SensorFleetApiView.as_view(), name="sensor-fleets"),
    path("<uuid:fleet_id>/", include(sensor_fleet_urlpatterns)),
]
