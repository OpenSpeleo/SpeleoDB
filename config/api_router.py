from django.conf import settings
from django.urls import path
from rest_framework.routers import DefaultRouter
from rest_framework.routers import SimpleRouter

from speleodb.surveys.api.views import ProjectListApiView
from speleodb.users.api.views import UserViewSet

router = DefaultRouter() if settings.DEBUG else SimpleRouter()

router.register("users", UserViewSet)

urlpatterns = [
    path("projects/", ProjectListApiView.as_view()),
]


app_name = "api"
urlpatterns += router.urls
