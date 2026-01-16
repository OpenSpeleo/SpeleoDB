# -*- coding: utf-8 -*-

from __future__ import annotations

from django.urls import URLPattern
from django.urls import URLResolver
from django.urls import include
from django.urls import path

from speleodb.api.v1.views.cylinder_fleet import CylinderInstallApiView
from speleodb.api.v1.views.cylinder_fleet import CylinderInstallGeoJSONApiView
from speleodb.api.v1.views.cylinder_fleet import CylinderInstallSpecificApiView
from speleodb.api.v1.views.cylinder_fleet import CylinderPressureCheckApiView
from speleodb.api.v1.views.cylinder_fleet import CylinderPressureCheckSpecificApiView

# Nested routes under /cylinder-installs/<uuid:install_id>/
cylinder_install_nested: list[URLPattern] = [
    path("", CylinderInstallSpecificApiView.as_view(), name="cylinder-install-detail"),
    # Pressure checks for this install
    path(
        "pressure-checks/",
        CylinderPressureCheckApiView.as_view(),
        name="cylinder-install-pressure-checks",
    ),
    path(
        "pressure-checks/<uuid:check_id>/",
        CylinderPressureCheckSpecificApiView.as_view(),
        name="cylinder-pressure-check-detail",
    ),
]


urlpatterns: list[URLPattern | URLResolver] = [
    # List all cylinder installs / Create new install
    path("", CylinderInstallApiView.as_view(), name="cylinder-installs"),
    # GeoJSON endpoint for all installed cylinders
    path(
        "geojson/",
        CylinderInstallGeoJSONApiView.as_view(),
        name="cylinder-installs-geojson",
    ),
    # Specific install operations
    path("<uuid:install_id>/", include(cylinder_install_nested)),
]
