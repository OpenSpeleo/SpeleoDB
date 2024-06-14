# ruff: noqa
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
        import debug_toolbar

        urlpatterns = [path("__debug__/", include(debug_toolbar.urls))] + urlpatterns
