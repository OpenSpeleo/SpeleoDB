# -*- coding: utf-8 -*-

from __future__ import annotations

import logging
from typing import Any

from rest_framework import serializers

from speleodb.common.enums import PermissionLevel
from speleodb.gis.models import Sensor
from speleodb.gis.models import SensorFleet
from speleodb.gis.models import SensorFleetUserPermission
from speleodb.users.models import User

logger = logging.getLogger(__name__)


class SensorSerializer(serializers.ModelSerializer[Sensor]):
    """Serializer for Sensor model."""

    # Make fleet write-only since we pass it via URL
    fleet = serializers.PrimaryKeyRelatedField(
        queryset=SensorFleet.objects.all(),
        write_only=True,
        required=False,
    )

    # Read-only fields for API responses
    fleet_id = serializers.UUIDField(source="fleet.id", read_only=True)
    fleet_name = serializers.CharField(source="fleet.name", read_only=True)

    class Meta:
        model = Sensor
        fields = "__all__"
        read_only_fields = [
            "id",
            "created_by",
            "creation_date",
            "modified_date",
        ]


class SensorFleetSerializer(serializers.ModelSerializer[SensorFleet]):
    """Serializer for SensorFleet model with optional initial sensors."""

    # Explicitly declare name field to enforce validation
    name = serializers.CharField(
        max_length=50,
        min_length=1,
        allow_blank=False,
        required=True,
        trim_whitespace=True,
    )

    # Read-only sensor count
    sensor_count = serializers.SerializerMethodField()

    class Meta:
        model = SensorFleet
        fields = "__all__"
        read_only_fields = [
            "id",
            "creation_date",
            "modified_date",
        ]

    def validate_name(self, value: str) -> str:
        """Validate that fleet name is not empty."""
        if not value or not value.strip():
            raise serializers.ValidationError("Fleet name cannot be empty.")
        return value.strip()

    def get_sensor_count(self, obj: SensorFleet) -> int:
        """Get the number of sensors in this fleet."""
        return obj.sensors.count()

    def create(self, validated_data: dict[str, Any]) -> SensorFleet:
        """Create a new sensor fleet with automatic permission creation."""
        sensor_fleet = super().create(validated_data)

        # assign an ADMIN permission to the creator
        _ = SensorFleetUserPermission.objects.create(
            sensor_fleet=sensor_fleet,
            user=User.objects.get(email=validated_data["created_by"]),
            level=PermissionLevel.ADMIN,
        )

        return sensor_fleet


class SensorFleetListSerializer(serializers.ModelSerializer[SensorFleet]):
    """Optimized serializer for listing sensor fleets with user permission level."""

    sensor_count = serializers.IntegerField(read_only=True)
    user_permission_level = serializers.IntegerField(read_only=True, required=False)
    user_permission_level_label = serializers.CharField(read_only=True, required=False)

    class Meta:
        model = SensorFleet
        fields = [
            "id",
            "name",
            "description",
            "is_active",
            "created_by",
            "creation_date",
            "modified_date",
            "sensor_count",
            "user_permission_level",
            "user_permission_level_label",
        ]
        read_only_fields = fields


class SensorFleetUserPermissionSerializer(
    serializers.ModelSerializer[SensorFleetUserPermission]
):
    """Serializer for SensorFleetUserPermission model."""

    # User email for creation/updates
    user_email = serializers.EmailField(write_only=True, required=False)

    # Read-only user info
    user_id = serializers.UUIDField(source="user.id", read_only=True)
    user_full_name = serializers.SerializerMethodField()
    user_display_email = serializers.EmailField(source="user.email", read_only=True)

    # Read-only permission level label
    level_label = serializers.CharField(read_only=True)

    # Fleet info (read-only)
    fleet_id = serializers.UUIDField(source="sensor_fleet.id", read_only=True)
    fleet_name = serializers.CharField(source="sensor_fleet.name", read_only=True)

    class Meta:
        model = SensorFleetUserPermission
        fields = [
            "id",
            "user",
            "user_email",
            "user_id",
            "user_full_name",
            "user_display_email",
            "sensor_fleet",
            "fleet_id",
            "fleet_name",
            "level",
            "level_label",
            "is_active",
            "deactivated_by",
            "creation_date",
            "modified_date",
        ]
        read_only_fields = [
            "id",
            "user",
            "sensor_fleet",
            "deactivated_by",
            "creation_date",
            "modified_date",
        ]

    def get_user_full_name(self, obj: SensorFleetUserPermission) -> str:
        """Get user's full name or email."""
        if obj.user.first_name or obj.user.last_name:
            return f"{obj.user.first_name} {obj.user.last_name}".strip()
        return obj.user.email

    def validate_user_email(self, value: str) -> str:
        """Validate user exists."""
        try:
            User.objects.get(email=value)
        except User.DoesNotExist as e:
            raise serializers.ValidationError(
                f"User with email '{value}' does not exist."
            ) from e
        return value

    def validate_level(self, value: int) -> int:
        """Validate permission level is valid."""
        valid_levels = [
            PermissionLevel.READ_ONLY,
            PermissionLevel.READ_AND_WRITE,
            PermissionLevel.ADMIN,
        ]
        if value not in valid_levels:
            raise serializers.ValidationError(
                f"Invalid permission level. Must be one of: {valid_levels}"
            )
        return value

    def create(self, validated_data: dict[str, Any]) -> SensorFleetUserPermission:
        """Create a new permission."""
        # Handle user_email if provided
        if "user_email" in validated_data:
            user_email = validated_data.pop("user_email")
            validated_data["user"] = User.objects.get(email=user_email)

        # Check for existing permission
        existing_perm = SensorFleetUserPermission.objects.filter(
            user=validated_data["user"],
            sensor_fleet=validated_data["sensor_fleet"],
        ).first()

        if existing_perm:
            if existing_perm.is_active:
                raise serializers.ValidationError(
                    {"user": ["User already has an active permission for this fleet."]}
                )
            # Reactivate existing permission
            existing_perm.is_active = True
            existing_perm.level = validated_data.get("level", existing_perm.level)
            existing_perm.deactivated_by = None
            existing_perm.save()
            return existing_perm

        return super().create(validated_data)

    def update(
        self, instance: SensorFleetUserPermission, validated_data: dict[str, Any]
    ) -> SensorFleetUserPermission:
        """Update permission level only."""
        # Only allow updating level
        if "level" in validated_data:
            instance.level = validated_data["level"]
            instance.save()

        return instance
