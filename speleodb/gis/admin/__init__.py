# -*- coding: utf-8 -*-

"""Admin module for Django."""

from __future__ import annotations

from speleodb.gis.admin.experiment import ExperimentAdmin
from speleodb.gis.admin.experiment import ExperimentRecordAdmin
from speleodb.gis.admin.experiment import ExperimentUserPermissionAdmin
from speleodb.gis.admin.log import LogEntryAdmin
from speleodb.gis.admin.network import MonitoringNetworkAdmin
from speleodb.gis.admin.network import MonitoringNetworkUserPermissionAdmin
from speleodb.gis.admin.point_of_interest import PointOfInterestAdmin
from speleodb.gis.admin.project_geojson import ProjectGeoJSONAdmin
from speleodb.gis.admin.resource import StationResourceAdmin
from speleodb.gis.admin.sensor import SensorAdmin
from speleodb.gis.admin.sensor import SensorFleetAdmin
from speleodb.gis.admin.sensor import SensorFleetUserPermissionAdmin
from speleodb.gis.admin.sensor import SensorInstallAdmin
from speleodb.gis.admin.station import StationAdmin
from speleodb.gis.admin.tag import StationTagAdmin
from speleodb.gis.admin.view import GISViewAdmin
from speleodb.gis.admin.view import GISViewProjectAdmin

__all__ = [
    "ExperimentAdmin",
    "ExperimentRecordAdmin",
    "ExperimentUserPermissionAdmin",
    "GISViewAdmin",
    "GISViewProjectAdmin",
    "LogEntryAdmin",
    "MonitoringNetworkAdmin",
    "MonitoringNetworkUserPermissionAdmin",
    "PointOfInterestAdmin",
    "ProjectGeoJSONAdmin",
    "SensorAdmin",
    "SensorFleetAdmin",
    "SensorFleetUserPermissionAdmin",
    "SensorInstallAdmin",
    "StationAdmin",
    "StationResourceAdmin",
    "StationTagAdmin",
]
