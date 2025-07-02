# -*- coding: utf-8 -*-

from __future__ import annotations

from decimal import Decimal
from decimal import InvalidOperation
from typing import Any

from rest_framework import serializers

from speleodb.surveys.models import PointOfInterest


def format_coordinate(value: Any) -> str | None:
    """Format a coordinate value without trailing zeros."""
    if value is None:
        return None
    # Convert to Decimal and format without trailing zeros
    decimal_value = Decimal(str(value))
    # Round to 7 decimal places
    rounded_value = round(decimal_value, 7)
    # Convert to string and remove trailing zeros
    # The normalize() method removes trailing zeros from Decimal
    normalized = rounded_value.normalize()
    return str(normalized)


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

    def create(self, validated_data):
        """Create a new POI and set created_by from request user."""
        request = self.context.get("request")
        if request and hasattr(request, "user") and request.user.is_authenticated:
            validated_data["created_by"] = request.user
        return super().create(validated_data)

    def to_internal_value(self, data):
        """Override to round coordinates before validation."""
        # Create a mutable copy of the data
        mutable_data = dict(data)

        # Round coordinates if they exist in the data
        if "latitude" in mutable_data and mutable_data["latitude"] is not None:
            try:
                lat_value = Decimal(str(mutable_data["latitude"]))
                mutable_data["latitude"] = str(round(lat_value, 7))
            except (ValueError, TypeError, InvalidOperation):
                pass  # Let the field validation handle the error

        if "longitude" in mutable_data and mutable_data["longitude"] is not None:
            try:
                lng_value = Decimal(str(mutable_data["longitude"]))
                mutable_data["longitude"] = str(round(lng_value, 7))
            except (ValueError, TypeError, InvalidOperation):
                pass  # Let the field validation handle the error

        return super().to_internal_value(mutable_data)

    def validate_latitude(self, value):
        """Ensure latitude is rounded to 7 decimal places."""
        if value is not None:
            return round(Decimal(str(value)), 7)
        return value

    def validate_longitude(self, value):
        """Ensure longitude is rounded to 7 decimal places."""
        if value is not None:
            return round(Decimal(str(value)), 7)
        return value

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
