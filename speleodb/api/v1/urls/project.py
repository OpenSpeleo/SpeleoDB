# -*- coding: utf-8 -*-

from __future__ import annotations

from django.urls import URLPattern
from django.urls import URLResolver
from django.urls import include
from django.urls import path

import speleodb.utils.url_converters  # noqa: F401  # Necessary to import the converters
from speleodb.api.v1.views.file import BlobDownloadView
from speleodb.api.v1.views.file import FileDownloadAtHashView
from speleodb.api.v1.views.file import FileDownloadView
from speleodb.api.v1.views.file import FileUploadView
from speleodb.api.v1.views.mutex import ProjectAcquireApiView
from speleodb.api.v1.views.mutex import ProjectReleaseApiView
from speleodb.api.v1.views.project import ProjectAllGeoJsonApiView
from speleodb.api.v1.views.project import ProjectApiView
from speleodb.api.v1.views.project import ProjectGeoJsonApiView
from speleodb.api.v1.views.project import ProjectSpecificApiView
from speleodb.api.v1.views.project_explorer import ProjectGitExplorerApiView
from speleodb.api.v1.views.project_explorer import ProjectRevisionsApiView
from speleodb.api.v1.views.station import ProjectStationsApiView
from speleodb.api.v1.views.station import ProjectStationsGeoJSONView
from speleodb.api.v1.views.team_permission import ProjectTeamPermissionListApiView
from speleodb.api.v1.views.team_permission import ProjectTeamPermissionSpecificApiView
from speleodb.api.v1.views.user_permission import ProjectUserPermissionListApiView
from speleodb.api.v1.views.user_permission import ProjectUserPermissionSpecificApiView

project_base_urlpatterns: list[URLPattern] = [
    path("", ProjectSpecificApiView.as_view(), name="project-detail"),
    # GeoJSON API
    path(
        "geojson/",
        ProjectGeoJsonApiView.as_view(),
        name="project-geojson",
    ),
    # =============================== GIT VIEW ============================== #
    path(
        "revisions/",
        ProjectRevisionsApiView.as_view(),
        name="project-revisions",
    ),
    path(
        "git_explorer/<gitsha:hexsha>/",
        ProjectGitExplorerApiView.as_view(),
        name="project-gitexplorer",
    ),
    # ========================= PROJECT PERMISSIONS ========================= #
    # --------- USER PERMISSIONS --------- #
    path(
        "permissions/user/",
        ProjectUserPermissionListApiView.as_view(),
        name="project-user-permissions",
    ),
    path(
        "permission/user/detail/",
        ProjectUserPermissionSpecificApiView.as_view(),
        name="project-user-permissions-detail",
    ),
    # --------- TEAM PERMISSIONS --------- #
    path(
        "permissions/team/",
        ProjectTeamPermissionListApiView.as_view(),
        name="project-team-permissions",
    ),
    path(
        "permission/team/detail/",
        ProjectTeamPermissionSpecificApiView.as_view(),
        name="project-team-permissions-detail",
    ),
    # =========================== PROJECT MUTEXES =========================== #
    path(
        "acquire/",
        ProjectAcquireApiView.as_view(),
        name="project-acquire",
    ),
    path(
        "release/",
        ProjectReleaseApiView.as_view(),
        name="project-release",
    ),
    # ============================= FILE UPLOAD ============================= #
    path(
        "upload/<upload_format:fileformat>/",
        FileUploadView.as_view(),
        name="project-upload",
    ),
    # ============================ FILE DOWNLOAD ============================ #
    path(
        "download/blob/<blobsha:hexsha>/",
        BlobDownloadView.as_view(),
        name="project-download-blob",
    ),
    path(
        "download/<download_format:fileformat>/",
        FileDownloadView.as_view(),
        name="project-download",
    ),
    path(
        "download/<download_format:fileformat>/<gitsha:hexsha>/",
        FileDownloadAtHashView.as_view(),
        name="project-download-at-hash",
    ),
    # ============================ STATIONS ============================ #
    path(
        "stations/",
        ProjectStationsApiView.as_view(),
        name="project-stations",
    ),
    path(
        "stations/geojson/",
        ProjectStationsGeoJSONView.as_view(),
        name="project-stations-geojson",
    ),
]

urlpatterns: list[URLPattern | URLResolver] = [
    path("", ProjectApiView.as_view(), name="projects"),
    # GeoJSON API
    path("geojson/", ProjectAllGeoJsonApiView.as_view(), name="all-projects-geojson"),
    path("<uuid:id>/", include(project_base_urlpatterns)),
]
