# -*- coding: utf-8 -*-

from __future__ import annotations

from django.urls import include
from django.urls import path

app_name = "api"
urlpatterns = [
    path("auth/", include("allauth.headless.urls", namespace="auth")),
    path("health/", include("speleodb.api.health.urls", namespace="health")),
    # DEPRECATED: Remove this in the future
    path("v1/", include("speleodb.api.v2.urls", namespace="v1")),
    # Latest Schema
    path("v2/", include("speleodb.api.v2.urls", namespace="v2")),
]
