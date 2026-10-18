"""URL configuration used only while exporting allauth's configured schema.

The upstream exporter reverses its own specification URL to find its mount.
Including those URLs here avoids enabling new HTTP routes in the application.
"""

from __future__ import annotations

from allauth.headless.spec.urls import urlpatterns as specification_patterns
from allauth.headless.urls import urlpatterns as authentication_patterns
from django.urls import include
from django.urls import path

urlpatterns = [
    path(
        "_allauth/",
        include(
            ([*authentication_patterns, *specification_patterns], "headless"),
            namespace="headless",
        ),
    ),
]
