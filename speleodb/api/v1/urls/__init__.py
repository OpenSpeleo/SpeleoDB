#!/usr/bin/env python
# -*- coding: utf-8 -*-

from django.urls import include
from django.urls import path

from speleodb.api.v1.urls.project import urlpatterns as project_urlpatterns
from speleodb.api.v1.urls.team import urlpatterns as team_urlpatterns
from speleodb.api.v1.urls.user import urlpatterns as user_urlpatterns

app_name = "v1"

urlpatterns = [
    path("projects/", include(project_urlpatterns)),
    path("teams/", include(team_urlpatterns)),
    path("user/", include(user_urlpatterns)),
]
