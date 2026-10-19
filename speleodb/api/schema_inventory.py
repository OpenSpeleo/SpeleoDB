"""Inventory mounted API handlers independently of schema annotations or prefixes."""

from __future__ import annotations

import re
from typing import Any

from allauth.headless.base.views import APIView as AllauthAPIView
from django.urls import URLPattern
from django.urls import URLResolver
from django.urls import get_resolver
from drf_spectacular.views import SpectacularSwaggerView
from rest_framework.views import APIView

METHODS = ("get", "post", "put", "patch", "delete")
# These mounts are guards, not an inclusion filter: APIViews elsewhere are also
# discovered. A function API added here must receive an explicit adapter instead
# of silently disappearing from the contract when it is not a DRF/allauth view.
_API_MOUNTS = ("api/", "_allauth/", "git/", ".well-known/")
_HTML_NAVIGATION_ROUTES = frozenset(
    {(".well-known/change-password", "well_known.views.change_password")}
)


def current_api_routes() -> list[dict[str, Any]]:
    """Include every DRF/allauth mount, including protocol and auth aliases.

    Swagger's HTML documentation UI is deliberately excluded by class. Ordinary
    Django HTML views, admin/debug tooling and static assets are not APIViews.
    A new APIView is inventoried wherever it is mounted, even with schema=None.
    The obsolete SpeleoDB /api/v1 mirror is outside the supported SDK contract;
    allauth protocol /v1 routes remain included on both mounts. HEAD/OPTIONS
    availability is recorded without synthesizing SDK operations.
    """
    routes: list[dict[str, Any]] = []

    def visit(patterns: list[URLPattern | URLResolver], prefix: str = "") -> None:
        for pattern in patterns:
            route = prefix + str(pattern.pattern)
            if isinstance(pattern, URLResolver):
                visit(pattern.url_patterns, route)
                continue
            if route.startswith("api/v1/"):
                continue
            callback = pattern.callback
            view = getattr(callback, "cls", None) or getattr(
                callback, "view_class", None
            )
            if view is None or not issubclass(view, (APIView, AllauthAPIView)):
                identity = f"{callback.__module__}.{callback.__qualname__}"
                if (
                    route.startswith(_API_MOUNTS)
                    and (route, identity) not in _HTML_NAVIGATION_ROUTES
                ):
                    raise ValueError(
                        "API mount needs an explicit inventory adapter: "
                        f"/{route} ({identity})"
                    )
                continue
            if issubclass(view, SpectacularSwaggerView):
                continue
            path = "/" + re.sub(r"<(?:[^:>]+:)?([^>]+)>", r"{\1}", route)
            available = [
                method
                for method in view.http_method_names
                if hasattr(view, method) or (method == "head" and hasattr(view, "get"))
            ]
            routes.extend(
                {
                    "path": path,
                    "method": method,
                    "route": "/" + route,
                    "view": f"{view.__module__}.{view.__name__}",
                    "name": pattern.name,
                    "available_methods": available,
                }
                for method in METHODS
                if method in available
            )

    visit(get_resolver().url_patterns)
    return routes
