# -*- coding: utf-8 -*-

from __future__ import annotations

import contextlib
from decimal import InvalidOperation
from typing import Any
from typing import ClassVar

from drf_spectacular.utils import extend_schema_field
from geojson import Feature  # type: ignore[attr-defined]
from geojson import Point  # type: ignore[attr-defined]
from rest_framework import serializers

from speleodb.common.constants import EXPLORATION_LEAD_MAX_HEADINGS
from speleodb.common.constants import HEADING_FULL_CIRCLE
from speleodb.gis.models import ExplorationLead
from speleodb.gis.models.explo_lead import validate_headings
from speleodb.utils.gps_utils import format_coordinate
from speleodb.utils.serializer_mixins import SanitizedFieldsMixin


@extend_schema_field(
    {
        "type": "number",
        "format": "double",
        "minimum": 0,
        "maximum": HEADING_FULL_CIRCLE,
        "exclusiveMaximum": True,
    }
)
class HeadingField(serializers.FloatField):
    """Finite clockwise bearing, including north and excluding a second full turn."""

    def to_internal_value(self, data: Any) -> float:
        if isinstance(data, bool):
            raise serializers.ValidationError("Headings must be numbers.")
        value = super().to_internal_value(data)
        validate_headings([value])
        return value


@extend_schema_field(
    {
        "type": "array",
        "items": {
            "type": "number",
            "format": "double",
            "minimum": 0,
            "maximum": HEADING_FULL_CIRCLE,
            "exclusiveMaximum": True,
        },
        "maxItems": EXPLORATION_LEAD_MAX_HEADINGS,
    }
)
class HeadingsField(serializers.JSONField):
    """Accept a heading array, JSON-encoded for multipart and URL-encoded forms."""

    def to_internal_value(self, data: Any) -> Any:
        values = super().to_internal_value(data)
        return serializers.ListField(
            child=HeadingField(),
            max_length=EXPLORATION_LEAD_MAX_HEADINGS,
            validators=[validate_headings],
        ).run_validation(values)


class ExplorationLeadSerializer(
    SanitizedFieldsMixin, serializers.ModelSerializer[ExplorationLead]
):
    """Serializer for ExplorationLead model."""

    sanitized_fields: ClassVar[list[str]] = ["description"]

    headings = HeadingsField(required=False)

    class Meta:
        model = ExplorationLead
        fields = [
            "id",
            "description",
            "headings",
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
            "headings",
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
                "headings": instance.headings,
                "created_by": instance.created_by,
                "creation_date": instance.creation_date.isoformat(),
                "modified_date": instance.modified_date.isoformat(),
                "project": str(instance.project.id),
            },
        )
