# -*- coding: utf-8 -*-

from __future__ import annotations

from django.urls import URLPattern
from django.urls import URLResolver
from django.urls import include
from django.urls import path
from drf_spectacular.views import SpectacularAPIView
from drf_spectacular.views import SpectacularSwaggerView

from speleodb.git_proxy.urls import urlpatterns as git_proxy_patterns
from speleodb.users.oidc import WebsiteAuthorizationView
from speleodb.users.oidc import WebsiteRevokeView
from speleodb.users.oidc import WebsiteTokenView

urlpatterns: list[URLPattern | URLResolver] = [
    # Even when using headless, the third-party provider endpoints are stil
    # needed for handling e.g. the OAuth handshake. The account views
    # can be disabled using `HEADLESS_ONLY = True`.
    path("allauth/", include("allauth.urls")),
    # Validate the registered callback and S256 PKCE before consent.
    path("identity/o/authorize", WebsiteAuthorizationView.as_view()),
    path("identity/o/api/token", WebsiteTokenView.as_view()),
    path("identity/o/api/revoke", WebsiteRevokeView.as_view()),
    path("", include("allauth.idp.urls")),
    # Include the API endpoints:
    path("_allauth/", include("allauth.headless.urls")),
    # Git URLs
    path("git/", include(git_proxy_patterns)),
    # API base url
    path("api/", include("speleodb.api_router")),
    path("api/schema/", SpectacularAPIView.as_view(), name="api-schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="api-schema"),
        name="api-docs",
    ),
]
