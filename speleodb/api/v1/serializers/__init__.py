# -*- coding: utf-8 -*-

from __future__ import annotations

from speleodb.api.v1.serializers.announcement import PublicAnnoucementSerializer
from speleodb.api.v1.serializers.authtoken import AuthTokenSerializer
from speleodb.api.v1.serializers.experiment import ExperimentRecordGISSerializer
from speleodb.api.v1.serializers.experiment import ExperimentRecordSerializer
from speleodb.api.v1.serializers.experiment import ExperimentSerializer
from speleodb.api.v1.serializers.file import UploadSerializer
from speleodb.api.v1.serializers.gis_view import GISProjectViewInputSerializer
from speleodb.api.v1.serializers.gis_view import GISProjectViewSerializer
from speleodb.api.v1.serializers.gis_view import GISViewCreateUpdateSerializer
from speleodb.api.v1.serializers.gis_view import GISViewDataSerializer
from speleodb.api.v1.serializers.gis_view import GISViewSerializer
from speleodb.api.v1.serializers.git import GitCommitSerializer
from speleodb.api.v1.serializers.git import GitFileSerializer
from speleodb.api.v1.serializers.gps_track import GPSTrackSerializer
from speleodb.api.v1.serializers.gps_track import GPSTrackWithFileSerializer
from speleodb.api.v1.serializers.landmark import LandmarkGeoJSONSerializer
from speleodb.api.v1.serializers.landmark import LandmarkSerializer
from speleodb.api.v1.serializers.log_entry import StationLogEntrySerializer
from speleodb.api.v1.serializers.password import PasswordChangeSerializer
from speleodb.api.v1.serializers.permissions import ExperimentUserPermissionSerializer
from speleodb.api.v1.serializers.permissions import ProjectTeamPermissionSerializer
from speleodb.api.v1.serializers.permissions import ProjectUserPermissionSerializer
from speleodb.api.v1.serializers.plugin_release import PluginReleaseSerializer
from speleodb.api.v1.serializers.project import ProjectGeoJSONFileSerializer
from speleodb.api.v1.serializers.project import ProjectSerializer
from speleodb.api.v1.serializers.project import ProjectWithGeoJsonSerializer
from speleodb.api.v1.serializers.project_commit import ProjectCommitSerializer
from speleodb.api.v1.serializers.project_geojson_commit import (
    ProjectGeoJSONCommitSerializer,
)
from speleodb.api.v1.serializers.request_serializers import TeamRequestSerializer
from speleodb.api.v1.serializers.request_serializers import (
    TeamRequestWithProjectLevelSerializer,
)
from speleodb.api.v1.serializers.request_serializers import UserRequestSerializer
from speleodb.api.v1.serializers.request_serializers import (
    UserRequestWithTeamRoleSerializer,
)
from speleodb.api.v1.serializers.sensor_fleet import SensorFleetSerializer
from speleodb.api.v1.serializers.sensor_fleet import SensorFleetUserPermissionSerializer
from speleodb.api.v1.serializers.sensor_fleet import SensorFleetWithPermSerializer
from speleodb.api.v1.serializers.sensor_fleet import SensorInstallSerializer
from speleodb.api.v1.serializers.sensor_fleet import SensorSerializer
from speleodb.api.v1.serializers.team import SurveyTeamMembershipSerializer
from speleodb.api.v1.serializers.team import SurveyTeamSerializer
from speleodb.api.v1.serializers.user import UserSerializer

__all__ = [
    "AuthTokenSerializer",
    "ExperimentRecordGISSerializer",
    "ExperimentRecordSerializer",
    "ExperimentSerializer",
    "ExperimentUserPermissionSerializer",
    "GISProjectViewInputSerializer",
    "GISProjectViewSerializer",
    "GISViewCreateUpdateSerializer",
    "GISViewDataSerializer",
    "GISViewSerializer",
    "GPSTrackSerializer",
    "GPSTrackWithFileSerializer",
    "GitCommitSerializer",
    "GitFileSerializer",
    "LandmarkGeoJSONSerializer",
    "LandmarkSerializer",
    "PasswordChangeSerializer",
    "PluginReleaseSerializer",
    "ProjectCommitSerializer",
    "ProjectGeoJSONCommitSerializer",
    "ProjectGeoJSONFileSerializer",
    "ProjectSerializer",
    "ProjectTeamPermissionSerializer",
    "ProjectUserPermissionSerializer",
    "ProjectWithGeoJsonSerializer",
    "PublicAnnoucementSerializer",
    "SensorFleetSerializer",
    "SensorFleetUserPermissionSerializer",
    "SensorFleetWithPermSerializer",
    "SensorInstallSerializer",
    "SensorSerializer",
    "StationLogEntrySerializer",
    "SurveyTeamMembershipSerializer",
    "SurveyTeamSerializer",
    "TeamRequestSerializer",
    "TeamRequestWithProjectLevelSerializer",
    "UploadSerializer",
    "UserRequestSerializer",
    "UserRequestWithTeamRoleSerializer",
    "UserSerializer",
]
