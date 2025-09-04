# -*- coding: utf-8 -*-

from __future__ import annotations

from django.urls import URLPattern
from django.urls import URLResolver
from django.urls import path

from speleodb.api.health.views import HealthCheckApiView
from speleodb.api.health.views import StatusApiView

app_name = "health"

urlpatterns: list[URLResolver | URLPattern] = [
    path("", StatusApiView.as_view(), name="status"),
    path("details/", HealthCheckApiView.as_view(), name="details"),
]
