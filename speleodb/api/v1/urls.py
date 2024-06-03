#!/usr/bin/env python
# -*- coding: utf-8 -*-

from django.urls import path
from django.urls import re_path

from speleodb.api.v1.views import CreateProjectApiView
from speleodb.api.v1.views import FileDownloadView
from speleodb.api.v1.views import FileUploadView
from speleodb.api.v1.views import ProjectAcquireApiView
from speleodb.api.v1.views import ProjectApiView
from speleodb.api.v1.views import ProjectListApiView
from speleodb.api.v1.views import ProjectReleaseApiView

app_name = "v1"

uuid_regex = "[0-9a-fA-F]{8}\\b-[0-9a-fA-F]{4}\\b-[0-9a-fA-F]{4}\\b-[0-9a-fA-F]{4}\\b-[0-9a-fA-F]{12}"  # noqa: E501

urlpatterns = [
    # ========================== Public API Routes ========================== #
    # ================== Authentication Required API Routes ================= #
    path("project/", CreateProjectApiView.as_view(), name="create_project"),
    path("project/<uuid:id>/", ProjectApiView.as_view(), name="get_one_project"),
    path(
        "project/<uuid:id>/acquire/",
        ProjectAcquireApiView.as_view(),
        name="acquire_project",
    ),
    path(
        "project/<uuid:id>/release/",
        ProjectReleaseApiView.as_view(),
        name="release_project",
    ),
    path("project/<uuid:id>/upload/", FileUploadView.as_view(), name="upload_project"),
    path(
        "project/<uuid:id>/download/",
        FileDownloadView.as_view(),
        name="download_project",
    ),
    re_path(
        rf"project/(?P<id>{uuid_regex})/download/(?P<commit_sha1>[0-9a-fA-F]{{6,40}})/$",
        FileDownloadView.as_view(),
        name="download_project_at_hash",
    ),
    path("projects/", ProjectListApiView.as_view(), name="list_all_projects"),
    # ================ Private API Routes - API KEY REQUIRED ================ #
]
