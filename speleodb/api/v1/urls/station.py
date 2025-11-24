# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import TYPE_CHECKING

from django.urls import include
from django.urls import path

from speleodb.api.v1.views.experiment import ExperimentRecordApiView
from speleodb.api.v1.views.log_entry import LogEntryApiView
from speleodb.api.v1.views.resource import StationResourceApiView
from speleodb.api.v1.views.sensor_fleet import StationSensorInstallApiView
from speleodb.api.v1.views.sensor_fleet import StationSensorInstallExportExcelApiView
from speleodb.api.v1.views.sensor_fleet import StationSensorInstallSpecificApiView
from speleodb.api.v1.views.station import StationsApiView
from speleodb.api.v1.views.station import StationsGeoJSONApiView
from speleodb.api.v1.views.station import StationSpecificApiView
from speleodb.api.v1.views.station_tag import StationTagsManageApiView

if TYPE_CHECKING:
    from django.urls import URLPattern
    from django.urls import URLResolver


station_urlpatterns: list[URLPattern] = [
    path("", StationSpecificApiView.as_view(), name="station-detail"),
    path(
        "resources/",
        StationResourceApiView.as_view(),
        name="station-resources",
    ),
    path("logs/", LogEntryApiView.as_view(), name="station-logs"),
    path("tags/", StationTagsManageApiView.as_view(), name="station-tags-manage"),
    path(
        "experiment/<uuid:exp_id>/records/",
        ExperimentRecordApiView.as_view(),
        name="experiment-records",
    ),
    path(
        "sensor-installs/",
        StationSensorInstallApiView.as_view(),
        name="station-sensor-installs",
    ),
    path(
        "sensor-installs/export/excel/",
        StationSensorInstallExportExcelApiView.as_view(),
        name="station-sensor-installs-export",
    ),
    path(
        "sensor-installs/<uuid:install_id>/",
        StationSensorInstallSpecificApiView.as_view(),
        name="station-sensor-install-detail",
    ),
]


urlpatterns: list[URLPattern | URLResolver] = [
    path("", StationsApiView.as_view(), name="stations"),
    path("geojson/", StationsGeoJSONApiView.as_view(), name="stations-geojson"),
    path("<uuid:id>/", include(station_urlpatterns)),
]
