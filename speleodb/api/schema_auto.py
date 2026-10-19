"""DRF schema support for the API's explicitly declared DELETE request bodies."""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING
from typing import Any
from typing import Literal
from typing import cast

from drf_spectacular.openapi import AutoSchema
from drf_spectacular.utils import OpenApiResponse
from rest_framework import serializers
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import AllowAny
from rest_framework.renderers import BrowsableAPIRenderer
from rest_framework.settings import api_settings

from speleodb.api.schema_errors import API_ERROR_SCHEMA

if TYPE_CHECKING:
    from rest_framework.views import APIView


def drf_transport_parameters(view: APIView, method: str) -> list[dict[str, Any]]:
    """Machine representation selection and session-authenticated CSRF inputs."""
    parameters: list[dict[str, Any]] = []
    formats = list(
        dict.fromkeys(
            renderer.format
            for renderer in view.get_renderers()
            if not isinstance(renderer, BrowsableAPIRenderer)
        )
    )
    if api_settings.URL_FORMAT_OVERRIDE and formats:
        parameters.append(
            {
                "in": "query",
                "name": api_settings.URL_FORMAT_OVERRIDE,
                "schema": {"type": "string", "enum": formats},
                "description": "DRF machine-response renderer selection.",
            }
        )
    if method.upper() not in {"GET", "HEAD", "OPTIONS"} and any(
        isinstance(authenticator, SessionAuthentication)
        for authenticator in view.get_authenticators()
    ):
        parameters.append(
            {
                "in": "header",
                "name": "X-CSRFToken",
                "schema": {"type": "string"},
                "description": (
                    "Required with authenticated cookie sessions unless the "
                    "csrfmiddlewaretoken form field supplies the CSRF token. "
                    "Token and Bearer authentication do not require it."
                ),
            }
        )
    return parameters


def project_drf_responses(
    responses: dict[str, Any],
    view: APIView,
    method: str,
    *,
    consumes_body: bool = False,
) -> dict[str, Any]:
    """Add errors produced by DRF before normal handler response construction.

    HTML API-browser representations are UI, outside the machine contract. A
    failed format/content negotiation falls back to the first configured renderer.
    Successful FileResponse/streaming results retain their declared media.
    """
    result = copy.deepcopy(responses)
    codes = {"404", "406"}
    if view.authentication_classes or (
        view.permission_classes and AllowAny not in view.permission_classes
    ):
        codes.add("403")
    if consumes_body and method.upper() in {"POST", "PUT", "PATCH", "DELETE"}:
        codes.update({"400", "415"})
    renderers = [
        renderer
        for renderer in view.get_renderers()
        if not isinstance(renderer, BrowsableAPIRenderer)
    ]
    for code in sorted(codes):
        response = result.setdefault(code, {"description": "API request failed."})
        content = response.setdefault("content", {})
        framework_schema: dict[str, Any] = {
            "type": "object",
            "properties": {"detail": {"type": "string"}},
            "required": ["detail"],
            "additionalProperties": False,
        }
        for renderer in renderers[:1] if code == "406" else renderers:
            media = content.setdefault(renderer.media_type, {})
            existing = media.get("schema")
            if existing is None:
                media["schema"] = (
                    copy.deepcopy(API_ERROR_SCHEMA)
                    if code == "400"
                    else framework_schema
                )
            elif existing not in (API_ERROR_SCHEMA, framework_schema):
                media["schema"] = {"anyOf": [existing, framework_schema]}
    for response in result.values():
        if any(
            media.get("schema", {}).get("format") == "binary"
            for media in response.get("content", {}).values()
        ):
            response.setdefault("headers", {}).setdefault(
                "Content-Disposition",
                {
                    "description": "Attachment disposition and download filename.",
                    "schema": {"type": "string"},
                },
            )
    return result


class SpeleoDBAutoSchema(AutoSchema):
    def _insert_field_validators(self, field: Any, schema: dict[str, Any]) -> None:
        super()._insert_field_validators(field, schema)  # type: ignore[no-untyped-call]
        if (
            isinstance(field, serializers.FileField)
            and schema.get("format") == "binary"
        ):
            # DRF validates the upload filename, not a regex/length of its bytes.
            for constraint in ("pattern", "minLength", "maxLength"):
                if constraint in schema:
                    schema["x-filename-" + constraint] = schema.pop(constraint)

    def _get_response_for_code(
        self,
        serializer: Any,
        status_code: str,
        media_types: list[str] | None = None,
        direction: str = "response",
    ) -> dict[str, Any]:
        response: dict[str, Any] = super()._get_response_for_code(  # type: ignore[no-untyped-call]
            serializer, status_code, media_types, direction
        )
        source = (
            serializer.response
            if isinstance(serializer, OpenApiResponse)
            else serializer
        )
        if isinstance(source, serializers.ListSerializer):
            for media in response.get("content", {}).values():
                schema = media.get("schema", {})
                if schema.get("type") == "array":
                    for attribute, constraint in (
                        ("min_length", "minItems"),
                        ("max_length", "maxItems"),
                    ):
                        if (value := getattr(source, attribute, None)) is not None:
                            schema[constraint] = value
        return response

    def _get_parameters(self) -> list[dict[str, Any]]:
        parameters = {
            (parameter["in"], parameter["name"]): parameter
            for parameter in super()._get_parameters()
        }
        for parameter in drf_transport_parameters(self.view, self.method):
            parameters[(parameter["in"], parameter["name"])] = parameter
        return sorted(
            parameters.values(),
            key=lambda parameter: (parameter["name"], parameter["in"]),
        )

    def _get_response_bodies(
        self, direction: Literal["request", "response"] = "response"
    ) -> dict[str, Any]:
        return project_drf_responses(
            super()._get_response_bodies(direction),
            self.view,
            self.method,
            consumes_body=(
                self.method in {"POST", "PUT", "PATCH", "DELETE"}
                and self.get_request_serializer() is not None
            ),
        )

    def get_request_serializer(self) -> Any:
        if self.method == "DELETE":
            return None
        return super().get_request_serializer()

    def _get_request_body(self, direction: str = "request") -> dict[str, Any] | None:
        if self.method != "DELETE":
            body = super()._get_request_body(direction)  # type: ignore[no-untyped-call]
            return self._project_request_body(body) if body else None
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
        return self._project_request_body(
            {
                "required": required,
                "content": {media: {"schema": schema} for media in self.map_parsers()},
            }
        )

    def _resolved_schema(self, schema: dict[str, Any]) -> dict[str, Any]:
        if reference := schema.get("$ref"):
            return cast(
                "dict[str, Any]",
                self.registry[(reference.rsplit("/", 1)[1], "schemas")].schema,
            )
        return schema

    def _requires_body(self, schema: dict[str, Any]) -> bool:
        source = self._resolved_schema(schema)
        if source.get("required") or source.get("minItems", 0) > 0:
            return True
        if "allOf" in source:
            return any(self._requires_body(branch) for branch in source["allOf"])
        for composition in ("anyOf", "oneOf"):
            if composition in source:
                return bool(source[composition]) and all(
                    self._requires_body(branch) for branch in source[composition]
                )
        return False

    def _project_request_body(self, body: dict[str, Any]) -> dict[str, Any]:
        result = copy.deepcopy(body)
        result["content"] = {}
        for media_type, media in body["content"].items():
            schema = self._request_media_schema(media["schema"], media_type)
            if schema is not None:
                result["content"][media_type] = {**media, "schema": schema}
        if not result["content"]:
            raise ValueError(
                f"No representable request media for {self.method} {self.path}"
            )
        result["required"] = all(
            self._requires_body(media["schema"]) for media in result["content"].values()
        )
        return result

    def _request_media_schema(
        self, schema: dict[str, Any], media_type: str
    ) -> dict[str, Any] | None:
        """Describe DRF HTML form JSON encoding and actual file transport.

        JSONField.get_value marks HTML form values as JSON strings. FileField
        requires an UploadedFile, which only the multipart parser can supply.
        Optional file fields remain absent in JSON/urlencoded representations.
        """
        source = self._resolved_schema(schema)
        form = media_type in {
            "multipart/form-data",
            "application/x-www-form-urlencoded",
        }
        if form and source.get("x-drf-form-unrepresentable"):
            return None
        for composition in ("anyOf", "oneOf", "allOf"):
            if composition in source:
                branches = [
                    self._request_media_schema(branch, media_type)
                    for branch in source[composition]
                ]
                if not any(branch is not None for branch in branches) or (
                    composition == "allOf"
                    and any(branch is None for branch in branches)
                ):
                    return None
                return {
                    **source,
                    composition: [branch for branch in branches if branch is not None],
                }
        properties = source.get("properties")
        if not properties:
            return schema
        result = copy.deepcopy(source)
        for name, original_field in list(result["properties"].items()):
            field = original_field
            json_form = field.pop("x-drf-json-form", False)
            unavailable_in_form = field.pop("x-drf-form-unrepresentable", False)
            null_as_empty = field.pop("x-drf-null-as-empty", None)
            if form and unavailable_in_form:
                if name in result.get("required", []):
                    return None
                del result["properties"][name]
                result["required"] = [
                    key for key in result.get("required", []) if key != name
                ]
                continue
            if form and json_form:
                result["properties"][name] = {
                    "type": "string",
                    "description": (
                        field.get("description", "") + "\nJSON-encoded value."
                    ).strip(),
                    "x-json-schema": field,
                }
                continue
            if any(keyword in field for keyword in ("anyOf", "oneOf", "allOf")):
                projected = self._request_media_schema(field, media_type)
                if projected is None:
                    if name in result.get("required", []):
                        return None
                    del result["properties"][name]
                    continue
                field = result["properties"][name] = projected
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
                    if name in result.get("required", []):
                        return None
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
