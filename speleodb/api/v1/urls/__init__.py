# -*- coding: utf-8 -*-

from __future__ import annotations

from django.urls import URLPattern
from django.urls import URLResolver
from django.urls import include
from django.urls import path

from speleodb.api.v1.urls.log_entry import log_entry_urlpatterns
from speleodb.api.v1.urls.poi import urlpatterns as poi_urlpatterns
from speleodb.api.v1.urls.project import urlpatterns as project_urlpatterns
from speleodb.api.v1.urls.resource import resource_urlpatterns
from speleodb.api.v1.urls.station import station_urlpatterns
from speleodb.api.v1.urls.team import urlpatterns as team_urlpatterns
from speleodb.api.v1.urls.tools import urlpatterns as tool_urlpatterns
from speleodb.api.v1.urls.user import urlpatterns as user_urlpatterns
from speleodb.api.v1.views.announcement import PublicAnnouncementApiView
from speleodb.api.v1.views.plugin_release import PluginReleasesApiView

app_name = "v1"

urlpatterns: list[URLResolver | URLPattern] = [
    path(
        "announcements/",
        PublicAnnouncementApiView.as_view(),
        name="public-announcements",
    ),
    path(
        "plugin_releases/",
        PluginReleasesApiView.as_view(),
        name="plugin-releases",
    ),
    path("logs/", include(log_entry_urlpatterns)),
    path("points_of_interest/", include(poi_urlpatterns)),
    path("projects/", include(project_urlpatterns)),
    path("resources/", include(resource_urlpatterns)),
    path("stations/", include(station_urlpatterns)),
    path("teams/", include(team_urlpatterns)),
    path("tools/", include(tool_urlpatterns)),
    path("user/", include(user_urlpatterns)),
]
