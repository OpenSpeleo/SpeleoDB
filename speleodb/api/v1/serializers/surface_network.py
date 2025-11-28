# -*- coding: utf-8 -*-

from __future__ import annotations

import logging
from typing import Any

from rest_framework import serializers

from speleodb.common.enums import PermissionLevel
from speleodb.gis.models import SurfaceMonitoringNetwork
from speleodb.gis.models import SurfaceMonitoringNetworkUserPermission
from speleodb.users.models import User

logger = logging.getLogger(__name__)


class SurfaceMonitoringNetworkSerializer(
    serializers.ModelSerializer[SurfaceMonitoringNetwork]
):
    """Serializer for SurfaceMonitoringNetwork model."""

    # Explicitly declare name field to enforce validation
    name = serializers.CharField(
        max_length=100,
        min_length=1,
        allow_blank=False,
        required=True,
        trim_whitespace=True,
    )

    class Meta:
        model = SurfaceMonitoringNetwork
        fields = "__all__"
        read_only_fields = [
            "id",
            "created_by",
            "gis_token",
            "creation_date",
            "modified_date",
        ]

    def validate_name(self, value: str) -> str:
        """Validate that network name is not empty."""
        if not value or not value.strip():
            raise serializers.ValidationError("Network name cannot be empty.")
        return value.strip()

    def create(self, validated_data: dict[str, Any]) -> SurfaceMonitoringNetwork:
        """Create a new network with automatic permission creation."""
        network = super().create(validated_data)

        # assign an ADMIN permission to the creator
        _ = SurfaceMonitoringNetworkUserPermission.objects.create(
            network=network,
            user=User.objects.get(email=network.created_by),
            level=PermissionLevel.ADMIN,
        )

        return network


class SurfaceMonitoringNetworkListSerializer(
    serializers.ModelSerializer[SurfaceMonitoringNetwork]
):
    """Optimized serializer for listing networks with user permission level."""

    user_permission_level = serializers.IntegerField(read_only=True, required=False)
    user_permission_level_label = serializers.CharField(read_only=True, required=False)

    class Meta:
        model = SurfaceMonitoringNetwork
        fields = [
            "id",
            "name",
            "description",
            "is_active",
            "created_by",
            "creation_date",
            "modified_date",
            "user_permission_level",
            "user_permission_level_label",
        ]
        read_only_fields = fields


class SurfaceMonitoringNetworkUserPermissionSerializer(
    serializers.ModelSerializer[SurfaceMonitoringNetworkUserPermission]
):
    """Serializer for SurfaceMonitoringNetworkUserPermission model."""

    # User email for creation/updates
    user_email = serializers.EmailField(write_only=True, required=False)

    # Read-only user info
    user_id = serializers.UUIDField(source="user.id", read_only=True)
    user_full_name = serializers.SerializerMethodField()
    user_display_email = serializers.EmailField(source="user.email", read_only=True)

    # Read-only permission level label
    level_label = serializers.CharField(read_only=True)

    # Network info (read-only)
    network_id = serializers.UUIDField(source="network.id", read_only=True)
    network_name = serializers.CharField(source="network.name", read_only=True)

    class Meta:
        model = SurfaceMonitoringNetworkUserPermission
        fields = [
            "id",
            "user",
            "user_email",
            "user_id",
            "user_full_name",
            "user_display_email",
            "network",
            "network_id",
            "network_name",
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
            "network",
            "deactivated_by",
            "creation_date",
            "modified_date",
        ]

    def get_user_full_name(self, obj: SurfaceMonitoringNetworkUserPermission) -> str:
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

    def create(
        self, validated_data: dict[str, Any]
    ) -> SurfaceMonitoringNetworkUserPermission:
        """Create a new permission."""
        # Handle user_email if provided
        if "user_email" in validated_data:
            user_email = validated_data.pop("user_email")
            validated_data["user"] = User.objects.get(email=user_email)

        # Check for existing permission
        existing_perm = SurfaceMonitoringNetworkUserPermission.objects.filter(
            user=validated_data["user"],
            network=validated_data["network"],
        ).first()

        if existing_perm:
            if existing_perm.is_active:
                raise serializers.ValidationError(
                    {
                        "user": [
                            "User already has an active permission for this network."
                        ]
                    }
                )
            # Reactivate existing permission
            existing_perm.is_active = True
            existing_perm.level = validated_data.get("level", existing_perm.level)
            existing_perm.deactivated_by = None
            existing_perm.save()
            return existing_perm

        return super().create(validated_data)

    def update(
        self,
        instance: SurfaceMonitoringNetworkUserPermission,
        validated_data: dict[str, Any],
    ) -> SurfaceMonitoringNetworkUserPermission:
        """Update permission level only."""
        # Only allow updating level
        if "level" in validated_data:
            instance.level = validated_data["level"]
            instance.save()

        return instance
