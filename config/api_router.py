from django.conf import settings
from django.conf.urls import include
from django.urls import path
from rest_framework.routers import DefaultRouter
from rest_framework.routers import SimpleRouter

from speleodb.users.api.v1.views import UserViewSet

user_router = (
    DefaultRouter(use_regex_path=False)
    if settings.DEBUG
    else SimpleRouter(use_regex_path=False)
)
user_router.register("users", UserViewSet)

urlpatterns = [
    path("v1/", include("speleodb.surveys.api.v1.urls")),
]

app_name = "api"
urlpatterns += user_router.urls
