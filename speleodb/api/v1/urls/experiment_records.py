# -*- coding: utf-8 -*-

from __future__ import annotations

from django.urls import URLPattern
from django.urls import URLResolver
from django.urls import path

from speleodb.api.v1.views.experiment import ExperimentRecordSpecificApiView

urlpatterns: list[URLPattern | URLResolver] = [
    path(
        "<uuid:id>/",
        ExperimentRecordSpecificApiView.as_view(),
        name="experiment-records-detail",
    ),
]
