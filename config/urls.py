# ruff: noqa
from pathlib import Path

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.urls import include
from django.urls import path

urlpatterns = [
    path("", include("frontend_public.urls")),
    path("", include("frontend_errors.urls")),
    path("", include("speleodb.urls")),
    path("private/", include("frontend_private.urls", namespace="private")),
    # Admin Panel
    path(
        f"{Path(settings.ADMIN_URL) / 'dynamic_raw_id'}/",
        include("dynamic_raw_id.urls"),
    ),
    path(settings.ADMIN_URL, admin.site.urls),
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
