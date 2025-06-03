from __future__ import annotations

from django.urls import include
from django.urls import path

app_name = "api"
urlpatterns = [
    path("v1/", include("speleodb.api.v1.urls", namespace="v1")),
    path("auth/", include("allauth.headless.urls", namespace="auth")),
]
