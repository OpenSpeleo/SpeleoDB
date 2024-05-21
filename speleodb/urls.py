from django.urls import include
from django.urls import path
from drf_spectacular.views import SpectacularAPIView
from drf_spectacular.views import SpectacularSwaggerView

from speleodb.users.api.v1.views import ObtainAuthToken

urlpatterns = [
    # User management
    path("users/", include("speleodb.users.urls", namespace="users")),
    path("accounts/", include("allauth.urls")),
]

# API URLS
urlpatterns += [
    # API base url
    path("api/", include("speleodb.api_router")),
    # DRF auth token
    path("api/auth-token/", ObtainAuthToken.as_view()),
    path("api/schema/", SpectacularAPIView.as_view(), name="api-schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="api-schema"),
        name="api-docs",
    ),
]
