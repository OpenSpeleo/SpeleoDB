# -*- coding: utf-8 -*-

from django.urls import path

from speleodb.api.v1.views.media_storage import MediaPresignedUploadView
from speleodb.api.v1.views.media_storage import MediaSecureAccessView
from speleodb.api.v1.views.media_storage import MediaSignedUrlView

urlpatterns = [
    # Media File Upload
    path(
        "media/upload/",
        MediaPresignedUploadView.as_view(),
        name="media-upload",
    ),
    # Media Signed URL Generation (deprecated - use secure-access instead)
    path(
        "media/signed-url/",
        MediaSignedUrlView.as_view(),
        name="media-signed-url",
    ),
    # Media Secure File Access (recommended)
    path(
        "media/secure-access/",
        MediaSecureAccessView.as_view(),
        name="media-secure-access",
    ),
]
