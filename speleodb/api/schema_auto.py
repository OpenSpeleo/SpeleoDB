"""DRF schema support for the API's explicitly declared DELETE request bodies."""

from __future__ import annotations

import copy
from typing import Any
from typing import Literal
from typing import cast

from drf_spectacular.openapi import AutoSchema
from rest_framework.permissions import AllowAny

from speleodb.api.schema_errors import API_ERROR_SCHEMA


class SpeleoDBAutoSchema(AutoSchema):
    def _get_response_bodies(
        self, direction: Literal["request", "response"] = "response"
    ) -> dict[str, Any]:
        responses = super()._get_response_bodies(direction)
        codes = set()
        if (
            self.view.permission_classes
            and AllowAny not in self.view.permission_classes
        ):
            codes.add("403")
        if self.method in {"POST", "PUT", "PATCH", "DELETE"}:
            codes.add("400")
        # Object routes can fail before their handler executes, in get_object.
        if "{" in self.path and getattr(self.view, "queryset", None) is not None:
            codes.add("404")
        for code in sorted(codes):
            responses.setdefault(
                code,
                {
                    "description": "API request failed.",
                    "content": {
                        "application/json": {"schema": copy.deepcopy(API_ERROR_SCHEMA)}
                    },
                },
            )
        return responses

    def get_request_serializer(self) -> Any:
        if self.method == "DELETE":
            return None
        return super().get_request_serializer()

    def _get_request_body(self, direction: str = "request") -> dict[str, Any] | None:
        if self.method != "DELETE":
            body = super()._get_request_body(direction)  # type: ignore[no-untyped-call]
            if body:
                for media_type, media in body["content"].items():
                    media["schema"] = self._request_media_schema(
                        media["schema"], media_type
                    )
            return cast("dict[str, Any] | None", body)
        # DRF-spectacular ignores DELETE bodies even with @extend_schema.
        # Permission revocations have an explicit user/team body. Only an
        # annotation can supply a serializer here; model deletion has no body.
        serializer = self.get_request_serializer()
        if serializer is None:
            return None
        schema, required = self._get_request_for_media_type(  # type: ignore[no-untyped-call]
            serializer, direction
        )
        if schema is None:
            return None
        return {
            "required": required,
            "content": {media: {"schema": schema} for media in self.map_parsers()},
        }

    def _request_media_schema(
        self, schema: dict[str, Any], media_type: str
    ) -> dict[str, Any]:
        """Describe DRF HTML form JSON encoding and actual file transport.

        JSONField.get_value marks HTML form values as JSON strings. FileField
        requires an UploadedFile, which only the multipart parser can supply.
        Optional file fields remain absent in JSON/urlencoded representations.
        """
        reference = schema.get("$ref")
        if reference:
            component = self.registry[(reference.rsplit("/", 1)[1], "schemas")]
            source = component.schema
        else:
            source = schema
        for composition in ("anyOf", "oneOf"):
            if composition in source:
                return {
                    **source,
                    composition: [
                        self._request_media_schema(branch, media_type)
                        for branch in source[composition]
                    ],
                }
        properties = source.get("properties")
        if not properties:
            return schema
        result = copy.deepcopy(source)
        form = media_type in {
            "multipart/form-data",
            "application/x-www-form-urlencoded",
        }
        for name, field in list(result["properties"].items()):
            json_form = field.pop("x-drf-json-form", False)
            unavailable_in_form = field.pop("x-drf-form-unrepresentable", False)
            null_as_empty = field.pop("x-drf-null-as-empty", None)
            if form and unavailable_in_form:
                del result["properties"][name]
                result["required"] = [
                    key for key in result.get("required", []) if key != name
                ]
                continue
            if form and json_form:
                result["properties"][name] = {
                    "type": "string",
                    "description": "JSON-encoded value.",
                }
                continue
            if field.get("format") == "binary" and media_type != "multipart/form-data":
                if field.get("nullable"):
                    result["properties"][name] = {
                        "type": "string",
                        "nullable": True,
                        "enum": [None]
                        if media_type == "application/json"
                        else [None, ""],
                    }
                    if form:
                        result["properties"][name]["x-drf-null-as-empty"] = True
                else:
                    del result["properties"][name]
                    result["required"] = [
                        key for key in result.get("required", []) if key != name
                    ]
                continue
            if form and null_as_empty is True:
                result["properties"][name] = {
                    "anyOf": [field, {"type": "string", "maxLength": 0}],
                    "x-drf-null-as-empty": True,
                }
            elif form and null_as_empty is False:
                # HTML forms cannot distinguish null from an allowed blank
                # string. JSON remains available for explicit null clears.
                field.pop("nullable", None)
            elif form and not any(
                key in field for key in ("type", "$ref", "oneOf", "allOf", "anyOf")
            ):
                result["properties"][name] = {
                    "type": "string",
                    "description": "JSON-encoded value.",
                }
        if not result.get("required"):
            result.pop("required", None)
        return result if result != source else schema
