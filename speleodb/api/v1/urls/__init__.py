# -*- coding: utf-8 -*-

from __future__ import annotations

from django.urls import URLPattern
from django.urls import URLResolver
from django.urls import include
from django.urls import path

from speleodb.api.v1.urls.experiment import urlpatterns as experiment_urlpatterns
from speleodb.api.v1.urls.experiment_records import (
    urlpatterns as experiment_record_urlpatterns,
)
from speleodb.api.v1.urls.exploration_lead import (
    urlpatterns as exploration_lead_urlpatterns,
)
from speleodb.api.v1.urls.file_import import urlpatterns as file_import_urlpatterns
from speleodb.api.v1.urls.gis import urlpatterns as gis_urlpatterns
from speleodb.api.v1.urls.gis_view import urlpatterns as gis_view_urlpatterns
from speleodb.api.v1.urls.gps_track import urlpatterns as gps_track_urlpatterns
from speleodb.api.v1.urls.landmark import urlpatterns as landmark_urlpatterns
from speleodb.api.v1.urls.log_entry import urlpatterns as log_entry_urlpatterns
from speleodb.api.v1.urls.project import urlpatterns as project_urlpatterns
from speleodb.api.v1.urls.resource import urlpatterns as resource_urlpatterns
from speleodb.api.v1.urls.sensor import urlpatterns as sensor_urlpatterns
from speleodb.api.v1.urls.sensor_fleet import urlpatterns as sensor_fleet_urlpatterns
from speleodb.api.v1.urls.station import urlpatterns as station_urlpatterns
from speleodb.api.v1.urls.station_tag import urlpatterns as station_tag_urlpatterns
from speleodb.api.v1.urls.surface_network import (
    urlpatterns as surface_network_urlpatterns,
)
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
    path("experiments/", include(experiment_urlpatterns)),
    path("experiment_records/", include(experiment_record_urlpatterns)),
    path("exploration-leads/", include(exploration_lead_urlpatterns)),
    path("gis-ogc/", include((gis_urlpatterns, "gis-ogc"), namespace="gis-ogc")),
    path("gis_view/", include(gis_view_urlpatterns)),
    path("gps_tracks/", include(gps_track_urlpatterns)),
    path("import/", include(file_import_urlpatterns)),
    path("logs/", include(log_entry_urlpatterns)),
    path("landmarks/", include(landmark_urlpatterns)),
    path("projects/", include(project_urlpatterns)),
    path("resources/", include(resource_urlpatterns)),
    path("sensor-fleets/", include(sensor_fleet_urlpatterns)),
    path("sensors/", include(sensor_urlpatterns)),
    path("stations/", include(station_urlpatterns)),
    path("station_tags/", include(station_tag_urlpatterns)),
    path("surface-networks/", include(surface_network_urlpatterns)),
    path("teams/", include(team_urlpatterns)),
    path("tools/", include(tool_urlpatterns)),
    path("user/", include(user_urlpatterns)),
]
