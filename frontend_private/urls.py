from django.urls import path

from frontend_private.views import AuthTokenView
from frontend_private.views import DashboardView
from frontend_private.views import FeedbackView
from frontend_private.views import NewProjectView
from frontend_private.views import PassWordView
from frontend_private.views import PreferencesView
from frontend_private.views import ProjectCommitsView
from frontend_private.views import ProjectDangerZoneView
from frontend_private.views import ProjectDetailsView
from frontend_private.views import ProjectListingView
from frontend_private.views import ProjectMutexesView
from frontend_private.views import ProjectPermissionsView

app_name = "private"
urlpatterns = [
    path("", DashboardView.as_view(), name="dashboard"),
    path("password/", PassWordView.as_view(), name="password"),
    path("auth-token/", AuthTokenView.as_view(), name="auth-token"),
    path("feedback/", FeedbackView.as_view(), name="feedback"),
    path("preferences/", PreferencesView.as_view(), name="preferences"),
    path("projects/", ProjectListingView.as_view(), name="projects"),
    path(
        "project/new/",
        NewProjectView.as_view(),
        name="project_new",
    ),
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
    path(
        "project/<uuid:project_id>/mutexes/",
        ProjectMutexesView.as_view(),
        name="project_mutexes",
    ),
    path(
        "project/<uuid:project_id>/revisions/",
        ProjectCommitsView.as_view(),
        name="project_revisions",
    ),
    path(
        "project/<uuid:project_id>/danger_zone/",
        ProjectDangerZoneView.as_view(),
        name="project_danger_zone",
    ),
]
