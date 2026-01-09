# -*- coding: utf-8 -*-

from __future__ import annotations

from django.urls import URLPattern
from django.urls import path

from speleodb.api.v1.views.exploration_lead import AllExploLeadsGeoJSONApiView
from speleodb.api.v1.views.exploration_lead import ExplorationLeadSpecificApiView

urlpatterns: list[URLPattern] = [
    path(
        "<uuid:id>/",
        ExplorationLeadSpecificApiView.as_view(),
        name="exploration-lead-detail",
    ),
    path(
        "geojson/",
        AllExploLeadsGeoJSONApiView.as_view(),
        name="exploration-lead-all-geojson",
    ),
]
