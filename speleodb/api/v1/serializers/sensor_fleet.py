# -*- coding: utf-8 -*-

from __future__ import annotations

import logging
from typing import Any

from rest_framework import serializers

from speleodb.common.enums import PermissionLevel
from speleodb.gis.models import Sensor
from speleodb.gis.models import SensorFleet
from speleodb.gis.models import SensorFleetUserPermission
from speleodb.gis.models import SensorInstall
from speleodb.gis.models import Station
from speleodb.gis.models.sensor import InstallStatus
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

    # Latest install status
    latest_install_project = serializers.SerializerMethodField()
    latest_install_lat = serializers.SerializerMethodField()
    latest_install_long = serializers.SerializerMethodField()
    latest_install_memory_expiry = serializers.SerializerMethodField()
    latest_install_battery_expiry = serializers.SerializerMethodField()
    active_installs = serializers.SerializerMethodField()

    class Meta:
        model = Sensor
        fields = "__all__"
        read_only_fields = [
            "id",
            "created_by",
            "creation_date",
            "modified_date",
            "latest_install_project",
            "latest_install_lat",
            "latest_install_long",
            "latest_install_memory_expiry",
            "latest_install_battery_expiry",
            "active_installs",
        ]

    def get_latest_install_project(self, obj: Sensor) -> str | None:
        """Get the name of the project where the sensor is currently installed."""
        install = obj.installs.filter(status=InstallStatus.INSTALLED).first()
        return install.station.project.name if install else None

    def get_latest_install_lat(self, obj: Sensor) -> float | None:
        """Get the latitude of the station where the sensor is currently installed."""
        install = obj.installs.filter(status=InstallStatus.INSTALLED).first()
        return float(install.station.latitude) if install else None

    def get_latest_install_long(self, obj: Sensor) -> float | None:
        """Get the longitude of the station where the sensor is currently installed."""
        install = obj.installs.filter(status=InstallStatus.INSTALLED).first()
        return float(install.station.longitude) if install else None

    def get_latest_install_memory_expiry(self, obj: Sensor) -> str | None:
        """Get the memory expiry date of the current install."""
        install = obj.installs.filter(status=InstallStatus.INSTALLED).first()
        return (
            install.expiracy_memory_date.isoformat()
            if install and install.expiracy_memory_date
            else None
        )

    def get_latest_install_battery_expiry(self, obj: Sensor) -> str | None:
        """Get the battery expiry date of the current install."""
        install = obj.installs.filter(status=InstallStatus.INSTALLED).first()
        return (
            install.expiracy_battery_date.isoformat()
            if install and install.expiracy_battery_date
            else None
        )

    def get_active_installs(self, obj: Sensor) -> list[dict[str, Any]]:
        """Get active installs with full details."""
        installs = obj.installs.filter(status=InstallStatus.INSTALLED).select_related(  # pyright: ignore[reportAttributeAccessIssue]
            "station", "station__project"
        )

        return [
            {
                "id": str(install.id),
                "station": {
                    "id": str(install.station.id),
                    "name": install.station.name,
                    "latitude": str(install.station.latitude),
                    "longitude": str(install.station.longitude),
                    "project": {
                        "id": str(install.station.project.id),
                        "name": install.station.project.name,
                    },
                },
                "expiracy_memory_date": install.expiracy_memory_date.isoformat()
                if install.expiracy_memory_date
                else None,
                "expiracy_battery_date": install.expiracy_battery_date.isoformat()
                if install.expiracy_battery_date
                else None,
            }
            for install in installs
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


class SensorInstallSerializer(serializers.ModelSerializer[SensorInstall]):
    """Serializer for SensorInstall model."""

    # Read-only nested information
    sensor_id = serializers.UUIDField(source="sensor.id", read_only=True)
    sensor_name = serializers.CharField(source="sensor.name", read_only=True)
    sensor_fleet_id = serializers.UUIDField(source="sensor.fleet.id", read_only=True)
    sensor_fleet_name = serializers.CharField(
        source="sensor.fleet.name", read_only=True
    )
    station_id = serializers.UUIDField(source="station.id", read_only=True)
    station_name = serializers.CharField(source="station.name", read_only=True)

    # Sensor is write-only for creation
    sensor = serializers.PrimaryKeyRelatedField(
        queryset=Sensor.objects.all(),
        write_only=True,
        required=True,
    )

    # Station is write-only for creation (passed via URL)
    station = serializers.PrimaryKeyRelatedField(
        queryset=Station.objects.all(),
        write_only=True,
        required=False,
    )

    class Meta:
        model = SensorInstall
        fields = "__all__"
        read_only_fields = [
            "id",
            "created_by",
            "creation_date",
            "modified_date",
        ]

    def validate(self, data: dict[str, Any]) -> dict[str, Any]:
        """Validate sensor install data and status transitions."""
        instance = self.instance
        status = data.get(
            "status", instance.status if instance else InstallStatus.INSTALLED
        )

        # If updating status to not INSTALLED, require uninstall fields
        if status != InstallStatus.INSTALLED:
            uninstall_date = data.get("uninstall_date")
            uninstall_user = data.get("uninstall_user")

            if not uninstall_date:
                raise serializers.ValidationError(
                    {
                        "uninstall_date": (
                            "Uninstall date is required when marking as uninstalled."
                        )
                    }
                )
            if not uninstall_user:
                raise serializers.ValidationError(
                    {
                        "uninstall_user": (
                            "Uninstall user is required when marking as uninstalled."
                        )
                    }
                )

            # Check install_date <= uninstall_date
            install_date = data.get(
                "install_date", instance.install_date if instance else None
            )
            if install_date and uninstall_date and install_date > uninstall_date:
                raise serializers.ValidationError(
                    {
                        "uninstall_date": (
                            "Uninstall date must be on or after install date."
                        )
                    }
                )

        # If status is INSTALLED, clear uninstall fields
        else:
            if "uninstall_date" in data and data["uninstall_date"] is not None:
                raise serializers.ValidationError(
                    {
                        "uninstall_date": (
                            "Uninstall date can only be set when status is uninstalled."
                        )
                    }
                )
            if "uninstall_user" in data and data["uninstall_user"] is not None:
                raise serializers.ValidationError(
                    {
                        "uninstall_user": (
                            "Uninstall user can only be set when status is uninstalled."
                        )
                    }
                )

        # Validate status transitions
        if instance:
            current_status = instance.status
            # Can only change from INSTALLED to other statuses
            if current_status not in (InstallStatus.INSTALLED, status):
                raise serializers.ValidationError(
                    {
                        "status": (
                            f"Cannot change status from {current_status} to {status}. "
                            "Only INSTALLED sensors can have their status changed."
                        )
                    }
                )

        return data

    def create(self, validated_data: dict[str, Any]) -> SensorInstall:
        """Create a new sensor install."""
        # Check if sensor is already installed elsewhere
        sensor = validated_data["sensor"]
        existing_install = SensorInstall.objects.filter(
            sensor=sensor, status=InstallStatus.INSTALLED
        ).first()

        if existing_install:
            raise serializers.ValidationError(
                {
                    "sensor": (
                        f"This sensor is already installed at station "
                        f"{existing_install.station.name} "
                        f"({existing_install.station.id}). "
                        "A sensor can only be installed at one station at a time."
                    )
                }
            )

        return super().create(validated_data)

    def update(
        self, instance: SensorInstall, validated_data: dict[str, Any]
    ) -> SensorInstall:
        """Update an existing sensor install."""
        # If sensor is being changed, check if new sensor is already installed
        if "sensor" in validated_data:
            new_sensor = validated_data["sensor"]
            # Only check if it's a different sensor
            if new_sensor != instance.sensor:
                existing_install = SensorInstall.objects.filter(
                    sensor=new_sensor, status=InstallStatus.INSTALLED
                ).first()

                if existing_install:
                    raise serializers.ValidationError(
                        {
                            "sensor": (
                                f"This sensor is already installed at station "
                                f"{existing_install.station.name} "
                                f"({existing_install.station.id}). "
                                "A sensor can only be installed at one station at a "
                                "time."
                            )
                        }
                    )

        return super().update(instance, validated_data)
