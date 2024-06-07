from django.urls import include
from django.urls import path
from drf_spectacular.views import SpectacularAPIView
from drf_spectacular.views import SpectacularSwaggerView

urlpatterns = [
    # Even when using headless, the third-party provider endpoints are stil
    # needed for handling e.g. the OAuth handshake. The account views
    # can be disabled using `HEADLESS_ONLY = True`.
    path("allauth/", include("allauth.urls")),
    # Include the API endpoints:
    path("_allauth/", include("allauth.headless.urls")),
]


# API URLS
urlpatterns += [
    # API base url
    path("api/", include("speleodb.api_router")),
    path("api/schema/", SpectacularAPIView.as_view(), name="api-schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="api-schema"),
        name="api-docs",
    ),
]
