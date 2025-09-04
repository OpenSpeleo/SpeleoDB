# -*- coding: utf-8 -*-

from __future__ import annotations

from django.urls import include
from django.urls import path

app_name = "api"
urlpatterns = [
    path("auth/", include("allauth.headless.urls", namespace="auth")),
    path("health/", include("speleodb.api.health.urls", namespace="health")),
    path("v1/", include("speleodb.api.v1.urls", namespace="v1")),
]
