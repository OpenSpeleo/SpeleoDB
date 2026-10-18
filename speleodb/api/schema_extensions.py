"""Represent custom serializer behavior that DRF's field introspection cannot see."""

from __future__ import annotations

import re
from typing import Any
from typing import cast

from drf_spectacular.extensions import OpenApiSerializerExtension
from drf_spectacular.extensions import OpenApiSerializerFieldExtension
from drf_spectacular.serializers import PolymorphicProxySerializerExtension
from rest_framework import serializers

from speleodb.api.v2.serializers.api_contract import ActiveMutexSerializer
from speleodb.api.v2.serializers.exploration_lead import ExplorationLeadSerializer
from speleodb.api.v2.serializers.geojson_contract import (
    CylinderInstallFeatureSerializer,
)
from speleodb.api.v2.serializers.geojson_contract import (
    ExperimentRecordFeatureSerializer,
)
from speleodb.api.v2.serializers.geojson_contract import (
    ExplorationLeadFeatureSerializer,
)
from speleodb.api.v2.serializers.geojson_contract import LandmarkFeatureSerializer
from speleodb.api.v2.serializers.geojson_contract import StationFeatureSerializer
from speleodb.api.v2.serializers.geojson_contract import StationTagSummarySerializer
from speleodb.api.v2.serializers.gis_view import GISViewSerializer
from speleodb.api.v2.serializers.landmark import LandmarkSerializer
from speleodb.api.v2.serializers.project import ProjectSerializer
from speleodb.api.v2.serializers.project_commit import ProjectCommitSerializer
from speleodb.api.v2.serializers.station import BaseStationSerializerMixin
from speleodb.api.v2.serializers.summary_contract import (
    CompletedExportSummarySerializer,
)
from speleodb.api.v2.serializers.summary_contract import FailedExportSummarySerializer
from speleodb.gis.geometry_validation import GIS_GEOMETRY_MAX_VERTICES


class CustomChoiceSchema(OpenApiSerializerFieldExtension):  # type: ignore[no-untyped-call]
    target_class = "speleodb.utils.serializer_fields.CustomChoiceField"

    def map_serializer_field(self, auto_schema: Any, direction: str) -> dict[str, Any]:
        field = self.target
        values = [
            str(key) if field.field_name == "country" else field.to_representation(key)
            for key in field.choices
        ]
        if direction == "request" and field.field_name != "country":
            patterns = [
                "".join(
                    f"[{character.upper()}{character.lower()}]"
                    if character.isalpha()
                    else character
                    for character in str(value)
                )
                for value in values
            ]
            return {
                "type": "string",
                "pattern": "^(?:" + "|".join(patterns) + ")$",
                "description": "Case-insensitive choice: " + ", ".join(values),
            }
        return {"type": "string", "enum": values}


class FormattedDateTimeSchema(OpenApiSerializerFieldExtension):  # type: ignore[no-untyped-call]
    target_class = "rest_framework.serializers.DateTimeField"

    def map_serializer_field(self, auto_schema: Any, direction: str) -> dict[str, Any]:
        if direction == "response" and getattr(self.target, "format", None) == (
            "%Y/%m/%d %H:%M"
        ):
            return {"type": "string", "pattern": r"^\d{4}/\d{2}/\d{2} \d{2}:\d{2}$"}
        return cast(
            "dict[str, Any]",
            auto_schema._map_serializer_field(  # noqa: SLF001
                self.target, direction, bypass_extensions=True
            ),
        )


class ModelRepresentationSchema(OpenApiSerializerExtension):  # type: ignore[no-untyped-call]
    target_class = "rest_framework.serializers.ModelSerializer"
    match_subclasses = True
    priority = -1

    def map_serializer(self, auto_schema: Any, direction: str) -> dict[str, Any]:
        wire_serializers = {
            "GISViewCreateUpdateSerializer": GISViewSerializer,
            "StationGeoJSONSerializer": StationFeatureSerializer,
            "ExplorationLeadGeoJSONSerializer": ExplorationLeadFeatureSerializer,
            "LandmarkGeoJSONSerializer": LandmarkFeatureSerializer,
            "CylinderInstallGeoJSONSerializer": CylinderInstallFeatureSerializer,
        }
        wire = wire_serializers.get(type(self.target).__name__)
        if wire is not None and direction == "response":
            return cast(
                "dict[str, Any]",
                auto_schema._map_serializer(wire(), direction),  # noqa: SLF001
            )
        schema: dict[str, Any] = auto_schema._map_serializer(  # noqa: SLF001
            self.target, direction, bypass_extensions=True
        )
        properties = schema.get("properties", {})
        serializer_name = type(self.target).__name__
        if serializer_name == "UserExportSerializer":
            properties["summary"] = {
                "anyOf": [
                    {"type": "object", "maxProperties": 0},
                    auto_schema.resolve_serializer(
                        CompletedExportSummarySerializer(), direction
                    ).ref,
                    auto_schema.resolve_serializer(
                        FailedExportSummarySerializer(), direction
                    ).ref,
                ],
                "readOnly": True,
            }
        if serializer_name in {"GISGeometrySerializer", "GISGeometryUpdateSerializer"}:
            position = {
                "type": "array",
                "minItems": 2,
                "maxItems": 2,
                "items": {"type": "number"},
            }
            line = {
                "type": "array",
                "minItems": 2,
                "maxItems": GIS_GEOMETRY_MAX_VERTICES,
                "items": position,
            }
            ring = {
                "type": "array",
                "minItems": 4,
                "maxItems": GIS_GEOMETRY_MAX_VERTICES + 1,
                "items": position,
            }
            properties["geojson"] = {
                "oneOf": [
                    {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "type": {"type": "string", "enum": ["LineString"]},
                            "coordinates": line,
                        },
                        "required": ["type", "coordinates"],
                    },
                    {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "type": {"type": "string", "enum": ["Polygon"]},
                            "coordinates": {
                                "type": "array",
                                "minItems": 1,
                                "maxItems": 1,
                                "items": ring,
                            },
                        },
                        "required": ["type", "coordinates"],
                    },
                ],
                "description": (
                    "WGS84 2D coordinates. Polygon has one closed simple outer ring "
                    "and no holes. Server additionally validates coordinate bounds, "
                    "topology, and bounding-box area."
                ),
            }
        if serializer_name == "ExperimentRecordSerializer":
            properties["data"] = {
                "type": "object",
                "additionalProperties": {
                    "anyOf": [
                        {"type": "string", "nullable": True},
                        {"type": "number"},
                        {"type": "boolean"},
                    ]
                },
                "description": (
                    "Values keyed by experiment field UUID; validated using that "
                    "experiment's field definitions."
                ),
            }
        if direction != "response":
            if (
                isinstance(self.target, BaseStationSerializerMixin)
                or serializer_name == "ExplorationLeadSerializer"
            ):
                for name in ("latitude", "longitude"):
                    properties[name] = {
                        "oneOf": [
                            {"type": "number"},
                            {
                                "type": "string",
                                "pattern": (
                                    r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)"
                                    r"(?:[eE][+-]?\d+)?$"
                                ),
                            },
                        ],
                        "description": (
                            "Numeric coordinate; rounded to seven decimal "
                            "places before validation."
                        ),
                    }
            if serializer_name == "SensorFleetCreateRequestSerializer":
                properties["sensors"]["x-drf-form-unrepresentable"] = True
            if serializer_name == "GISViewCreateUpdateSerializer":
                properties["projects"]["x-drf-form-unrepresentable"] = True
            if serializer_name == "ExperimentSerializer":
                for name in ("start_date", "end_date"):
                    properties[name] = {
                        "anyOf": [properties[name], {"type": "string", "maxLength": 0}]
                    }
                field_list = properties["experiment_fields"]
                field_list.pop("nullable", None)
                definition = field_list["items"]
                definition["properties"]["uuid"] = {
                    "type": "string",
                    "format": "uuid",
                    "description": "Existing-field identifier; id takes precedence.",
                }
                definition["properties"]["type"]["enum"] = [
                    "text",
                    "number",
                    "date",
                    "boolean",
                    "select",
                ]
                definition["required"] = ["name", "type"]
                properties["experiment_fields"] = {
                    "anyOf": [
                        field_list,
                        {"type": "object", "additionalProperties": definition},
                        {"type": "string", "nullable": True, "enum": [None]},
                    ],
                    "x-drf-form-unrepresentable": True,
                }
            for name, field in self.target.fields.items():
                if name in properties and isinstance(field, serializers.JSONField):
                    properties[name]["x-drf-json-form"] = True
                elif name in properties and field.allow_null:
                    properties[name]["x-drf-null-as-empty"] = not getattr(
                        field, "allow_blank", False
                    )
            return schema
        if serializer_name == "ExperimentSerializer":
            fields = properties["experiment_fields"]
            fields.pop("nullable", None)
            fields["items"]["required"] = ["id", "name", "type", "required", "order"]
            fields["items"]["properties"]["type"]["enum"] = [
                "text",
                "number",
                "date",
                "boolean",
                "select",
            ]
        # Model fields with defaults/blank=True are optional on input but are
        # still serialized on every response. Only explicit representation
        # omissions below remain optional.
        schema["required"] = sorted(properties)
        if (
            type(self.target).to_representation
            is serializers.ModelSerializer.to_representation
        ):
            # DRF's unchanged implementation iterates exactly declared fields.
            # Custom representations can add keys and require their own audit.
            schema["additionalProperties"] = False
        for name, field in self.target.fields.items():
            if name not in properties:
                continue
            if isinstance(field, serializers.FileField):
                # File validators constrain uploaded filenames, not the signed
                # storage URLs returned by FileField.to_representation.
                for constraint in ("pattern", "maxLength", "minLength"):
                    properties[name].pop(constraint, None)
            if isinstance(field, serializers.EmailField) and field.allow_blank:
                properties[name].pop("format", None)
            if (
                isinstance(field, serializers.DateTimeField)
                and getattr(field, "format", None) == "%Y/%m/%d %H:%M"
            ):
                properties[name].pop("format", None)
                properties[name]["pattern"] = r"^\d{4}/\d{2}/\d{2} \d{2}:\d{2}$"
        if isinstance(self.target, ProjectCommitSerializer):
            properties["authored_date"] = {
                "type": "string",
                "pattern": r"^\d{4}/\d{2}/\d{2} \d{2}:\d{2}$",
            }
            properties["tree"] = {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        name: {"type": "string"}
                        for name in ("mode", "object", "path", "type")
                    },
                    "required": ["mode", "object", "path", "type"],
                },
            }
        if type(self.target).__name__ == "PluginReleaseSerializer":
            # Python named captures are not valid ECMAScript pattern syntax.
            # Captures have no semantic role in schema validation.
            version = properties.get("plugin_version", {})
            if "pattern" in version:
                version["pattern"] = re.sub(r"\(\?P<[^>]+>", "(?:", version["pattern"])
        if isinstance(
            self.target,
            (
                ProjectSerializer,
                BaseStationSerializerMixin,
                ExplorationLeadSerializer,
                LandmarkSerializer,
            ),
        ):
            for coordinate in ("latitude", "longitude"):
                if coordinate in properties:
                    properties[coordinate] = {
                        "type": "number",
                        "format": "double",
                        "nullable": properties[coordinate].get("nullable", False),
                    }
        if isinstance(self.target, ProjectSerializer):
            schema["required"] = [
                name
                for name in schema["required"]
                if name not in {"latitude", "longitude", "n_commits", "permission"}
            ]
            properties["latest_commit"] = {
                "allOf": [
                    auto_schema.resolve_serializer(
                        ProjectCommitSerializer(), direction
                    ).ref
                ],
                "nullable": True,
            }
            properties["active_mutex"] = {
                "allOf": [
                    auto_schema.resolve_serializer(
                        ActiveMutexSerializer(), direction
                    ).ref
                ],
                "nullable": True,
            }
            for name in ("latitude", "longitude"):
                if name in properties:
                    properties[name].pop("nullable", None)
        if isinstance(self.target, BaseStationSerializerMixin) and "tag" in properties:
            properties["tag"] = {
                "allOf": [
                    auto_schema.resolve_serializer(
                        StationTagSummarySerializer(), direction
                    ).ref
                ],
                "nullable": True,
            }
        return schema


class UntaggedInputUnionSchema(PolymorphicProxySerializerExtension):  # type: ignore[no-untyped-call]
    """Untagged update inputs can match multiple concrete serializers."""

    target_class = "drf_spectacular.utils.PolymorphicProxySerializer"
    priority = 1

    def map_serializer(self, auto_schema: Any, direction: str) -> dict[str, Any]:
        schema = super().map_serializer(auto_schema, direction)  # type: ignore[no-untyped-call]
        if direction == "request" and self.target.resource_type_field_name is None:
            schema["anyOf"] = schema.pop("oneOf")
        return cast("dict[str, Any]", schema)


class DecimalInputSchema(OpenApiSerializerFieldExtension):  # type: ignore[no-untyped-call]
    target_class = "rest_framework.serializers.DecimalField"
    match_subclasses = True

    def map_serializer_field(self, auto_schema: Any, direction: str) -> dict[str, Any]:
        schema: dict[str, Any] = auto_schema._map_serializer_field(  # noqa: SLF001
            self.target, direction, bypass_extensions=True
        )
        if direction == "request":
            return {"oneOf": [schema, {"type": "number"}]}
        return schema


class ExperimentRecordFeatureSchema(OpenApiSerializerExtension):  # type: ignore[no-untyped-call]
    target_class = (
        "speleodb.api.v2.serializers.experiment.ExperimentRecordGISSerializer"
    )

    def map_serializer(self, auto_schema: Any, direction: str) -> dict[str, Any]:
        schema = cast(
            "dict[str, Any]",
            auto_schema._map_serializer(  # noqa: SLF001
                ExperimentRecordFeatureSerializer(), direction
            ),
        )
        schema["properties"]["properties"] = {
            "type": "object",
            "properties": {
                "station_id": {"type": "string", "format": "uuid"},
                "station_name": {"type": "string"},
            },
            "required": ["station_id", "station_name"],
            "additionalProperties": {},
            "description": (
                "Station identity plus values keyed by experiment field UUID."
            ),
        }
        return schema
