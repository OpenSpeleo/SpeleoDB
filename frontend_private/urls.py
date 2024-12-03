from django.urls import path
from django.urls import re_path

from frontend_private.views import AuthTokenView
from frontend_private.views import DashboardView
from frontend_private.views import FeedbackView
from frontend_private.views import NewProjectView
from frontend_private.views import NewTeamView
from frontend_private.views import PassWordView
from frontend_private.views import PreferencesView
from frontend_private.views import ProjectCommitsView
from frontend_private.views import ProjectDangerZoneView
from frontend_private.views import ProjectDetailsView
from frontend_private.views import ProjectGitExplorerView
from frontend_private.views import ProjectListingView
from frontend_private.views import ProjectMutexesView
from frontend_private.views import ProjectPermissionsView
from frontend_private.views import ProjectUploadView
from frontend_private.views import TeamDangerZoneView
from frontend_private.views import TeamDetailsView
from frontend_private.views import TeamListingView
from frontend_private.views import TeamMembershipsView

uuid_regex = "[0-9a-fA-F]{8}\\b-[0-9a-fA-F]{4}\\b-[0-9a-fA-F]{4}\\b-[0-9a-fA-F]{4}\\b-[0-9a-fA-F]{12}"  # noqa: E501

app_name = "private"
urlpatterns = [
    path("", DashboardView.as_view(), name="dashboard"),
    path("password/", PassWordView.as_view(), name="password"),
    path("auth-token/", AuthTokenView.as_view(), name="auth-token"),
    path("feedback/", FeedbackView.as_view(), name="feedback"),
    path("preferences/", PreferencesView.as_view(), name="preferences"),
    # Teams URLs
    path("teams/", TeamListingView.as_view(), name="teams"),
    path("team/new/", NewTeamView.as_view(), name="team_new"),
    path("team/<int:team_id>/", TeamDetailsView.as_view(), name="team_details"),
    path(
        "team/<int:team_id>/memberships/",
        TeamMembershipsView.as_view(),
        name="team_memberships",
    ),
    path(
        "project/<int:team_id>/danger_zone/",
        TeamDangerZoneView.as_view(),
        name="team_danger_zone",
    ),
    # Project URLs
    path("projects/", ProjectListingView.as_view(), name="projects"),
    path("project/new/", NewProjectView.as_view(), name="project_new"),
    path(
        "project/<uuid:project_id>/",
        ProjectDetailsView.as_view(),
        name="project_details",
    ),
    path(
        "project/<uuid:project_id>/upload/",
        ProjectUploadView.as_view(),
        name="project_upload",
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
        "project/<uuid:project_id>/browser/",
        ProjectGitExplorerView.as_view(),
        name="project_revision_explorer",
    ),
    re_path(
        rf"project/(?P<project_id>{uuid_regex})/browser/(?P<hexsha>[0-9a-fA-F]{{6,40}})/$",
        ProjectGitExplorerView.as_view(),
        name="project_revision_explorer",
    ),
    path(
        "project/<uuid:project_id>/danger_zone/",
        ProjectDangerZoneView.as_view(),
        name="project_danger_zone",
    ),
]
