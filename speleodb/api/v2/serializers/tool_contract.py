"""Wire inputs for spreadsheet tools, before their internal shot conversion."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from typing import Any

from drf_spectacular.extensions import OpenApiSerializerFieldExtension
from drf_spectacular.plumbing import ResolvedComponent
from rest_framework import serializers

from speleodb.api.schema_numeric import FLOAT_EXPONENT_PATTERN
from speleodb.api.schema_numeric import FLOAT_MANTISSA_PATTERN
from speleodb.api.v2.views.tmp_utils import CompassShot
from speleodb.api.v2.views.tmp_utils import DeclinationObj

if TYPE_CHECKING:
    from pydantic import BaseModel


def openapi_model_schema(model: type[BaseModel]) -> dict[str, Any]:
    """Project a tool's Pydantic input constraints into the OAS 3.0 dialect."""
    schema: dict[str, Any] = model.model_json_schema(mode="validation")

    def convert(value: Any) -> None:
        if isinstance(value, dict):
            if value.get("type") == "null":
                value.update(type="string", nullable=True, enum=[None])
            for exclusive, bound in (
                ("exclusiveMinimum", "minimum"),
                ("exclusiveMaximum", "maximum"),
            ):
                if exclusive in value and not isinstance(value[exclusive], bool):
                    value[bound] = value[exclusive]
                    value[exclusive] = True
            for child in value.values():
                convert(child)
        elif isinstance(value, list):
            for child in value:
                convert(child)

    convert(schema)
    return schema


class JSONTextField(serializers.CharField):
    """Schema-only field for a JSON object transported as multipart text."""

    def __init__(
        self, *, model: type[BaseModel], example: dict[str, Any], **kwargs: Any
    ) -> None:
        self.model = model
        self.example = example
        super().__init__(**kwargs)


class JSONTextFieldSchema(OpenApiSerializerFieldExtension):  # type: ignore[no-untyped-call]
    target_class = "speleodb.api.v2.serializers.tool_contract.JSONTextField"

    def map_serializer_field(self, auto_schema: Any, direction: str) -> dict[str, Any]:
        field = self.target
        # drf-spectacular exposes this constructor without type annotations.
        component = ResolvedComponent(  # type: ignore[no-untyped-call]
            name=field.model.__name__,
            type=ResolvedComponent.SCHEMA,
            object=field.model,
            schema=openapi_model_schema(field.model),
        )
        auto_schema.registry.register_on_missing(component)
        return {
            "type": "string",
            "description": (
                "JSON-encoded " + field.model.__name__ + ". Send a text form field, "
                "not a file part. The x-json-schema reference defines the decoded "
                "object. survey_date must not be in the future and must be non-null "
                "when fix_dmp is true. All seven configuration keys are required."
            ),
            "x-json-schema": component.ref,
            "example": json.dumps(field.example),
        }


def numeric_cell(
    *, blank: bool = False, bounds: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Spreadsheet cells arrive as numbers or textual numbers."""
    numeric_text = rf"\s*[+-]?{FLOAT_MANTISSA_PATTERN}{FLOAT_EXPONENT_PATTERN}\s*"
    textual: dict[str, Any] = {
        "type": "string",
        "pattern": "^" + numeric_text + "$",
    }
    if blank:
        textual["nullable"] = True
        textual["pattern"] = "^(?:" + numeric_text + ")?$"
    number = {"type": "number", **(bounds or {})}
    return {
        "oneOf": [
            number,
            textual,
            {"type": "boolean", "description": "Coerced to 1 for true or 0 for false."},
        ]
    }


def spreadsheet_input(*, compass: bool) -> dict[str, Any]:
    """The final row is a station/depth terminator, not a measured shot."""
    cells = {
        name: numeric_cell(blank=True)
        for name in ("depth", "length", "azimuth", "left", "right", "up", "down")
    }
    cells["azimuth"] = numeric_cell()
    shot_required = ["depth", "length", "azimuth", "left", "right", "up", "down"]
    terminal: dict[str, Any] = {
        "type": "object",
        "properties": {"depth": numeric_cell(blank=True)},
        "required": ["depth"],
        "description": "Final depth row. Other cells are ignored for DMP output.",
    }
    if compass:
        normalized = openapi_model_schema(CompassShot)["properties"]
        cells["depth"] = numeric_cell()
        for name in ("length", "azimuth", "left", "right", "up", "down"):
            cells[name] = numeric_cell(blank=name in {"left", "right", "up", "down"})
            cells[name]["x-normalized-schema"] = normalized[name]
            cells[name]["description"] = (
                "Converted to a number and rounded to two decimal places before "
                "the x-normalized-schema constraints are applied. Empty/null LRUD "
                "cells remain null."
            )
        cells.update(
            {
                "station": {"type": "string", "minLength": 1, "maxLength": 32},
                "flags": {
                    "type": "string",
                    "nullable": True,
                    "pattern": r"^[#\\|]*\s*[PCLXS]*\s*#*$",
                    "x-normalized-schema": normalized["flags"],
                    "description": (
                        "Leading #, backslash and | characters and trailing # "
                        "characters are removed before trimming whitespace. "
                        "Remaining characters must be uppercase P/C/L/X/S; "
                        "duplicates are removed and flags sorted alphabetically."
                    ),
                },
                "comment": {"type": "string", "nullable": True, "maxLength": 256},
            }
        )
        shot_required = ["depth", "station", "length", "azimuth"]
        terminal = {
            "type": "object",
            "properties": {
                "station": cells["station"],
                "depth": cells["depth"],
                **{
                    name: {
                        "anyOf": [
                            {"type": "number", "enum": [0]},
                            {"type": "string", "nullable": True, "enum": ["", None]},
                            {"type": "boolean", "enum": [False]},
                            {"type": "array", "maxItems": 0, "items": {}},
                            {"type": "object", "maxProperties": 0},
                        ]
                    }
                    for name in (
                        "length",
                        "azimuth",
                        "left",
                        "right",
                        "up",
                        "down",
                        "flags",
                        "comment",
                    )
                },
            },
            "required": ["station", "depth"],
            "description": (
                "Final station/depth row. Measurement, LRUD, flag and comment "
                "cells must be absent or falsey: empty/null/zero/false, an empty "
                "array, or an empty object."
            ),
        }
    properties: dict[str, Any] = {
        "shots": {
            "type": "array",
            "items": {
                "anyOf": [
                    {"type": "object", "properties": cells, "required": shot_required},
                    terminal,
                ]
            },
            "description": (
                "Rows in survey order. Every measured row supplies length and azimuth; "
                "LRUD cells accept numeric values or empty/null cells. All rows except "
                "the last must use the measured-row variant; only the last uses the "
                "terminal variant. OpenAPI 3.0 cannot express that positional rule. "
                + (
                    "The terminal row supplies station/depth and falsey measurement "
                    "cells. Compass LRUD keys are optional. "
                    "Length must cover the absolute "
                    "depth difference to the next row; the normalized difference "
                    "must be between -1000 and 1000."
                    if compass
                    else "DMP measured rows require all four LRUD keys, "
                    "even when empty. "
                    "The terminal row supplies depth; its other cells are ignored."
                )
            ),
        },
        "survey_date": {"type": "string", "format": "date"},
        "unit": {"type": "string", "enum": ["feet", "meters"]},
    }
    required = ["shots", "survey_date", "unit"]
    if compass:
        coordinate_schemas = openapi_model_schema(DeclinationObj)["properties"]
        properties["survey_date"]["description"] = (
            "Survey date must not be in the future."
        )
        properties["shots"]["minItems"] = 2
        properties.update(
            {
                "cave_name": {"type": "string", "minLength": 1, "maxLength": 64},
                "survey_name": {"type": "string", "minLength": 1, "maxLength": 64},
                "survey_team": {"type": "array", "items": {"type": "string"}},
                "comment": {"type": "string", "nullable": True, "maxLength": 512},
                **{
                    name: {
                        **numeric_cell(
                            bounds={
                                key: value
                                for key, value in coordinate_schemas[name].items()
                                if key in {"minimum", "maximum"}
                            }
                        ),
                        "description": (
                            "WGS84 coordinate. Numeric text is coerced before the "
                            "same coordinate bounds are checked."
                        ),
                    }
                    for name in ("latitude", "longitude")
                },
            }
        )
        required.extend(
            [
                "cave_name",
                "survey_name",
                "survey_team",
                "comment",
                "latitude",
                "longitude",
            ]
        )
    else:
        regular_shots = properties["shots"]
        description = regular_shots.pop("description")
        properties["shots"] = {
            "anyOf": [
                {"type": "array", "maxItems": 1, "items": {}},
                regular_shots,
            ],
            "description": (
                description + " With zero or one input row there are no measured "
                "pairs: the row is ignored and output contains only the end-of-survey "
                "marker. The ignored row may have any JSON value."
            ),
        }
        properties["unit"] = {
            "type": "string",
            "description": (
                "feet converts to meters; other values are interpreted as meters."
            ),
        }
        properties["direction"] = {
            "type": "string",
            "description": (
                "in selects inward direction; other values select outward direction."
            ),
        }
        required.append("direction")
    return {"type": "object", "properties": properties, "required": required}
