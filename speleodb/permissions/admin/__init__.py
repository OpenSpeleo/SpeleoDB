# -*- coding: utf-8 -*-

"""Admin module for Django."""

from __future__ import annotations

from speleodb.permissions.admin.cylinder_fleet import CylinderFleetUserPermissionAdmin
from speleodb.permissions.admin.experiment import ExperimentUserPermissionAdmin
from speleodb.permissions.admin.landmark_collection import (
    LandmarkCollectionUserPermissionAdmin,
)
from speleodb.permissions.admin.network import (
    SurfaceMonitoringNetworkUserPermissionAdmin,
)
from speleodb.permissions.admin.project import PermissionAdmin
from speleodb.permissions.admin.sensor_fleet import SensorFleetUserPermissionAdmin

__all__ = [
    "CylinderFleetUserPermissionAdmin",
    "ExperimentUserPermissionAdmin",
    "LandmarkCollectionUserPermissionAdmin",
    "PermissionAdmin",
    "SensorFleetUserPermissionAdmin",
    "SurfaceMonitoringNetworkUserPermissionAdmin",
]
