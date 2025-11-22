# -*- coding: utf-8 -*-

from __future__ import annotations

from django.urls import URLPattern
from django.urls import URLResolver
from django.urls import include
from django.urls import path

from speleodb.api.v1.views.sensor_fleet import SensorApiView
from speleodb.api.v1.views.sensor_fleet import SensorFleetApiView
from speleodb.api.v1.views.sensor_fleet import SensorFleetPermissionApiView
from speleodb.api.v1.views.sensor_fleet import SensorFleetSpecificApiView

# Nested routes under /sensor-fleets/<uuid:fleet_id>/
sensor_fleet_urlpatterns: list[URLPattern] = [
    path("", SensorFleetSpecificApiView.as_view(), name="sensor-fleet-detail"),
    # --------- SENSORS --------- #
    path(
        "sensors/",
        SensorApiView.as_view(),
        name="sensor-fleet-sensors",
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
