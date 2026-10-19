"""Validate rendered HTTP responses against the exported API contract."""

from __future__ import annotations

import json
import os
import re
from functools import cache
from hashlib import sha256
from http import HTTPStatus
from typing import TYPE_CHECKING
from typing import Any

import yaml
from django.conf import settings
from django.http import HttpRequest
from django.urls import Resolver404
from django.urls import resolve
from openapi_core import Config
from openapi_core import OpenAPI
from openapi_core.contrib.django import DjangoOpenAPIRequest
from openapi_core.contrib.django import DjangoOpenAPIResponse
from openapi_core.validation.request.validators import V30RequestBodyValidator
from openapi_core.validation.request.validators import V30RequestParametersValidator
from openapi_core.validation.response.validators import V30ResponseValidator

if TYPE_CHECKING:
    from collections.abc import Mapping

    from django.http import HttpResponseBase
    from jsonschema_path import SchemaPath


CONTRACT_METADATA: dict[str, Any] = {"format_version": 2}


class ContractResponseValidator(V30ResponseValidator):
    """Validate empty wire payloads according to their declared media/schema.

    An empty Git result or allauth's empty HTML error is a real representation.
    Keep the normal media deserializer and schema validation: empty JSON still
    fails parsing and nonempty-string constraints still reject an empty body.
    """

    def _get_data_value(self, data: bytes | None) -> bytes:
        if data is None:
            return super()._get_data_value(data)
        return data


class ContractRequestParametersValidator(V30RequestParametersValidator):
    """Honor explicitly allowed empty query values before numeric/CSV casting.

    openapi-core casts empty numeric and array inputs before honoring
    allowEmptyValue. OGC deliberately treats those empty values as omission.
    Every nonempty value, header, and undeclared empty value uses its normal
    deserializer and constraints.
    """

    def _get_param_or_header_and_schema(
        self,
        param_or_header: SchemaPath,
        location: Mapping[str, Any],
        name: str | None = None,
    ) -> tuple[Any, SchemaPath | None]:
        parameter_name = name or (param_or_header / "name").read_str("")
        if (
            parameter_name is not None
            and (param_or_header / "in").read_str("") == "query"
            and (param_or_header / "allowEmptyValue").read_bool(default=False)
            and location.get(parameter_name) == ""
        ):
            return "", None
        return super()._get_param_or_header_and_schema(
            param_or_header, location, name=name
        )


@cache
def contract_schema() -> dict[str, Any]:
    # Capture the artifact at schema initialization, not session finish: a
    # developer may refine source/export while an independent suite is running.
    exported = (settings.BASE_DIR / "OpenAPI.yaml").read_bytes()
    document = yaml.safe_load(exported)
    if not isinstance(document, dict):
        raise TypeError("The canonical OpenAPI snapshot must be an object")
    CONTRACT_METADATA["schema_sha256"] = sha256(exported).hexdigest()
    return document


@cache
def api_contract() -> OpenAPI:
    return OpenAPI.from_dict(
        contract_schema(),
        config=Config(
            response_validator_cls=ContractResponseValidator,
            extra_media_type_deserializers={
                **dict.fromkeys(
                    (
                        "application/geo+json",
                        "application/geojson",
                        "application/vnd.oai.openapi+json",
                    ),
                    deserialize_json,
                ),
                **dict.fromkeys(
                    ("application/yaml", "application/vnd.oai.openapi"),
                    deserialize_text,
                ),
            },
        ),
    )


def deserialize_json(value: bytes, **parameters: str) -> Any:
    """JSON media parameters such as version/charset do not alter JSON syntax."""
    return json.loads(value)


def deserialize_text(value: bytes, **parameters: str) -> str:
    """The schema endpoint's YAML representations are UTF-8 text."""
    return value.decode(parameters.get("charset", "utf-8"))


def resolver_path_pattern(route: str) -> str:
    """Replace converters without swallowing literal suffixes such as .git."""
    return "/" + re.sub(r"<(?:[^:>]+:)?([^>]+)>", r"{\1}", route).removeprefix(
        "^"
    ).removesuffix("$")


class CanonicalAPIRequest(DjangoOpenAPIRequest):
    """Preserve the mounted URL and the original textual path parameter values."""

    def __init__(self, request: HttpRequest) -> None:
        super().__init__(request)
        # Django converters return UUID/int objects; OpenAPI validates the
        # original string values transmitted in the URL.
        self.parameters.path = {
            key: str(value) for key, value in self.parameters.path.items()
        }

    @property
    def path_pattern(self) -> str | None:
        if self.request.resolver_match is None:
            return None
        return resolver_path_pattern(self.request.resolver_match.route)


def assert_api_response(response: HttpResponseBase) -> None:
    """Validate the actual request URL/status/headers and rendered response bytes."""
    request = getattr(response, "wsgi_request", None)
    if not isinstance(request, HttpRequest):
        raise TypeError("Contract assertions require an actual Django test response")
    api_contract().validate_response(
        CanonicalAPIRequest(request),
        # The upstream stub omits supported streaming/test response subclasses.
        DjangoOpenAPIResponse(response),  # type: ignore[arg-type]
    )


CONTRACT_OBSERVATIONS: list[dict[str, Any]] = []


def is_successful_observation(observation: dict[str, Any]) -> bool:
    """An HTTP 200 Git packet-line rejection is not successful API evidence."""
    return HTTPStatus.OK <= observation[
        "status"
    ] < HTTPStatus.BAD_REQUEST and not observation.get("protocol_error", False)


@cache
def request_validators() -> tuple[
    V30RequestParametersValidator, V30RequestBodyValidator
]:
    """Validate input shape separately from real middleware authentication."""
    schema = api_contract().spec
    return ContractRequestParametersValidator(schema), V30RequestBodyValidator(schema)


def request_property_names(schema: dict[str, Any]) -> set[str] | None:
    """Collect named inputs for diagnostics without restricting DRF's ignored keys."""
    if "$ref" in schema:
        return request_property_names(
            contract_schema()["components"]["schemas"][schema["$ref"].rsplit("/", 1)[1]]
        )
    if schema.get("additionalProperties"):
        return None
    for composition in ("anyOf", "oneOf", "allOf"):
        if composition in schema:
            branches = [
                request_property_names(branch) for branch in schema[composition]
            ]
            return set().union(*(branch for branch in branches if branch is not None))
    return set(schema["properties"]) if "properties" in schema else None


class APIContractMiddleware:
    """Opt-in test observer; records real responses without replacing transport."""

    def __init__(self, get_response: Any) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> Any:
        try:
            match = resolve(request.path_info)
        except Resolver404:
            return self.get_response(request)
        pattern = resolver_path_pattern(match.route)
        operation = (
            contract_schema()["paths"]
            .get(pattern, {})
            .get((request.method or "").lower())
        )
        if operation is None:
            return self.get_response(request)
        # Django caches this read and preserves the stream for DRF. Do not read
        # multipart uploads into memory or interfere with upload size limits.
        body_available = request.content_type in {
            "application/json",
            "application/x-www-form-urlencoded",
            "",
        } and int(request.headers.get("content-length") or 0) <= (
            settings.DATA_UPLOAD_MAX_MEMORY_SIZE or 2_621_440
        )
        if body_available:
            _ = request.body
        response = self.get_response(request)
        wrapped_request = CanonicalAPIRequest(request)
        wrapped_response = DjangoOpenAPIResponse(response)
        observation: dict[str, Any] = {
            "operation_id": operation["operationId"],
            "method": wrapped_request.method,
            "path": pattern,
            "status": response.status_code,
            "media_type": response.headers.get("Content-Type", "").split(";", 1)[0],
            "alias": request.path.startswith("/api/auth/"),
            "test": os.environ.get("PYTEST_CURRENT_TEST", ""),
        }
        try:
            if pattern.startswith("/git/") and response.status_code == HTTPStatus.OK:
                observation["protocol_error"] = bool(
                    re.match(rb"^[0-9a-f]{4,}\x02SpeleoDB: ", wrapped_response.data)
                )
            completed_auth_transition = (
                response.status_code == HTTPStatus.UNAUTHORIZED
                and operation["operationId"].startswith("auth_")
                and "test_configured_account_lifecycle" in observation["test"]
            )
            if (
                is_successful_observation(observation)
                and response.status_code < HTTPStatus.MULTIPLE_CHOICES
            ) or completed_auth_transition:
                parameter_validator, body_validator = request_validators()
                parameter_validator.validate(wrapped_request)
                observation["request_parameters_validated"] = True
                body_required = operation.get("requestBody", {}).get("required", False)
                if body_available and (wrapped_request.body or body_required):
                    body_validator.validate(wrapped_request)
                    observation["request_body_validated"] = True
                    media = (
                        operation.get("requestBody", {})
                        .get("content", {})
                        .get(request.content_type, {})
                    )
                    names = request_property_names(media.get("schema", {}))
                    if names is not None and request.content_type == "application/json":
                        payload = json.loads(request.body)
                        if isinstance(payload, dict):
                            observation["undocumented_request_fields"] = sorted(
                                payload.keys() - names
                            )
            api_contract().validate_response(wrapped_request, wrapped_response)
        except Exception as error:  # noqa: BLE001 - Collect violations across the suite.
            messages: list[str] = []
            current: BaseException | None = error
            while current is not None:
                messages.append(f"{type(current).__name__}: {current}")
                current = current.__cause__
            observation["error"] = "\n".join(messages)
        CONTRACT_OBSERVATIONS.append(observation)
        return response
