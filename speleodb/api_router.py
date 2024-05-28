from django.conf.urls import include
from django.urls import path

app_name = "api"
urlpatterns = [
    path("v1/", include("speleodb.surveys.api.v1.urls")),
    path("auth/", include("allauth.headless.urls")),
]
