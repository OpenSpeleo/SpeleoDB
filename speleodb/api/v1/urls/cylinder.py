# -*- coding: utf-8 -*-

from __future__ import annotations

from django.urls import URLPattern
from django.urls import URLResolver
from django.urls import include
from django.urls import path

from speleodb.api.v1.views.cylinder_fleet import CylinderSpecificApiView

# Nested routes under /cylinders/<uuid:id>/
cylinder_urlpatterns: list[URLPattern] = [
    path("", CylinderSpecificApiView.as_view(), name="cylinder-detail"),
]

urlpatterns: list[URLPattern | URLResolver] = [
    path("<uuid:id>/", include(cylinder_urlpatterns)),
]


# NOTE: CylinderInstall and CylinderPressureCheck routes are defined in
# cylinder_install.py
