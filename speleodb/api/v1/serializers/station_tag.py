# -*- coding: utf-8 -*-

from __future__ import annotations

import random
from typing import Any

from rest_framework import serializers

from speleodb.gis.models import StationTag


class StationTagSerializer(serializers.ModelSerializer[StationTag]):
    """Serializer for StationTag model."""

    station_count = serializers.SerializerMethodField()

    class Meta:
        model = StationTag
        fields = [
            "id",
            "name",
            "color",
            "user",
            "creation_date",
            "modified_date",
            "station_count",
        ]

        read_only_fields = [
            "id",
            "user",
            "creation_date",
            "modified_date",
            "station_count",
        ]

    def get_station_count(self, obj: StationTag) -> int:
        """Get the number of stations with this tag."""
        return obj.stations.count()

    def validate_name(self, value: str) -> str:
        """Capitalize tag name for consistency and check for duplicates."""
        return value.strip().title()

    def validate_color(self, value: str) -> str:
        """Ensure color is uppercase for consistency."""
        return value.upper()

    def create(self, validated_data: dict[str, Any]) -> StationTag:
        """Create a new station tag with the current user."""
        # If no color provided, pick a random one from predefined colors
        if "color" not in validated_data or not validated_data["color"]:
            validated_data["color"] = random.choice(
                StationTag.get_predefined_colors()
            ).upper()

        return super().create(validated_data)


class StationTagListSerializer(serializers.Serializer):  # type: ignore[type-arg]
    """Serializer to return list of predefined colors."""

    colors = serializers.ListField(child=serializers.CharField())

    def to_representation(self, instance: Any) -> dict[str, list[str]]:
        """Return predefined colors."""
        return {"colors": StationTag.get_predefined_colors()}


class StationTagBulkSerializer(serializers.Serializer):  # type: ignore[type-arg]
    """Serializer for bulk tag operations."""

    tag_ids = serializers.ListField(
        child=serializers.UUIDField(),
        help_text="List of tag IDs to assign/remove",
    )
