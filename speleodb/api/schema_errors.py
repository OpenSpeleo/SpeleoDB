"""The error envelopes emitted by SpeleoDB views and DRF exceptions."""

from __future__ import annotations

from typing import Any

from drf_spectacular.utils import OpenApiResponse

API_ERROR_SCHEMA: dict[str, Any] = {
    "anyOf": [
        {
            "type": "object",
            "minProperties": 1,
            "additionalProperties": {
                "oneOf": [
                    {"type": "string"},
                    {"type": "array", "items": {"type": "string"}},
                ]
            },
        },
        {
            "type": "object",
            "required": ["error"],
            "properties": {"error": {"type": "string"}},
        },
        {
            "type": "object",
            "required": ["detail"],
            "properties": {"detail": {"type": "string"}},
        },
        {
            "type": "object",
            "required": ["errors"],
            "properties": {
                # Validation errors may be nested by serializer field/index.
                "errors": {
                    "oneOf": [
                        {"type": "object", "additionalProperties": True},
                        {"type": "array", "items": {"type": "string"}},
                    ]
                },
            },
        },
    ],
}
API_ERROR = OpenApiResponse(
    response=API_ERROR_SCHEMA, description="API request failed."
)

# DRF 3.18 serializes invalid ListSerializer rows as an index-keyed object.
# Sensor fleet creation emits either ordinary field errors or those child maps;
# valid child rows have no entry. Malformed/non-object bodies use DRF's detail.
INDEXED_SERIALIZER_ERROR = OpenApiResponse(
    response={
        "anyOf": [
            {
                "type": "object",
                "required": ["detail"],
                "properties": {"detail": {"type": "string"}},
                "additionalProperties": False,
            },
            {
                "type": "object",
                "required": ["errors"],
                "properties": {
                    "errors": {
                        "type": "object",
                        "additionalProperties": {
                            "oneOf": [
                                {"type": "array", "items": {"type": "string"}},
                                {
                                    "type": "object",
                                    "additionalProperties": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                    },
                                },
                            ]
                        },
                    }
                },
                "additionalProperties": False,
            },
        ]
    },
    description="Field or indexed child validation errors, or a malformed body.",
)
