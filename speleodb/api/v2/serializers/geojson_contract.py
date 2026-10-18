"""Wire shapes emitted by the custom GeoJSON serializer representations."""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

from speleodb.common.enums import SubSurfaceStationType
from speleodb.gis.models import Landmark


class PointGeometrySerializer(serializers.Serializer[dict[str, Any]]):
    type = serializers.ChoiceField(choices=["Point"])
    coordinates = serializers.ListField(
        child=serializers.FloatField(), min_length=2, max_length=2
    )


class StationTagSummarySerializer(serializers.Serializer[dict[str, Any]]):
    id = serializers.UUIDField()
    name = serializers.CharField()
    color = serializers.CharField()


class StationFeaturePropertiesSerializer(serializers.Serializer[dict[str, Any]]):
    name = serializers.CharField()
    description = serializers.CharField()
    created_by = serializers.CharField()
    creation_date = serializers.DateTimeField()
    modified_date = serializers.DateTimeField()
    station_type = serializers.ChoiceField(choices=["subsurface", "surface"])
    project = serializers.UUIDField(allow_null=True)
    network = serializers.UUIDField(allow_null=True)
    tag = StationTagSummarySerializer(allow_null=True)
    type = serializers.ChoiceField(
        choices=SubSurfaceStationType.choices, allow_null=True
    )


class StationFeatureSerializer(serializers.Serializer[dict[str, Any]]):
    id = serializers.UUIDField()
    type = serializers.ChoiceField(choices=["Feature"])
    geometry = PointGeometrySerializer()
    properties: serializers.Field[Any, Any, Any, Any] = (
        StationFeaturePropertiesSerializer()
    )


class ExplorationLeadFeaturePropertiesSerializer(
    serializers.Serializer[dict[str, Any]]
):
    description = serializers.CharField()
    created_by = serializers.CharField()
    creation_date = serializers.DateTimeField()
    modified_date = serializers.DateTimeField()
    project = serializers.UUIDField()


class ExplorationLeadFeatureSerializer(StationFeatureSerializer):
    properties = ExplorationLeadFeaturePropertiesSerializer()


class LandmarkFeaturePropertiesSerializer(serializers.Serializer[dict[str, Any]]):
    name = serializers.CharField()
    description = serializers.CharField()
    icon = serializers.ChoiceField(choices=Landmark.Icon.choices)
    collection = serializers.UUIDField()
    collection_name = serializers.CharField()
    collection_type = serializers.CharField()
    collection_color = serializers.CharField()
    is_personal_collection = serializers.BooleanField()
    created_by = serializers.CharField()
    creation_date = serializers.DateTimeField(allow_null=True)
    can_write = serializers.BooleanField()
    can_delete = serializers.BooleanField()


class LandmarkFeatureSerializer(StationFeatureSerializer):
    properties = LandmarkFeaturePropertiesSerializer()


class CylinderInstallFeaturePropertiesSerializer(
    serializers.Serializer[dict[str, Any]]
):
    id = serializers.UUIDField()
    cylinder_id = serializers.UUIDField()
    cylinder_name = serializers.CharField()
    cylinder_serial = serializers.CharField()
    fleet_id = serializers.UUIDField()
    fleet_name = serializers.CharField()
    project_id = serializers.UUIDField(allow_null=True)
    project_name = serializers.CharField(allow_null=True)
    location_name = serializers.CharField()
    install_date = serializers.DateField(allow_null=True)
    install_user = serializers.CharField()
    distance_from_entry = serializers.FloatField(allow_null=True)
    unit_system = serializers.CharField()
    status = serializers.CharField()
    o2_percentage = serializers.FloatField()
    he_percentage = serializers.FloatField()
    pressure = serializers.IntegerField()
    pressure_unit_system = serializers.CharField()


class CylinderInstallFeatureSerializer(StationFeatureSerializer):
    properties = CylinderInstallFeaturePropertiesSerializer()


class ExperimentRecordFeatureSerializer(StationFeatureSerializer):
    # Experiment field UUIDs are user-defined keys; values depend on that
    # experiment's field definitions rather than a fixed global object shape.
    properties = serializers.DictField(child=serializers.JSONField())
