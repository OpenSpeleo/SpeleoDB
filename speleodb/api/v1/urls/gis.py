# -*- coding: utf-8 -*-

from __future__ import annotations

from django.urls import URLPattern
from django.urls import URLResolver
from django.urls import path

import speleodb.utils.url_converters  # noqa: F401  # Necessary to import the converters
from speleodb.api.v1.views.experiment import ExperimentGISApiView
from speleodb.api.v1.views.project import ProjectGISGeoJsonApiView

app_name = "gis"

urlpatterns: list[URLPattern | URLResolver] = [
    path("experiment/<gis_token>/", ExperimentGISApiView.as_view(), name="experiment"),
    path("projects/", ProjectGISGeoJsonApiView.as_view(), name="projects"),
]
