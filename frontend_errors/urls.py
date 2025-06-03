# -*- coding: utf-8 -*-

from __future__ import annotations

from django.conf import settings
from django.urls import path
from django.views import defaults as default_views
from django.views.defaults import ERROR_400_TEMPLATE_NAME
from django.views.defaults import ERROR_403_TEMPLATE_NAME
from django.views.defaults import ERROR_404_TEMPLATE_NAME
from django.views.defaults import ERROR_500_TEMPLATE_NAME

ERROR_400_TEMPLATE_NAME = "400.html"  # noqa: F811
ERROR_403_TEMPLATE_NAME = "403.html"  # noqa: F811
ERROR_404_TEMPLATE_NAME = "404.html"  # noqa: F811
ERROR_500_TEMPLATE_NAME = "500.html"  # noqa: F811

app_name = "errors"

if settings.DEBUG:
    # This allows the error pages to be debugged during development, just visit
    # these url in browser to see how these error pages look like.
    urlpatterns = [
        path(
            "400/",
            default_views.bad_request,
            kwargs={"exception": Exception("Bad Request!")},
        ),
        path(
            "403/",
            default_views.permission_denied,
            kwargs={"exception": Exception("Permission Denied")},
        ),
        path(
            "404/",
            default_views.page_not_found,
            kwargs={"exception": Exception("Page not Found")},
        ),
        path("500/", default_views.server_error),
    ]

else:
    urlpatterns = []
