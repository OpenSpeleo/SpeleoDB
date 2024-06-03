from django.urls import path
from django.views.generic import TemplateView

from frontend_private.views import DashboardView
from frontend_private.views import ProjectView
from frontend_private.views import AccountView

app_name = "private"
urlpatterns = [
    path("", DashboardView.as_view(), name="dashboard"),
    path("projects/", ProjectView.as_view(), name="projects"),
    path("account/", AccountView.as_view(), name="account"),
]
