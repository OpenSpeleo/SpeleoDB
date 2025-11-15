# -*- coding: utf-8 -*-

from __future__ import annotations

import contextlib
from decimal import InvalidOperation
from typing import Any

from rest_framework import serializers

from speleodb.gis.models import PointOfInterest
from speleodb.utils.gps_utils import format_coordinate


class PointOfInterestSerializer(serializers.ModelSerializer[PointOfInterest]):
    """Serializer for POI with all details."""

    user = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = PointOfInterest
        fields = "__all__"
        read_only_fields = [
            "id",
            "creation_date",
            "modified_date",
            "user",
        ]

    def create(self, validated_data: Any) -> PointOfInterest:
        """Create a new POI and set user from request user."""
        request = self.context.get("request")
        if request and hasattr(request, "user") and request.user.is_authenticated:
            validated_data["user"] = request.user

        return super().create(validated_data)

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

    def to_representation(self, instance: PointOfInterest) -> dict[str, Any]:
        """Ensure coordinates are rounded to 7 decimal places."""
        data = super().to_representation(instance)
        if data.get("latitude") is not None:
            data["latitude"] = format_coordinate(data["latitude"])
        if data.get("longitude") is not None:
            data["longitude"] = format_coordinate(data["longitude"])
        return data


class PointOfInterestGeoJSONSerializer(serializers.ModelSerializer[PointOfInterest]):
    """Map serializer for POIs - returns GeoJSON-like format."""

    class Meta:
        model = PointOfInterest
        fields = [
            "id",
            "name",
            "description",
            "latitude",
            "longitude",
            "user",
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
            },
        }
