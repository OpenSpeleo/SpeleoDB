#!/usr/bin/env python
# -*- coding: utf-8 -*-

from django.urls import re_path

from speleodb.api.v1.views.file import BlobDownloadView
from speleodb.api.v1.views.file import FileDownloadView
from speleodb.api.v1.views.file import FileUploadView
from speleodb.surveys.models import Format

uuid_regex = "[0-9a-fA-F]{8}\\b-[0-9a-fA-F]{4}\\b-[0-9a-fA-F]{4}\\b-[0-9a-fA-F]{4}\\b-[0-9a-fA-F]{12}"  # noqa: E501

down_formats_regex = (
    "(?P<fileformat>" + "|".join(Format.FileFormat.download_choices) + ")"
)
up_formats_regex = "(?P<fileformat>" + "|".join(Format.FileFormat.upload_choices) + ")"

urlpatterns = [
    re_path(
        rf"project/(?P<id>{uuid_regex})/upload/{up_formats_regex}/$",
        FileUploadView.as_view(),
        name="upload_project",
    ),
    re_path(
        rf"project/(?P<id>{uuid_regex})/download/blob/(?P<hexsha>[0-9a-fA-F]{{40}})/$",
        BlobDownloadView.as_view(),
        name="download_blob",
    ),
    re_path(
        rf"project/(?P<id>{uuid_regex})/download/{down_formats_regex}/$",
        FileDownloadView.as_view(),
        name="download_project",
    ),
    re_path(
        rf"project/(?P<id>{uuid_regex})/download/{down_formats_regex}/(?P<hexsha>[0-9a-fA-F]{{6,40}})/$",
        FileDownloadView.as_view(),
        name="download_project_at_hash",
    ),
]
