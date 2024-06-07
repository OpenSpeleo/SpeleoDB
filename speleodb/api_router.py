from django.conf.urls import include
from django.urls import path

app_name = "api"
urlpatterns = [
    path("v1/", include("speleodb.api.v1.urls", namespace="v1")),
    path("v1/", include("speleodb.users.api.v1.urls", namespace="v1_users")),
    path("auth/", include("allauth.headless.urls", namespace="auth")),
]
