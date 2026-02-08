# -*- coding: utf-8 -*-

from __future__ import annotations

import contextlib
from decimal import InvalidOperation
from typing import Any
from typing import ClassVar

from geojson import Feature  # type: ignore[attr-defined]
from geojson import Point  # type: ignore[attr-defined]
from rest_framework import serializers

from speleodb.gis.models import ExplorationLead
from speleodb.utils.gps_utils import format_coordinate
from speleodb.utils.serializer_mixins import SanitizedFieldsMixin


class ExplorationLeadSerializer(
    SanitizedFieldsMixin, serializers.ModelSerializer[ExplorationLead]
):
    """Serializer for ExplorationLead model."""

    sanitized_fields: ClassVar[list[str]] = ["description"]

    class Meta:
        model = ExplorationLead
        fields = [
            "id",
            "description",
            "latitude",
            "longitude",
            "project",
            "created_by",
            "creation_date",
            "modified_date",
        ]

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
                data["latitude"] = format_coordinate(data["latitude"])

        if "longitude" in data and data["longitude"] is not None:
            with contextlib.suppress(ValueError, TypeError, InvalidOperation):
                data["longitude"] = format_coordinate(data["longitude"])

        return super().to_internal_value(data)

    def to_representation(self, instance: ExplorationLead) -> dict[str, Any]:
        """Ensure coordinates are formatted without trailing zeros."""
        data = super().to_representation(instance)

        if data.get("latitude") is not None:
            data["latitude"] = format_coordinate(data["latitude"])

        if data.get("longitude") is not None:
            data["longitude"] = format_coordinate(data["longitude"])

        return data


class ExplorationLeadGeoJSONSerializer(serializers.ModelSerializer[ExplorationLead]):
    """GeoJSON serializer for ExplorationLead - returns GeoJSON-like format for maps."""

    class Meta:
        model = ExplorationLead
        fields = [
            "id",
            "description",
            "latitude",
            "longitude",
            "created_by",
            "creation_date",
            "modified_date",
        ]

    def to_representation(self, instance: ExplorationLead) -> dict[str, Any]:
        """Convert to GeoJSON Feature"""
        return Feature(  # type: ignore[no-untyped-call]
            id=str(instance.id),
            geometry=Point((float(instance.longitude), float(instance.latitude))),  # type: ignore[no-untyped-call]
            properties={
                "description": instance.description,
                "created_by": instance.created_by,
                "creation_date": instance.creation_date.isoformat(),
                "modified_date": instance.modified_date.isoformat(),
                "project": str(instance.project.id),
            },
        )
