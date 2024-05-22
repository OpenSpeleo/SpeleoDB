#!/usr/bin/env python
# -*- coding: utf-8 -*-

from django.urls import path
from django.urls import re_path

from speleodb.surveys.api.v1.views import CreateProjectApiView
from speleodb.surveys.api.v1.views import FileDownloadView
from speleodb.surveys.api.v1.views import FileUploadView
from speleodb.surveys.api.v1.views import ProjectAcquireApiView
from speleodb.surveys.api.v1.views import ProjectApiView
from speleodb.surveys.api.v1.views import ProjectListApiView
from speleodb.surveys.api.v1.views import ProjectReleaseApiView

uuid_regex = "[0-9a-fA-F]{8}\\b-[0-9a-fA-F]{4}\\b-[0-9a-fA-F]{4}\\b-[0-9a-fA-F]{4}\\b-[0-9a-fA-F]{12}"  # noqa: E501

urlpatterns = [
    # ========================== Public API Routes ========================== #
    # ================== Authentication Required API Routes ================= #
    path("project/", CreateProjectApiView.as_view()),
    path("project/<uuid:id>/", ProjectApiView.as_view()),
    path("project/<uuid:id>/acquire/", ProjectAcquireApiView.as_view()),
    path("project/<uuid:id>/release/", ProjectReleaseApiView.as_view()),
    path("project/<uuid:id>/update/", FileUploadView.as_view()),
    path("project/<uuid:id>/download/", FileDownloadView.as_view()),
    re_path(
        rf"project/(?P<id>{uuid_regex})/download/(?P<commit_sha1>[0-9a-fA-F]{{6,40}})/$",
        FileDownloadView.as_view(),
    ),
    path("projects/", ProjectListApiView.as_view()),
    # ================ Private API Routes - API KEY REQUIRED ================ #
]
