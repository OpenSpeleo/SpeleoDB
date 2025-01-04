#!/usr/bin/env python
# -*- coding: utf-8 -*-

from django.urls import path

from speleodb.git_proxy.views import InfoRefsView
from speleodb.git_proxy.views import ReadServiceView
from speleodb.git_proxy.views import WriteServiceView

app_name = "git_proxy"


urlpatterns = [
    path(
        "<uuid:id>.git/info/<str:command>",
        InfoRefsView.as_view(),
        name="git_info",
    ),
    path(
        "<uuid:id>.git/git-upload-pack",
        ReadServiceView.as_view(),
        name="git_service_read",
    ),
    path(
        "<uuid:id>.git/git-receive-pack",
        WriteServiceView.as_view(),
        name="git_service_write",
    ),
]
