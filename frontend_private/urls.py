from django.urls import path

from frontend_private.views import DashboardView
from frontend_private.views import FeedbackView
from frontend_private.views import NotificationsView
from frontend_private.views import ProjectDetailsView
from frontend_private.views import ProjectPermissionsView
from frontend_private.views import ProjectView

app_name = "private"
urlpatterns = [
    path("", DashboardView.as_view(), name="dashboard"),
    path("feedback/", FeedbackView.as_view(), name="feedback"),
    path("notifications/", NotificationsView.as_view(), name="notifications"),
    path("projects/", ProjectView.as_view(), name="projects"),
    path(
        "project/<uuid:project_id>/",
        ProjectDetailsView.as_view(),
        name="project_details",
    ),
    path(
        "project/<uuid:project_id>/permissions/",
        ProjectPermissionsView.as_view(),
        name="project_permissions",
    ),
]
