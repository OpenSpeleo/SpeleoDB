# -*- coding: utf-8 -*-

"""Admin module for Django."""

from __future__ import annotations

from speleodb.gis.admin.experiment import ExperimentAdmin
from speleodb.gis.admin.experiment import ExperimentRecordAdmin
from speleodb.gis.admin.landmark import LandmarkAdmin
from speleodb.gis.admin.log import StationLogEntryAdmin
from speleodb.gis.admin.network import SurfaceMonitoringNetworkAdmin
from speleodb.gis.admin.project_geojson import ProjectGeoJSONAdmin
from speleodb.gis.admin.resource import StationResourceAdmin
from speleodb.gis.admin.sensor import SensorAdmin
from speleodb.gis.admin.sensor import SensorFleetAdmin
from speleodb.gis.admin.sensor import SensorInstallAdmin
from speleodb.gis.admin.station import SubSurfaceStationAdmin
from speleodb.gis.admin.tag import StationTagAdmin
from speleodb.gis.admin.view import GISViewAdmin
from speleodb.gis.admin.view import GISViewProjectAdmin

__all__ = [
    "ExperimentAdmin",
    "ExperimentRecordAdmin",
    "GISViewAdmin",
    "GISViewProjectAdmin",
    "LandmarkAdmin",
    "ProjectGeoJSONAdmin",
    "SensorAdmin",
    "SensorFleetAdmin",
    "SensorInstallAdmin",
    "StationLogEntryAdmin",
    "StationResourceAdmin",
    "StationTagAdmin",
    "SubSurfaceStationAdmin",
    "SurfaceMonitoringNetworkAdmin",
]
