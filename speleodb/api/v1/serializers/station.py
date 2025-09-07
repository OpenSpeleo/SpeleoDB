# -*- coding: utf-8 -*-

from __future__ import annotations

import contextlib
from decimal import InvalidOperation
from typing import Any

from django.core.exceptions import ValidationError
from rest_framework import serializers

from speleodb.surveys.models import Station
from speleodb.surveys.models import StationResource
from speleodb.surveys.models.station import StationResourceType


def format_coordinate(value: Any) -> float:
    """Format a coordinate value to 7 decimal places"""
    return round(float(value), 7)


class StationResourceSerializer(serializers.ModelSerializer[StationResource]):
    """Serializer for StationResource model."""

    created_by = serializers.EmailField(source="created_by.email", read_only=True)
    file_url = serializers.URLField(source="get_file_url", read_only=True)
    miniature_url = serializers.URLField(source="get_miniature_url", read_only=True)

    class Meta:
        model = StationResource
        fields = [
            "id",
            "created_by",
            "creation_date",
            "description",
            "file",
            "file_url",
            "miniature_url",
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
            "file_url",
            "miniature_url",
            "station",
        ]

    def get_file_url(self, obj: StationResource) -> str | None:
        """Get the full URL for the file if it exists."""
        return obj.get_file_url()

    def get_miniature_url(self, obj: StationResource) -> str | None:
        """Get miniature URL if available (for PHOTO, VIDEO, DOCUMENT resources)."""
        return obj.get_miniature_url()

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

        # Only validate file requirement for new resources or when file is being updated
        if resource_type in [
            StationResourceType.PHOTO,
            StationResourceType.VIDEO,
            StationResourceType.DOCUMENT,
        ]:
            # For updates, only validate if file is being changed
            if self.instance and not file_field:
                return attrs

            if not file_field:
                raise serializers.ValidationError(
                    f"Resource type '{resource_type}' requires a file."
                )

            # Validate file size (max 5MBs)
            if file_field:
                max_size = 5 * 1024 * 1024  # 5MB in bytes
                if file_field.size > max_size:
                    raise serializers.ValidationError(
                        {"file": "File size cannot exceed 5MB."}
                    )

        elif resource_type in [
            StationResourceType.NOTE,
            StationResourceType.SKETCH,
        ]:
            # For updates, check if text_content is being updated
            if self.instance and "text_content" not in attrs:
                return attrs

            # For new resources, text_content is required
            if not text_content:
                raise serializers.ValidationError(
                    f"Resource type '{resource_type}' requires text content."
                )

        else:
            raise ValidationError(f"Unknown value received: `{resource_type}`")

        return attrs


class StationSerializer(serializers.ModelSerializer[Station]):
    """Serializer for creating stations."""

    created_by = serializers.EmailField(source="created_by.email", read_only=True)

    class Meta:
        model = Station
        fields = "__all__"

        read_only_fields = [
            "id",
            "created_by",
            "creation_date",
            "modified_date",
            "project",
        ]

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

        return super().to_internal_value(data)

    def to_representation(self, instance: Station) -> dict[str, Any]:
        """Ensure coordinates are formatted without trailing zeros."""
        data = super().to_representation(instance)

        if data.get("latitude") is not None:
            data["latitude"] = format_coordinate(data["latitude"])

        if data.get("longitude") is not None:
            data["longitude"] = format_coordinate(data["longitude"])

        return data


class StationWithResourcesSerializer(StationSerializer):
    """Serializer for stations."""

    resources = StationResourceSerializer(many=True, read_only=True)


class StationGeoJSONSerializer(serializers.ModelSerializer[Station]):
    """Map serializer for POIs - returns GeoJSON-like format."""

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
        ]

    def to_representation(self, instance: Station) -> dict[str, Any]:
        """Convert to GeoJSON Feature format."""
        return {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [float(instance.longitude), float(instance.latitude)],
            },
            "properties": {
                "id": str(instance.id),
                "name": instance.name,
                "description": instance.description,
                "created_by": instance.created_by.email,
                "creation_date": instance.creation_date.isoformat(),
            },
        }
