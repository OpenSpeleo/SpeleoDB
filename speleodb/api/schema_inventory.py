"""Inventory current API routes independently of schema annotations."""

from __future__ import annotations

import re
from typing import Any

from django.urls import URLPattern
from django.urls import URLResolver
from django.urls import get_resolver

CURRENT_PREFIXES = ("/api/v2/", "/api/health/", "/_allauth/")
METHODS = ("get", "post", "put", "patch", "delete")


def current_api_routes() -> list[dict[str, Any]]:
    routes: list[dict[str, Any]] = []

    def visit(patterns: list[URLPattern | URLResolver], prefix: str = "") -> None:
        for pattern in patterns:
            route = prefix + str(pattern.pattern)
            if isinstance(pattern, URLResolver):
                visit(pattern.url_patterns, route)
                continue
            path = "/" + re.sub(r"<(?:[^:>]+:)?([^>]+)>", r"{\1}", route)
            if not path.startswith(CURRENT_PREFIXES):
                continue
            callback = pattern.callback
            view = getattr(callback, "cls", None) or getattr(
                callback, "view_class", None
            )
            if view is None:
                raise ValueError(
                    f"API route needs an explicit inventory adapter: {route}"
                )
            routes.extend(
                {
                    "path": path,
                    "method": method,
                    "route": "/" + route,
                    "view": f"{view.__module__}.{view.__name__}",
                    "name": pattern.name,
                }
                for method in METHODS
                if hasattr(view, method)
            )

    visit(get_resolver().url_patterns)
    return routes
