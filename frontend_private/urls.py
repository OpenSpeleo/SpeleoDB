# -*- coding: utf-8 -*-

from __future__ import annotations

from django.urls import URLPattern
from django.urls import URLResolver
from django.urls import include
from django.urls import path

import speleodb.utils.url_converters  # noqa: F401  # Necessary to import the converters
from frontend_private.views import AuthTokenView
from frontend_private.views import DashboardView
from frontend_private.views import FeedbackView
from frontend_private.views import MapViewerView
from frontend_private.views import NewProjectView
from frontend_private.views import NewTeamView
from frontend_private.views import PassWordView
from frontend_private.views import PreferencesView
from frontend_private.views import ProjectDangerZoneView
from frontend_private.views import ProjectDetailsView
from frontend_private.views import ProjectGitExplorerView
from frontend_private.views import ProjectGitInstructionsView
from frontend_private.views import ProjectListingView
from frontend_private.views import ProjectMutexesView
from frontend_private.views import ProjectRevisionHistoryView
from frontend_private.views import ProjectTeamPermissionsView
from frontend_private.views import ProjectUploadView
from frontend_private.views import ProjectUserPermissionsView
from frontend_private.views import TeamDangerZoneView
from frontend_private.views import TeamDetailsView
from frontend_private.views import TeamListingView
from frontend_private.views import TeamMembershipsView

app_name = "private"


project_patterns: list[URLPattern | URLResolver] = [
    path("", ProjectDetailsView.as_view(), name="project_details"),
    path("upload/", ProjectUploadView.as_view(), name="project_upload"),
    path(
        "permissions/",
        include(
            [
                path(
                    "user/",
                    ProjectUserPermissionsView.as_view(),
                    name="project_user_permissions",
                ),
                path(
                    "team/",
                    ProjectTeamPermissionsView.as_view(),
                    name="project_team_permissions",
                ),
            ]
        ),
    ),
    path("mutexes/", ProjectMutexesView.as_view(), name="project_mutexes"),
    path("revisions/", ProjectRevisionHistoryView.as_view(), name="project_revisions"),
    path(
        "browser/<gitsha:hexsha>/",
        ProjectGitExplorerView.as_view(),
        name="project_revision_explorer",
    ),
    path(
        "danger_zone/",
        ProjectDangerZoneView.as_view(),
        name="project_danger_zone",
    ),
    path(
        "git_instructions/",
        ProjectGitInstructionsView.as_view(),
        name="project_git_instructions",
    ),
]

team_urls: list[URLPattern] = [
    path("", TeamDetailsView.as_view(), name="team_details"),
    path(
        "memberships/",
        TeamMembershipsView.as_view(),
        name="team_memberships",
    ),
    path(
        "danger_zone/",
        TeamDangerZoneView.as_view(),
        name="team_danger_zone",
    ),
]

urlpatterns: list[URLPattern | URLResolver] = [
    # User URLs
    path("", DashboardView.as_view(), name="user_dashboard"),
    path("auth-token/", AuthTokenView.as_view(), name="user_authtoken"),
    path("feedback/", FeedbackView.as_view(), name="user_feedback"),
    path("password/", PassWordView.as_view(), name="user_password"),
    path("preferences/", PreferencesView.as_view(), name="user_preferences"),
    # Teams URLs
    path("teams/", TeamListingView.as_view(), name="teams"),
    path("team/new/", NewTeamView.as_view(), name="team_new"),
    path("team/<uuid:team_id>/", include(team_urls)),
    # Project URLs
    path("projects/", ProjectListingView.as_view(), name="projects"),
    path("project/new/", NewProjectView.as_view(), name="project_new"),
    path("project/<uuid:project_id>/", include(project_patterns)),
    # Map Viewer URLs
    path("map_viewer/", MapViewerView.as_view(), name="map_viewer"),
]
