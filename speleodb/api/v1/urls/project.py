#!/usr/bin/env python
# -*- coding: utf-8 -*-

from django.urls import URLPattern
from django.urls import URLResolver
from django.urls import include
from django.urls import path

import speleodb.utils.url_converters  # noqa: F401  # Necessary to import the converters
from speleodb.api.v1.views.file import BlobDownloadView
from speleodb.api.v1.views.file import FileDownloadView
from speleodb.api.v1.views.file import FileUploadView
from speleodb.api.v1.views.mutex import ProjectAcquireApiView
from speleodb.api.v1.views.mutex import ProjectReleaseApiView
from speleodb.api.v1.views.project import ProjectApiView
from speleodb.api.v1.views.project import ProjectSpecificApiView
from speleodb.api.v1.views.project_explorer import ProjectGitExplorerApiView
from speleodb.api.v1.views.project_explorer import ProjectRevisionsApiView
from speleodb.api.v1.views.team_permission import ProjectTeamPermissionListView
from speleodb.api.v1.views.team_permission import ProjectTeamPermissionView
from speleodb.api.v1.views.user_permission import ProjectUserPermissionListView
from speleodb.api.v1.views.user_permission import ProjectUserPermissionView

project_base_urlpatterns: list[URLPattern] = [
    path("", ProjectSpecificApiView.as_view(), name="one_project_apiview"),
    # =============================== GIT VIEW ============================== #
    path(
        "revisions/",
        ProjectRevisionsApiView.as_view(),
        name="one_project_revisions_apiview",
    ),
    path(
        "git_explorer/<gitsha:hexsha>/",
        ProjectGitExplorerApiView.as_view(),
        name="one_project_gitexplorer_apiview",
    ),
    # ========================= PROJECT PERMISSIONS ========================= #
    # --------- USER PERMISSIONS --------- #
    path(
        "permission/user/",
        ProjectUserPermissionView.as_view(),
        name="project_user_permission",
    ),
    path(
        "permissions/user/",
        ProjectUserPermissionListView.as_view(),
        name="list_project_user_permissions",
    ),
    # --------- TEAM PERMISSIONS --------- #
    path(
        "permission/team/",
        ProjectTeamPermissionView.as_view(),
        name="project_team_permission",
    ),
    path(
        "permissions/team/",
        ProjectTeamPermissionListView.as_view(),
        name="list_project_team_permissions",
    ),
    # =========================== PROJECT MUTEXES =========================== #
    path(
        "acquire/",
        ProjectAcquireApiView.as_view(),
        name="acquire_project",
    ),
    path(
        "release/",
        ProjectReleaseApiView.as_view(),
        name="release_project",
    ),
    # ============================= FILE UPLOAD ============================= #
    path(
        "upload/<upload_format:fileformat>/",
        FileUploadView.as_view(),
        name="upload_project",
    ),
    # ============================ FILE DOWNLOAD ============================ #
    path(
        "download/blob/<blobsha:hexsha>/",
        BlobDownloadView.as_view(),
        name="download_blob",
    ),
    path(
        "download/<download_format:fileformat>/",
        FileDownloadView.as_view(),
        name="download_project",
    ),
    path(
        "download/<download_format:fileformat>/<gitsha:hexsha>/",
        FileDownloadView.as_view(),
        name="download_project_at_hash",
    ),
]

urlpatterns: list[URLPattern | URLResolver] = [
    path("", ProjectApiView.as_view(), name="project_api"),
    path("<uuid:id>/", include(project_base_urlpatterns)),
]
