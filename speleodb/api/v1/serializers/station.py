# -*- coding: utf-8 -*-

from __future__ import annotations

import contextlib
from decimal import InvalidOperation
from typing import Any
from typing import ClassVar
from typing import TypeVar

from django.conf import settings
from django.core.exceptions import ValidationError
from geojson import Feature  # type: ignore[attr-defined]
from geojson import Point  # type: ignore[attr-defined]
from rest_framework import serializers

from speleodb.common.enums import StationResourceType
from speleodb.gis.models import Station
from speleodb.gis.models import StationResource
from speleodb.gis.models import SubSurfaceStation
from speleodb.gis.models import SurfaceStation
from speleodb.utils.gps_utils import format_coordinate
from speleodb.utils.serializer_mixins import SanitizedFieldsMixin

# Type variable for station types
T = TypeVar("T", bound=Station)


class StationResourceSerializer(
    SanitizedFieldsMixin, serializers.ModelSerializer[StationResource]
):
    sanitized_fields: ClassVar[list[str]] = ["title", "description", "text_content"]
    """Serializer for StationResource model."""

    class Meta:
        model = StationResource
        fields = [
            "id",
            "created_by",
            "creation_date",
            "description",
            "file",
            "miniature",
            "modified_date",
            "resource_type",
            "station",
            "text_content",
            "title",
        ]

        read_only_fields = [
            "id",
            "created_by",
            "creation_date",
            "modified_date",
            "station",
        ]

    def validate_resource_type(self, value: str) -> str:
        """Prevent resource_type from being changed during updates."""
        if self.instance and self.instance.resource_type != value:
            raise serializers.ValidationError(
                "Resource type cannot be changed once created."
            )

        return value

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """Validate that file-based resources have files and text-based have text."""
        # Get resource_type - if updating, use existing if not provided
        resource_type = attrs.get("resource_type")

        if resource_type:
            if isinstance(resource_type, str):
                resource_type = StationResourceType.from_str(resource_type)

        elif self.instance:
            resource_type = self.instance.resource_type

        file_field = attrs.get("file")
        text_content = attrs.get("text_content")

        match resource_type:
            case (
                StationResourceType.PHOTO
                | StationResourceType.VIDEO
                | StationResourceType.DOCUMENT
            ):
                # For updates, only validate if file is being changed
                if self.instance and not file_field:
                    with contextlib.suppress(KeyError):
                        del attrs["file"]
                    return attrs

                # Validate file size (max 5MBs)
                if file_field:
                    max_size = (
                        settings.DJANGO_UPLOAD_INDIVIDUAL_FILESIZE_MB_LIMIT
                        * 1024
                        * 1024
                    )
                    if file_field.size > max_size:
                        raise serializers.ValidationError(
                            {"file": "File size cannot exceed 5MB."}
                        )

            case StationResourceType.NOTE:
                # For updates, check if text_content is being updated
                if self.instance and "text_content" not in attrs:
                    return attrs

                # For new resources, text_content is required
                if not text_content:
                    raise serializers.ValidationError(
                        f"Resource type '{resource_type}' requires text content."
                    )

            case _:
                raise ValidationError(f"Unknown value received: `{resource_type}`")

        return attrs


class BaseStationSerializerMixin:
    """
    Mixin providing shared serializer logic for Station subclasses.

    Provides:
    - Tag serialization (get_tag method)
    - Coordinate rounding (to_internal_value, to_representation)
    """

    def get_tag(self, obj: Station) -> dict[str, Any] | None:
        """Get tag as a dictionary."""
        # Handle case where obj is validated_data dict (during error handling)
        if isinstance(obj, dict):
            return None

        if obj.tag:
            return {
                "id": str(obj.tag.id),
                "name": obj.tag.name,
                "color": obj.tag.color,
            }
        return None

    def to_internal_value(self, data: dict[str, Any]) -> Any:
        """Override to round coordinates before validation."""

        # Data is immutable - need to copy
        data = data.copy()

        # Round coordinates if they exist in the data
        if "latitude" in data and data["latitude"] is not None:
            with contextlib.suppress(ValueError, TypeError, InvalidOperation):
                # Let the field validation handle the error
                data["latitude"] = format_coordinate(data["latitude"])

        if "longitude" in data and data["longitude"] is not None:
            with contextlib.suppress(ValueError, TypeError, InvalidOperation):
                # Let the field validation handle the error
                data["longitude"] = format_coordinate(data["longitude"])

        return super().to_internal_value(data)  # type: ignore[misc]

    def to_representation(self, instance: Station) -> dict[str, Any]:
        """Ensure coordinates are formatted without trailing zeros."""
        data = super().to_representation(instance)  # type: ignore[misc]

        if data.get("latitude") is not None:
            data["latitude"] = format_coordinate(data["latitude"])

        if data.get("longitude") is not None:
            data["longitude"] = format_coordinate(data["longitude"])

        return data  # type: ignore[no-any-return]


class StationSerializer(
    SanitizedFieldsMixin,
    BaseStationSerializerMixin,
    serializers.ModelSerializer[Station],
):
    """Serializer for base Station model (read operations)."""

    sanitized_fields: ClassVar[list[str]] = ["name", "description"]

    # Override tag field to return nested representation
    tag = serializers.SerializerMethodField()

    class Meta:
        model = Station
        fields = "__all__"

        read_only_fields = [
            "id",
            "created_by",
            "creation_date",
            "modified_date",
            "tag",
        ]


class StationWithResourcesSerializer(StationSerializer):
    """Serializer for stations with resources."""

    resources = StationResourceSerializer(many=True, read_only=True)


class SubSurfaceStationSerializer(
    SanitizedFieldsMixin,
    BaseStationSerializerMixin,
    serializers.ModelSerializer[SubSurfaceStation],
):
    """Serializer for SubSurfaceStation model (has project field)."""

    sanitized_fields: ClassVar[list[str]] = ["name", "description"]

    # Override tag field to return nested representation
    tag = serializers.SerializerMethodField()

    class Meta:
        model = SubSurfaceStation
        fields = "__all__"

        read_only_fields = [
            "id",
            "created_by",
            "creation_date",
            "modified_date",
            "project",
            "tag",
        ]

    def validate_type(self, value: str) -> str:
        """Prevent type from being changed during updates (only settable on
        creation)."""
        if self.instance is not None:
            # This is an update - only allow if type matches existing value
            if self.instance.type != value:
                raise serializers.ValidationError(
                    "Station type cannot be changed once created."
                )
        return value


class SubSurfaceStationWithResourcesSerializer(SubSurfaceStationSerializer):
    """Serializer for subsurface stations with resources."""

    resources = StationResourceSerializer(many=True, read_only=True)


class SurfaceStationSerializer(
    SanitizedFieldsMixin,
    BaseStationSerializerMixin,
    serializers.ModelSerializer[SurfaceStation],
):
    """Serializer for SurfaceStation model (has network field)."""

    sanitized_fields: ClassVar[list[str]] = ["name", "description"]

    # Override tag field to return nested representation
    tag = serializers.SerializerMethodField()

    class Meta:
        model = SurfaceStation
        fields = "__all__"

        read_only_fields = [
            "id",
            "created_by",
            "creation_date",
            "modified_date",
            "network",
            "tag",
        ]


class SurfaceStationWithResourcesSerializer(SurfaceStationSerializer):
    """Serializer for surface stations with resources."""

    resources = StationResourceSerializer(many=True, read_only=True)


class StationGeoJSONSerializer(serializers.ModelSerializer[Station]):
    """Map serializer for stations - returns GeoJSON-like format.

    Note: The `type` field is specific to SubSurfaceStation and is added
    dynamically in to_representation(), not declared in fields.
    """

    class Meta:
        model = Station
        fields = [
            "id",
            "name",
            "description",
            "latitude",
            "longitude",
            "created_by",
            "creation_date",
            "modified_date",
            "tag",
        ]

    def to_representation(self, instance: Station) -> dict[str, Any]:
        """Convert to GeoJSON Feature format."""
        # Get tag details if exists
        tag = None
        if instance.tag:
            tag = {
                "id": str(instance.tag.id),
                "name": instance.tag.name,
                "color": instance.tag.color,
            }

        # Determine station type for frontend identification
        station_type = "unknown"
        subsurf_station_type = None

        match instance:
            case SubSurfaceStation():
                station_type = "subsurface"
                subsurf_station_type = instance.type

            case SurfaceStation():
                station_type = "surface"

            case _:
                raise TypeError(f"Unexpected Station type received: {type(instance)}")

        return Feature(  # type: ignore[no-untyped-call]
            id=str(instance.id),
            geometry=Point((float(instance.longitude), float(instance.latitude))),  # type: ignore[no-untyped-call]
            properties={
                "name": instance.name,
                "description": instance.description,
                "created_by": instance.created_by,
                "creation_date": instance.creation_date.isoformat(),
                "modified_date": instance.modified_date.isoformat(),
                "station_type": station_type,
                "project": (
                    str(instance.project.id)
                    if isinstance(instance, SubSurfaceStation)
                    else None
                ),
                "network": (
                    str(instance.network.id)
                    if isinstance(instance, SurfaceStation)
                    else None
                ),
                "tag": tag,
                "type": subsurf_station_type,  # SubSurfaceStationType
            },
        )
