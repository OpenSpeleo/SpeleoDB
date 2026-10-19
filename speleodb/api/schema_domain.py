"""Schema projections for domain validation performed outside DRF field metadata.

These functions describe existing serializers; they never validate API requests.
Context-dependent rules remain documented alongside the representable shapes.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from django.conf import settings

from speleodb.api.schema_numeric import FLOAT_EXPONENT_PATTERN
from speleodb.api.schema_numeric import FLOAT_MANTISSA_PATTERN
from speleodb.api.v2.serializers.station import BaseStationSerializerMixin
from speleodb.common.enums import StationResourceType


def _without_fields(schema: dict[str, Any], *names: str) -> None:
    for name in names:
        schema.get("properties", {}).pop(name, None)
    required = [name for name in schema.get("required", []) if name not in names]
    if required:
        schema["required"] = required
    else:
        schema.pop("required", None)


def _experiment_definition(*, ordered: bool) -> dict[str, Any]:
    properties: dict[str, Any] = {
        "name": {"type": "string", "minLength": 1},
        "type": {"type": "string"},
        "required": {
            "anyOf": [
                {"type": "boolean"},
                {"type": "integer", "enum": [0, 1]},
                {
                    "type": "string",
                    "pattern": (
                        r"^(?:[01]|[fFnNtTyY]|[nN][oO]|[oO][nN]|[oO][fF][fF]"
                        r"|[yY][eE][sS]|[tT][rR][uU][eE]|[fF][aA][lL][sS][eE])$"
                    ),
                },
            ],
            "default": False,
            "x-normalized-schema": {"type": "boolean"},
            "description": (
                "Pydantic boolean conversion accepts booleans, 0/1 and "
                "case-insensitive 0/1, f/n/no/off/false, t/y/on/yes/true text."
            ),
        },
        "order": {
            "anyOf": [
                {"type": "integer", "minimum": 0},
                {"type": "boolean"},
                {
                    "type": "string",
                    "pattern": (
                        r"^\s*(?:\+?[0-9](?:_?[0-9])*(?:\.0+)?"
                        r"|-0(?:_?0)*(?:\.0+)?)\s*$"
                    ),
                },
            ],
            "x-normalized-schema": {"type": "integer", "minimum": 0},
            "description": (
                "Nonnegative integer after Pydantic conversion. Whole numeric "
                "values, booleans and integral decimal strings are accepted; "
                "strings support surrounding whitespace, signs, underscores "
                "between digits and a zero fractional part. Defaults to array "
                "position in lists."
            ),
        },
    }
    if not ordered:
        for key in ("id", "uuid"):
            properties[key] = {
                "type": "string",
                "nullable": True,
                "description": (
                    "Existing UUID or temp_ key; a nonempty id takes precedence "
                    "over uuid. Missing/empty identifiers create a field."
                ),
            }
    required = ["name", "type", *(["order"] if ordered else [])]
    common: dict[str, Any] = {
        "type": "object",
        "properties": properties,
        "required": required,
    }
    select = deepcopy(common)
    select["properties"]["type"]["enum"] = ["select"]
    select["properties"]["options"] = {
        "type": "array",
        "items": {"type": "string"},
        "minItems": 1,
    }
    select["required"].append("options")
    scalar = deepcopy(common)
    scalar["properties"]["type"]["enum"] = ["text", "number", "date", "boolean"]
    scalar["properties"]["options"] = {
        "type": "string",
        "nullable": True,
        "enum": [None],
    }
    variants = [select, scalar]
    if not ordered:
        # The list adapter skips unnamed/blank entries before field validation.
        variants.append(
            {
                "type": "object",
                "properties": {"name": {"type": "string", "pattern": r"^\s*$"}},
                "description": (
                    "An omitted or blank name makes this list entry ignored."
                ),
            }
        )
    return {"anyOf": variants}


def _experiment_fields() -> dict[str, Any]:
    return {
        "anyOf": [
            {"type": "array", "items": _experiment_definition(ordered=False)},
            {
                "type": "object",
                "additionalProperties": _experiment_definition(ordered=True),
            },
        ],
        "x-drf-form-unrepresentable": True,
        "description": (
            "List definitions infer order from position; dictionary definitions "
            "require order and UUID or temp_ keys. Names are sanitized and must "
            "remain nonempty and unique. Existing type, required and options are "
            "immutable. PUT with existing IDs must include every existing field. "
            "An empty list preserves fields on update and creates only mandatory "
            "fields on creation. Null is rejected."
        ),
    }


def _resource_creation(schema: dict[str, Any]) -> dict[str, Any]:
    note = deepcopy(schema)
    note["properties"]["resource_type"] = {
        "type": "string",
        "enum": [StationResourceType.NOTE.value],
    }
    note["properties"]["text_content"]["minLength"] = 1
    note["required"] = sorted({*note.get("required", []), "text_content"})
    for name in ("file", "miniature"):
        note["properties"][name] = {
            "type": "string",
            "nullable": True,
            "enum": [None],
            "x-drf-null-as-empty": True,
        }
    uploaded = deepcopy(schema)
    uploaded["properties"]["resource_type"] = {
        "type": "string",
        "enum": [
            StationResourceType.PHOTO.value,
            StationResourceType.VIDEO.value,
            StationResourceType.DOCUMENT.value,
        ],
    }
    uploaded["properties"]["file"].pop("nullable", None)
    uploaded["properties"]["file"].pop("x-drf-null-as-empty", None)
    uploaded["properties"]["file"]["description"] = (
        "Uploaded file required. Photo: jpg/jpeg/png/gif/bmp/webp/heic/heif; "
        "video: mp4/avi/mov/wmv/flv/webm; document: pdf/doc/docx/txt/rtf. "
        f"Maximum {settings.DJANGO_UPLOAD_INDIVIDUAL_FILESIZE_MB_LIMIT} MiB."
    )
    uploaded["required"] = sorted({*uploaded.get("required", []), "file"})
    return {
        "anyOf": [note, uploaded],
        "description": (
            "Notes require nonempty sanitized text and no files. Other resource "
            "types require an uploaded file. Resource type cannot later change."
        ),
    }


def project_domain_request_schema(
    serializer: Any, schema: dict[str, Any], method: str
) -> dict[str, Any]:
    """Apply domain-specific input projections after generic DRF metadata."""
    if method not in {"POST", "PUT", "PATCH", "DELETE"}:
        return schema
    name = type(serializer).__name__
    properties = schema.get("properties", {})
    if isinstance(serializer, BaseStationSerializerMixin) or name in {
        "ExplorationLeadSerializer",
        "LandmarkSerializer",
    }:
        for coordinate in ("latitude", "longitude"):
            if coordinate in properties:
                limit = 90 if coordinate == "latitude" else 180
                properties[coordinate] = {
                    "oneOf": [
                        {"type": "number"},
                        {"type": "boolean", "x-drf-form-unrepresentable": True},
                        {
                            "type": "string",
                            "pattern": (
                                rf"^\s*[+-]?{FLOAT_MANTISSA_PATTERN}"
                                rf"{FLOAT_EXPONENT_PATTERN}\s*$"
                            ),
                        },
                    ],
                    "description": (
                        "Numeric coordinate (booleans become 0/1; numeric "
                        "strings accept digit-separating underscores), rounded "
                        "to seven decimal places "
                        f"before validation within [-{limit}, {limit}]."
                    ),
                }
    if name == "GISGeometryUpdateSerializer":
        schema["required"] = sorted({*schema.get("required", []), "expected_revision"})
    if name in {
        "CylinderFleetSerializer",
        "SensorFleetSerializer",
        "SensorFleetCreateRequestSerializer",
        "LandmarkCollectionSerializer",
        "LandmarkCollectionUpdateRequestSerializer",
    }:
        _without_fields(schema, "created_by")
    if name == "ExperimentSerializer":
        for field in ("start_date", "end_date"):
            properties[field] = {
                "anyOf": [properties[field], {"type": "string", "maxLength": 0}]
            }
        properties["experiment_fields"] = _experiment_fields()
    if name == "LandmarkCollectionUpdateRequestSerializer":
        return {
            "anyOf": [
                schema,
                {
                    "type": "object",
                    "properties": {"color": deepcopy(properties["color"])},
                    "additionalProperties": False,
                },
            ],
            "description": (
                "Shared collection PUT requires name. Personal collection PUT "
                "accepts only color, including an empty object; all other "
                "properties are rejected for personal collections."
            ),
        }
    if name == "StationResourceCreateRequestSerializer":
        return _resource_creation(schema)
    if name == "StationResourceSerializer" and "resource_type" in properties:
        properties["resource_type"]["description"] = (
            "Must equal the existing resource type; it cannot be changed. "
            "Omitted file/text retains the existing content on update."
        )
    return schema
