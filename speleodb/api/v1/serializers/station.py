# -*- coding: utf-8 -*-

from __future__ import annotations

from decimal import Decimal
from decimal import InvalidOperation
from typing import Any

from rest_framework import serializers

from speleodb.surveys.models import Project
from speleodb.surveys.models import Station
from speleodb.surveys.models import StationResource


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


class StationResourceSerializer(serializers.ModelSerializer[StationResource]):
    """Serializer for StationResource model."""

    created_by_email = serializers.CharField(source="created_by.email", read_only=True)
    file_url = serializers.SerializerMethodField()
    station_id = serializers.UUIDField(write_only=True, required=False)

    class Meta:
        model = StationResource
        fields = [
            "id",
            "resource_type",
            "title",
            "description",
            "file",
            "file_url",
            "text_content",
            "created_by",
            "created_by_email",
            "creation_date",
            "modified_date",
            "station_id",
        ]
        read_only_fields = ["id", "created_by", "creation_date", "modified_date"]

    def get_file_url(self, obj: StationResource) -> str | None:
        """Get the full URL for the file if it exists."""
        return obj.get_file_url()

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
        if not resource_type and self.instance:
            resource_type = self.instance.resource_type

        file_field = attrs.get("file")
        text_content = attrs.get("text_content")

        # Only validate file requirement for new resources or when file is being updated
        if resource_type in [
            "photo",
            "video",
            "document",
        ]:
            # For updates, only validate if file is being changed
            if not self.instance and not file_field:
                raise serializers.ValidationError(
                    f"Resource type '{resource_type}' requires a file."
                )

            # Validate file size (max 5MB for videos)
            if file_field and resource_type == "video":
                max_size = 5 * 1024 * 1024  # 5MB in bytes
                if file_field.size > max_size:
                    raise serializers.ValidationError(
                        {"file": "Video file size cannot exceed 5MB."}
                    )
        elif resource_type in [
            "note",
            "sketch",
        ]:
            # For updates, check if text_content is being cleared
            if self.instance:
                # If text_content is in attrs and is empty, that's an error
                if "text_content" in attrs and not text_content:
                    raise serializers.ValidationError(
                        f"Resource type '{resource_type}' requires text content."
                    )
            # For new resources, text_content is required
            elif not text_content:
                raise serializers.ValidationError(
                    f"Resource type '{resource_type}' requires text content."
                )

        return attrs


class StationSerializer(serializers.ModelSerializer):
    """Serializer for stations."""

    resources = StationResourceSerializer(many=True, read_only=True)
    created_by_email = serializers.CharField(source="created_by.email", read_only=True)
    resource_count = serializers.SerializerMethodField()
    project_id = serializers.UUIDField(source="project.id", read_only=True)
    project = serializers.PrimaryKeyRelatedField(
        queryset=Project.objects.all(),
        required=False,
        write_only=True,
    )

    class Meta:
        model = Station
        fields = "__all__"
        read_only_fields = [
            "id",
            "creation_date",
            "modified_date",
            "created_by",
        ]

    def get_resource_count(self, obj: Station) -> int:
        """Get the total number of resources for this station."""
        return obj.resources.count()  # type: ignore[attr-defined]

    def to_internal_value(self, data):
        """Override to round coordinates before validation and handle project_id."""
        # Create a mutable copy of the data
        mutable_data = dict(data)

        # Handle project_id -> project conversion
        if "project_id" in mutable_data and "project" not in mutable_data:
            mutable_data["project"] = mutable_data.pop("project_id")

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

    def to_representation(self, instance: Station) -> dict[str, Any]:
        """Ensure coordinates are rounded to 7 decimal places."""
        data = super().to_representation(instance)
        if data.get("latitude") is not None:
            data["latitude"] = format_coordinate(data["latitude"])
        if data.get("longitude") is not None:
            data["longitude"] = format_coordinate(data["longitude"])
        return data


class StationListSerializer(serializers.ModelSerializer):
    """List serializer for stations with resource counts."""

    resource_count = serializers.SerializerMethodField()
    project_id = serializers.UUIDField(source="project.id", read_only=True)

    class Meta:
        model = Station
        fields = [
            "id",
            "name",
            "description",
            "latitude",
            "longitude",
            "resource_count",
            "creation_date",
            "modified_date",
            "project_id",
        ]
        read_only_fields = ["id", "creation_date", "modified_date", "project_id"]

    def get_resource_count(self, obj: Station) -> int:
        """Get the total number of resources for this station."""
        return obj.resources.count()  # type: ignore[attr-defined]

    def to_representation(self, instance: Station) -> dict[str, Any]:
        """Ensure coordinates are rounded to 7 decimal places."""
        data = super().to_representation(instance)
        if data.get("latitude") is not None:
            data["latitude"] = format_coordinate(data["latitude"])
        if data.get("longitude") is not None:
            data["longitude"] = format_coordinate(data["longitude"])
        return data


class StationCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating stations."""

    # Define coordinates as required - they can't be null in the database
    latitude = serializers.DecimalField(
        max_digits=10,
        decimal_places=7,
        required=True,
        allow_null=False,
        min_value=-90,
        max_value=90,
    )
    longitude = serializers.DecimalField(
        max_digits=10,
        decimal_places=7,
        required=True,
        allow_null=False,
        min_value=-180,
        max_value=180,
    )

    class Meta:
        model = Station
        fields = ["id", "name", "description", "latitude", "longitude", "creation_date"]
        read_only_fields = ["id", "creation_date"]

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

    def to_representation(self, instance: Station) -> dict[str, Any]:
        """Ensure coordinates are formatted without trailing zeros."""
        data = super().to_representation(instance)
        if data.get("latitude") is not None:
            data["latitude"] = format_coordinate(data["latitude"])
        if data.get("longitude") is not None:
            data["longitude"] = format_coordinate(data["longitude"])
        return data

    def create(self, validated_data: dict[str, Any]) -> Station:
        """Create a station."""
        # The project and created_by are now passed from the ViewSet
        return super().create(validated_data)
