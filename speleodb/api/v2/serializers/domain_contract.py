"""Operation-specific domain request declarations, without runtime validation."""

from __future__ import annotations

from typing import Any

from speleodb.api.v2.serializers.landmark_collection import LandmarkCollectionSerializer
from speleodb.api.v2.serializers.station import StationResourceSerializer
from speleodb.gis.models.experiment import MandatoryFieldUuid


class LandmarkCollectionUpdateRequestSerializer(LandmarkCollectionSerializer):
    """Schema identity for the personal/shared PUT request variants."""


class StationResourceCreateRequestSerializer(StationResourceSerializer):
    """Schema identity for note content versus mandatory uploaded files."""


_EXPERIMENT_RECORD_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        MandatoryFieldUuid.MEASUREMENT_DATE.value: {
            "type": "string",
            "minLength": 1,
            "description": (
                "Mandatory measurement date, parsed as an ISO date or datetime."
            ),
        }
    },
    "additionalProperties": {
        "anyOf": [
            {"type": "string", "nullable": True},
            {"type": "number"},
            {"type": "boolean"},
        ]
    },
    "description": (
        "Keys must be field UUIDs defined by the experiment. Values must "
        "match each definition: string, finite number, boolean, ISO date "
        "or datetime string, or a configured select option. Null/empty "
        "values are allowed only for optional fields. POST and PUT must "
        "provide every required editable field; PATCH merges with existing "
        "values. The server restores submitter identity regardless of input."
    ),
}

EXPERIMENT_RECORD_REQUEST: dict[str, Any] = {
    "application/json": _EXPERIMENT_RECORD_SCHEMA,
}

EXPERIMENT_RECORD_REPLACEMENT_REQUEST: dict[str, Any] = {
    "application/json": {
        **_EXPERIMENT_RECORD_SCHEMA,
        "required": [MandatoryFieldUuid.MEASUREMENT_DATE.value],
    }
}

EXPERIMENT_RECORD_CREATE_REQUEST: dict[str, Any] = {
    **EXPERIMENT_RECORD_REPLACEMENT_REQUEST,
    **{
        media_type: {
            **EXPERIMENT_RECORD_REPLACEMENT_REQUEST["application/json"],
            "additionalProperties": {"type": "string"},
            "description": (
                _EXPERIMENT_RECORD_SCHEMA["description"]
                + " Form inputs are text: populated number/boolean experiment "
                "fields require JSON instead. Successful form creation stores each "
                "text value and the server-owned submitter email as nonempty arrays. "
                "Subsequent PUT/PATCH fails validation because the submitter array "
                "is preserved. Create records with JSON for editable scalar values."
            ),
        }
        for media_type in ("multipart/form-data", "application/x-www-form-urlencoded")
    },
}
