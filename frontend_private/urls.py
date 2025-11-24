# -*- coding: utf-8 -*-

from __future__ import annotations

from django.urls import URLPattern
from django.urls import URLResolver
from django.urls import include
from django.urls import path

import speleodb.utils.url_converters  # noqa: F401  # Necessary to import the converters
from frontend_private.views import AuthTokenView
from frontend_private.views import DashboardView
from frontend_private.views import ExperimentDangerZoneView
from frontend_private.views import ExperimentDataViewerView
from frontend_private.views import ExperimentDetailsView
from frontend_private.views import ExperimentGISView
from frontend_private.views import ExperimentListingView
from frontend_private.views import ExperimentUserPermissionsView
from frontend_private.views import FeedbackView
from frontend_private.views import GISViewDangerZoneView
from frontend_private.views import GISViewDetailsView
from frontend_private.views import GISViewGISIntegrationView
from frontend_private.views import GISViewListingView
from frontend_private.views import MapViewerView
from frontend_private.views import NewExperimentView
from frontend_private.views import NewGISViewView
from frontend_private.views import NewProjectView
from frontend_private.views import NewSensorFleetView
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
from frontend_private.views import SensorFleetDangerZoneView
from frontend_private.views import SensorFleetDetailsView
from frontend_private.views import SensorFleetHistoryView
from frontend_private.views import SensorFleetListingView
from frontend_private.views import SensorFleetUserPermissionsView
from frontend_private.views import SensorFleetWatchlistView
from frontend_private.views import StationTagsView
from frontend_private.views import TeamDangerZoneView
from frontend_private.views import TeamDetailsView
from frontend_private.views import TeamListingView
from frontend_private.views import TeamMembershipsView
from frontend_private.views import ToolDMP2Json
from frontend_private.views import ToolDMPDoctor
from frontend_private.views import ToolXLSToArianeDMP
from frontend_private.views import ToolXLSToCompass

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

experiment_patterns = [
    path("", ExperimentDetailsView.as_view(), name="experiment_details"),
    path(
        "danger_zone/",
        ExperimentDangerZoneView.as_view(),
        name="experiment_danger_zone",
    ),
    path(
        "permissions/",
        ExperimentUserPermissionsView.as_view(),
        name="experiment_user_permissions",
    ),
    path(
        "gis/",
        ExperimentGISView.as_view(),
        name="experiment_gis_integration",
    ),
    path(
        "data_viewer/",
        ExperimentDataViewerView.as_view(),
        name="experiment_data_viewer",
    ),
]

sensor_fleet_patterns = [
    path("", SensorFleetDetailsView.as_view(), name="sensor_fleet_details"),
    path(
        "danger_zone/",
        SensorFleetDangerZoneView.as_view(),
        name="sensor_fleet_danger_zone",
    ),
    path(
        "permissions/",
        SensorFleetUserPermissionsView.as_view(),
        name="sensor_fleet_user_permissions",
    ),
    path(
        "history/",
        SensorFleetHistoryView.as_view(),
        name="sensor_fleet_history",
    ),
    path(
        "watchlist/",
        SensorFleetWatchlistView.as_view(),
        name="sensor_fleet_watchlist",
    ),
]

gis_view_patterns: list[URLPattern] = [
    path("", GISViewDetailsView.as_view(), name="gis_view_details"),
    path(
        "gis/",
        GISViewGISIntegrationView.as_view(),
        name="gis_view_gis_integration",
    ),
    path(
        "danger_zone/",
        GISViewDangerZoneView.as_view(),
        name="gis_view_danger_zone",
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
    path("station_tags/", StationTagsView.as_view(), name="station_tags"),
    # Teams URLs
    path("teams/", TeamListingView.as_view(), name="teams"),
    path("team/new/", NewTeamView.as_view(), name="team_new"),
    path("team/<uuid:team_id>/", include(team_urls)),
    # Project URLs
    path("projects/", ProjectListingView.as_view(), name="projects"),
    path("project/new/", NewProjectView.as_view(), name="project_new"),
    path("project/<uuid:project_id>/", include(project_patterns)),
    # Experiments URLs
    path("experiments/", ExperimentListingView.as_view(), name="experiments"),
    path("experiment/new/", NewExperimentView.as_view(), name="experiment_new"),
    path("experiment/<uuid:experiment_id>/", include(experiment_patterns)),
    # Sensor Fleets URLs
    path("sensor-fleets/", SensorFleetListingView.as_view(), name="sensor_fleets"),
    path("sensor-fleet/new/", NewSensorFleetView.as_view(), name="sensor_fleet_new"),
    path("sensor-fleet/<uuid:fleet_id>/", include(sensor_fleet_patterns)),
    # GIS Views URLs
    path("gis_views/", GISViewListingView.as_view(), name="gis_views"),
    path("gis_view/new/", NewGISViewView.as_view(), name="gis_view_new"),
    path("gis_view/<uuid:gis_view_id>/", include(gis_view_patterns)),
    # Map Viewer URLs
    path("map_viewer/", MapViewerView.as_view(), name="map_viewer"),
    # Tool URLs
    path("tools/dmp_to_json/", ToolDMP2Json.as_view(), name="tool-dmp2json"),
    path("tools/dmp_doctor/", ToolDMPDoctor.as_view(), name="tool-dmp-doctor"),
    path("tools/xls_to_dmp/", ToolXLSToArianeDMP.as_view(), name="tool-xls2dmp"),
    path("tools/xls_to_compass/", ToolXLSToCompass.as_view(), name="tool-xls2compass"),
]
