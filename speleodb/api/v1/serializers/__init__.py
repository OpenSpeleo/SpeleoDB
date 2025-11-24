# -*- coding: utf-8 -*-

from __future__ import annotations

from speleodb.api.v1.serializers.announcement import PublicAnnoucementSerializer
from speleodb.api.v1.serializers.authtoken import AuthTokenSerializer
from speleodb.api.v1.serializers.experiment import ExperimentRecordGISSerializer
from speleodb.api.v1.serializers.experiment import ExperimentRecordSerializer
from speleodb.api.v1.serializers.experiment import ExperimentSerializer
from speleodb.api.v1.serializers.file import UploadSerializer
from speleodb.api.v1.serializers.gis_view import GISViewCreateUpdateSerializer
from speleodb.api.v1.serializers.gis_view import GISViewProjectInputSerializer
from speleodb.api.v1.serializers.gis_view import GISViewProjectSerializer
from speleodb.api.v1.serializers.gis_view import GISViewSerializer
from speleodb.api.v1.serializers.git import GitCommitListSerializer
from speleodb.api.v1.serializers.git import GitCommitSerializer
from speleodb.api.v1.serializers.git import GitFileListSerializer
from speleodb.api.v1.serializers.git import GitFileSerializer
from speleodb.api.v1.serializers.password import PasswordChangeSerializer
from speleodb.api.v1.serializers.permissions import (
    ExperimentUserPermissionListSerializer,
)
from speleodb.api.v1.serializers.permissions import ExperimentUserPermissionSerializer
from speleodb.api.v1.serializers.permissions import ProjectTeamPermissionListSerializer
from speleodb.api.v1.serializers.permissions import ProjectTeamPermissionSerializer
from speleodb.api.v1.serializers.permissions import ProjectUserPermissionListSerializer
from speleodb.api.v1.serializers.permissions import ProjectUserPermissionSerializer
from speleodb.api.v1.serializers.plugin_release import PluginReleaseSerializer
from speleodb.api.v1.serializers.project import ProjectGeoJSONFileSerializer
from speleodb.api.v1.serializers.project import ProjectSerializer
from speleodb.api.v1.serializers.project import ProjectWithGeoJsonSerializer
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
from speleodb.api.v1.serializers.sensor_fleet import SensorFleetListSerializer
from speleodb.api.v1.serializers.sensor_fleet import SensorFleetSerializer
from speleodb.api.v1.serializers.sensor_fleet import SensorFleetUserPermissionSerializer
from speleodb.api.v1.serializers.sensor_fleet import SensorInstallSerializer
from speleodb.api.v1.serializers.sensor_fleet import SensorSerializer
from speleodb.api.v1.serializers.team import SurveyTeamListSerializer
from speleodb.api.v1.serializers.team import SurveyTeamMembershipListSerializer
from speleodb.api.v1.serializers.team import SurveyTeamMembershipSerializer
from speleodb.api.v1.serializers.team import SurveyTeamSerializer
from speleodb.api.v1.serializers.user import UserSerializer

__all__ = [
    "AuthTokenSerializer",
    "ExperimentRecordGISSerializer",
    "ExperimentRecordSerializer",
    "ExperimentSerializer",
    "ExperimentUserPermissionListSerializer",
    "ExperimentUserPermissionSerializer",
    "GISViewCreateUpdateSerializer",
    "GISViewDataSerializer",
    "GISViewProjectInputSerializer",
    "GISViewProjectSerializer",
    "GISViewSerializer",
    "GitCommitListSerializer",
    "GitCommitSerializer",
    "GitFileListSerializer",
    "GitFileSerializer",
    "PasswordChangeSerializer",
    "PluginReleaseSerializer",
    "ProjectGeoJSONCommitSerializer",
    "ProjectGeoJSONFileSerializer",
    "ProjectSerializer",
    "ProjectTeamPermissionListSerializer",
    "ProjectTeamPermissionSerializer",
    "ProjectUserPermissionListSerializer",
    "ProjectUserPermissionSerializer",
    "ProjectWithGeoJsonSerializer",
    "PublicAnnoucementSerializer",
    "SensorFleetListSerializer",
    "SensorFleetSerializer",
    "SensorFleetUserPermissionSerializer",
    "SensorInstallSerializer",
    "SensorSerializer",
    "SurveyTeamListSerializer",
    "SurveyTeamMembershipListSerializer",
    "SurveyTeamMembershipSerializer",
    "SurveyTeamSerializer",
    "TeamRequestSerializer",
    "TeamRequestWithProjectLevelSerializer",
    "UploadSerializer",
    "UserRequestSerializer",
    "UserRequestWithTeamRoleSerializer",
    "UserSerializer",
]
