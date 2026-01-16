# -*- coding: utf-8 -*-

"""Admin module for Django."""

from __future__ import annotations

from speleodb.gis.admin.cylinder import CylinderAdmin
from speleodb.gis.admin.cylinder import CylinderFleetAdmin
from speleodb.gis.admin.cylinder import CylinderFleetUserPermissionAdmin
from speleodb.gis.admin.cylinder import CylinderInstallAdmin
from speleodb.gis.admin.cylinder import CylinderPressureCheckAdmin
from speleodb.gis.admin.experiment import ExperimentAdmin
from speleodb.gis.admin.experiment import ExperimentRecordAdmin
from speleodb.gis.admin.explo_lead import ExplorationLeadAdmin
from speleodb.gis.admin.gps_track import GPSTrackAdmin
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
from speleodb.gis.admin.view import GISProjectViewAdmin
from speleodb.gis.admin.view import GISViewAdmin

__all__ = [
    "CylinderAdmin",
    "CylinderFleetAdmin",
    "CylinderFleetUserPermissionAdmin",
    "CylinderInstallAdmin",
    "CylinderPressureCheckAdmin",
    "ExperimentAdmin",
    "ExperimentRecordAdmin",
    "ExplorationLeadAdmin",
    "GISProjectViewAdmin",
    "GISViewAdmin",
    "GPSTrackAdmin",
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
