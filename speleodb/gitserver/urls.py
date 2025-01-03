#!/usr/bin/env python
# -*- coding: utf-8 -*-

from django.urls import path

from speleodb.gitserver.views import GitService
from speleodb.gitserver.views import InfoRefsView
from speleodb.gitserver.views import ServiceView
from speleodb.utils.url_converters import BaseChoicesConverter
from speleodb.utils.url_converters import register_converter

app_name = "gitserver"


@register_converter("git_service")
class UploadFormatsConverter(BaseChoicesConverter):
    choices = [service.value for service in GitService]


urlpatterns = [
    path(
        "<uuid:id>.git/info/<str:command>",
        InfoRefsView.as_view(),
        name="git_info",
    ),
    path(
        "<uuid:id>.git/<git_service:service>",
        ServiceView.as_view(),
        name="git_service",
    ),
]
