# -*- coding: utf-8 -*-

from __future__ import annotations

from django.urls import URLPattern
from django.urls import URLResolver
from django.urls import include
from django.urls import path

from speleodb.api.v1.urls.project import urlpatterns as project_urlpatterns
from speleodb.api.v1.urls.team import urlpatterns as team_urlpatterns
from speleodb.api.v1.urls.user import urlpatterns as user_urlpatterns
from speleodb.api.v1.views.announcement import PublicAnnouncementApiView

app_name = "v1"

urlpatterns: list[URLResolver | URLPattern] = [
    path(
        "announcements/",
        PublicAnnouncementApiView.as_view(),
        name="public_announcements",
    ),
    path("projects/", include(project_urlpatterns)),
    path("teams/", include(team_urlpatterns)),
    path("user/", include(user_urlpatterns)),
]
