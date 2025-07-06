# -*- coding: utf-8 -*-

from __future__ import annotations

import contextlib
from decimal import InvalidOperation
from typing import Any

from rest_framework import serializers

from speleodb.surveys.models import PointOfInterest


def format_coordinate(value: Any) -> float:
    """Format a coordinate value to 7 decimal places"""
    return round(float(value), 7)


class PointOfInterestSerializer(serializers.ModelSerializer[PointOfInterest]):
    """Serializer for POI with all details."""

    created_by_email = serializers.CharField(source="created_by.email", read_only=True)

    class Meta:
        model = PointOfInterest
        fields = "__all__"
        read_only_fields = [
            "id",
            "creation_date",
            "modified_date",
            "created_by",
        ]

    def create(self, validated_data: Any) -> PointOfInterest:
        """Create a new POI and set created_by from request user."""
        request = self.context.get("request")
        if request and hasattr(request, "user") and request.user.is_authenticated:
            validated_data["created_by"] = request.user
        return super().create(validated_data)

    def to_internal_value(self, data: Any) -> Any:
        """Override to round coordinates before validation."""

        # Round coordinates if they exist in the data
        if "latitude" in data and data["latitude"] is not None:
            with contextlib.suppress(ValueError, TypeError, InvalidOperation):
                # Let the field validation handle the error
                data["latitude"] = round(float(data["latitude"]), 7)

        if "longitude" in data and data["longitude"] is not None:
            with contextlib.suppress(ValueError, TypeError, InvalidOperation):
                # Let the field validation handle the error
                data["longitude"] = round(float(data["longitude"]), 7)

        return super().to_internal_value(data)

    def validate_latitude(self, value: str | float) -> float:
        """Ensure latitude is rounded to 7 decimal places."""
        return format_coordinate(value)

    def validate_longitude(self, value: str | float) -> float:
        """Ensure longitude is rounded to 7 decimal places."""
        return format_coordinate(value)

    def to_representation(self, instance: PointOfInterest) -> dict[str, Any]:
        """Ensure coordinates are rounded to 7 decimal places."""
        data = super().to_representation(instance)
        if data.get("latitude") is not None:
            data["latitude"] = format_coordinate(data["latitude"])
        if data.get("longitude") is not None:
            data["longitude"] = format_coordinate(data["longitude"])
        return data


class PointOfInterestListSerializer(serializers.ModelSerializer[PointOfInterest]):
    """List serializer for POIs - minimal fields for performance."""

    class Meta:
        model = PointOfInterest
        fields = [
            "id",
            "name",
            "latitude",
            "longitude",
            "creation_date",
        ]
        read_only_fields = ["id", "creation_date"]

    def to_representation(self, instance: PointOfInterest) -> dict[str, Any]:
        """Ensure coordinates are rounded to 7 decimal places."""
        data = super().to_representation(instance)
        if data.get("latitude") is not None:
            data["latitude"] = format_coordinate(data["latitude"])
        if data.get("longitude") is not None:
            data["longitude"] = format_coordinate(data["longitude"])
        return data


class PointOfInterestMapSerializer(serializers.ModelSerializer[PointOfInterest]):
    """Map serializer for POIs - returns GeoJSON-like format."""

    created_by_email = serializers.CharField(source="created_by.email", read_only=True)

    class Meta:
        model = PointOfInterest
        fields = [
            "id",
            "name",
            "description",
            "latitude",
            "longitude",
            "created_by_email",
            "creation_date",
        ]

    def to_representation(self, instance: PointOfInterest) -> dict[str, Any]:
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
                "created_by_email": instance.created_by.email
                if instance.created_by
                else "Unknown",
                "creation_date": instance.creation_date.isoformat(),
            },
        }
