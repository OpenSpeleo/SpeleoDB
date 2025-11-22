# -*- coding: utf-8 -*-

from __future__ import annotations

from django.urls import URLPattern
from django.urls import URLResolver
from django.urls import include
from django.urls import path

from speleodb.api.v1.views.sensor_fleet import SensorSpecificApiView
from speleodb.api.v1.views.sensor_fleet import SensorToggleFunctionalApiView

# Nested routes under /sensor-fleets/<uuid:fleet_id>/
sensor_urlpatterns: list[URLPattern] = [
    path("", SensorSpecificApiView.as_view(), name="sensor-detail"),
    # --------- SENSORS --------- #
    path(
        "toggle-functional/",
        SensorToggleFunctionalApiView.as_view(),
        name="sensor-toggle-functional",
    ),
]

urlpatterns: list[URLPattern | URLResolver] = [
    # Sensor endpoints
    path("<uuid:id>/", include(sensor_urlpatterns)),
]
