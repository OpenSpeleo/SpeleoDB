# -*- coding: utf-8 -*-

from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.urls import include
from django.urls import path
from django.views.decorators.cache import cache_page
from django_js_reverse.views import urls_js

urlpatterns = [
    path("", include("frontend_public.urls")),
    path("", include("frontend_errors.urls", namespace="errors")),
    path("", include("speleodb.urls")),
    path("private/", include("frontend_private.urls", namespace="private")),
    # Admin Panel
    path(
        f"{Path(settings.ADMIN_URL) / 'dynamic_raw_id'}/",
        include("dynamic_raw_id.urls"),
    ),
    path(settings.ADMIN_URL, admin.site.urls),
    path(
        "helper/url_reverse.js",
        urls_js if settings.DEBUG else cache_page(5 * 60)(urls_js),
        name="url_reverse.js",
    ),
    # Debuging Tools
    path(settings.HIJACK_URL, include("hijack.urls", namespace="hijack")),
    # Media files
    *static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT),
]

if settings.DEBUG:
    # Static file serving when using Gunicorn + Uvicorn for local web socket development
    urlpatterns += staticfiles_urlpatterns()

    if "debug_toolbar" in settings.INSTALLED_APPS:
        urlpatterns += [
            path("__debug__/", include("debug_toolbar.urls")),
        ]

    if "schema_viewer" in settings.INSTALLED_APPS:
        urlpatterns += [
            path("schema-viewer/", include("schema_viewer.urls")),
        ]

    if "silk" in settings.INSTALLED_APPS:
        urlpatterns += [
            path("silk/", include("silk.urls")),
        ]
