"""Small transport payloads shared by API schema declarations."""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

from speleodb.api.v2.serializers.cylinder_fleet import CylinderInstallSerializer
from speleodb.api.v2.serializers.project import ProjectSerializer
from speleodb.api.v2.serializers.sensor_fleet import SensorFleetSerializer
from speleodb.api.v2.serializers.sensor_fleet import SensorInstallSerializer
from speleodb.api.v2.serializers.sensor_fleet import SensorSerializer
from speleodb.common.enums import PermissionLevel
from speleodb.gis.gis_layer_processing.errors import ProcessingErrorCode
from speleodb.surveys.models import Project
from speleodb.utils.serializer_fields import CustomChoiceField


class DirectUserPermissionRequestSerializer(serializers.Serializer[dict[str, Any]]):
    user = serializers.EmailField()
    level = CustomChoiceField(PermissionLevel.choices)


class NonWebViewerPermissionRequestSerializer(DirectUserPermissionRequestSerializer):
    level = CustomChoiceField(PermissionLevel.choices_no_webviewer)


class SensorFleetCreateRequestSerializer(SensorFleetSerializer):
    sensors = SensorSerializer(many=True, required=False, write_only=True)


class SensorInstallCreateRequestSerializer(SensorInstallSerializer):
    class Meta(SensorInstallSerializer.Meta):
        read_only_fields = [
            *SensorInstallSerializer.Meta.read_only_fields,
            "install_user",
        ]


class CylinderInstallCreateRequestSerializer(CylinderInstallSerializer):
    project = serializers.PrimaryKeyRelatedField(queryset=Project.objects.all())

    class Meta(CylinderInstallSerializer.Meta):
        read_only_fields = [
            *CylinderInstallSerializer.Meta.read_only_fields,
            "install_user",
        ]


class IdentifierSerializer(serializers.Serializer[dict[str, Any]]):
    id = serializers.UUIDField()


class MessageSerializer(serializers.Serializer[dict[str, Any]]):
    message = serializers.CharField()


class GISProcessingErrorSerializer(serializers.Serializer[dict[str, Any]]):
    error = serializers.CharField()
    code = serializers.ChoiceField(
        choices=[value.value for value in ProcessingErrorCode]
    )
    details = serializers.DictField()


class KMLNoEligiblePlacesErrorSerializer(serializers.Serializer[dict[str, Any]]):
    error = serializers.CharField()
    code = serializers.ChoiceField(choices=["KML_NO_ELIGIBLE_PLACES"])


class AuthTokenResponseSerializer(serializers.Serializer[dict[str, Any]]):
    user = serializers.EmailField()
    token = serializers.CharField()


class ProjectUploadRequestSerializer(serializers.Serializer[dict[str, Any]]):
    artifact = serializers.ListField(child=serializers.FileField(), min_length=1)
    message = serializers.CharField()


class ActiveMutexSerializer(serializers.Serializer[dict[str, Any]]):
    user = serializers.EmailField()
    creation_date = serializers.DateTimeField()
    modified_date = serializers.DateTimeField()


class ProjectUploadResponseSerializer(serializers.Serializer[dict[str, Any]]):
    files = serializers.ListField(child=serializers.CharField())
    message = serializers.CharField()
    hexsha = serializers.CharField()
    geojson_status = serializers.CharField()
    browser_url = serializers.CharField(allow_null=True)
    project = ProjectSerializer()
