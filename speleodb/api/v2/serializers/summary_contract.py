"""Concrete dictionaries emitted by serializer method fields."""

from typing import Any

from rest_framework import serializers

from speleodb.common.enums import UnitSystem


class NamedProjectSummarySerializer(serializers.Serializer[dict[str, Any]]):
    id = serializers.UUIDField()
    name = serializers.CharField()


class SensorStationSummarySerializer(serializers.Serializer[dict[str, Any]]):
    id = serializers.UUIDField()
    name = serializers.CharField()
    latitude = serializers.CharField()
    longitude = serializers.CharField()
    project = NamedProjectSummarySerializer(allow_null=True)


class SensorActiveInstallSerializer(serializers.Serializer[dict[str, Any]]):
    id = serializers.UUIDField()
    station = SensorStationSummarySerializer()
    expiracy_memory_date = serializers.DateField(allow_null=True)
    expiracy_battery_date = serializers.DateField(allow_null=True)


class CylinderActiveInstallSerializer(serializers.Serializer[dict[str, Any]]):
    id = serializers.UUIDField()
    location_name = serializers.CharField()
    latitude = serializers.CharField()
    longitude = serializers.CharField()
    distance_from_entry = serializers.IntegerField(allow_null=True)
    unit_system = serializers.ChoiceField(choices=UnitSystem.choices)
    install_date = serializers.DateField(allow_null=True)


class CylinderPressureCheckSummarySerializer(serializers.Serializer[dict[str, Any]]):
    id = serializers.UUIDField()
    pressure = serializers.IntegerField(min_value=0)
    unit_system = serializers.ChoiceField(choices=UnitSystem.choices)
    user = serializers.CharField(allow_blank=True)
    creation_date = serializers.DateTimeField()


class GitCommitFormatSerializer(serializers.Serializer[dict[str, Any]]):
    name = serializers.CharField()
    download_url = serializers.CharField()


class ExportNoticeSerializer(serializers.Serializer[dict[str, Any]]):
    category = serializers.CharField()
    id = serializers.CharField()
    name = serializers.CharField()
    reason = serializers.CharField()
    path = serializers.CharField(required=False)


class CompletedExportSummarySerializer(serializers.Serializer[dict[str, Any]]):
    omissions = ExportNoticeSerializer(many=True)
    notes = ExportNoticeSerializer(many=True)
    file_count = serializers.IntegerField(min_value=0)


class FailedExportSummarySerializer(serializers.Serializer[dict[str, Any]]):
    error = serializers.CharField()
