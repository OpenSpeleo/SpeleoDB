"""Validate rendered HTTP responses against the exported API contract."""

from __future__ import annotations

import json
import os
from functools import cache
from hashlib import sha256
from http import HTTPStatus
from typing import TYPE_CHECKING
from typing import Any

import yaml
from django.conf import settings
from django.http import HttpRequest
from openapi_core import Config
from openapi_core import OpenAPI
from openapi_core.contrib.django import DjangoOpenAPIRequest
from openapi_core.contrib.django import DjangoOpenAPIResponse
from openapi_core.validation.request.validators import V30RequestBodyValidator
from openapi_core.validation.request.validators import V30RequestParametersValidator

if TYPE_CHECKING:
    from django.http import HttpResponseBase


CONTRACT_METADATA: dict[str, Any] = {"format_version": 2}


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
            extra_media_type_deserializers=dict.fromkeys(
                (
                    "application/geo+json",
                    "application/geojson",
                    "application/vnd.oai.openapi+json",
                ),
                deserialize_json,
            )
        ),
    )


def deserialize_json(value: bytes, **parameters: str) -> Any:
    """JSON media parameters such as version/charset do not alter JSON syntax."""
    return json.loads(value)


class CanonicalAPIRequest(DjangoOpenAPIRequest):
    """The mounted allauth alias has the same configured view as its canonical URL."""

    def __init__(self, request: HttpRequest) -> None:
        super().__init__(request)
        # Django converters return UUID/int objects; OpenAPI validates the
        # original string values transmitted in the URL.
        self.parameters.path = {
            key: str(value) for key, value in self.parameters.path.items()
        }

    @property
    def path(self) -> str:
        return super().path.replace("/api/auth/", "/_allauth/", 1)

    @property
    def path_pattern(self) -> str | None:
        pattern = super().path_pattern
        return pattern.replace("/api/auth/", "/_allauth/", 1) if pattern else None


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


@cache
def request_validators() -> tuple[
    V30RequestParametersValidator, V30RequestBodyValidator
]:
    """Validate input shape separately from real middleware authentication."""
    schema = api_contract().spec
    return V30RequestParametersValidator(schema), V30RequestBodyValidator(schema)


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
        if not request.path.startswith(
            ("/api/v2/", "/api/health/", "/_allauth/", "/api/auth/")
        ):
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
        pattern = wrapped_request.path_pattern
        if pattern is None:
            return response
        document = contract_schema()
        operation = document["paths"].get(pattern, {}).get(wrapped_request.method)
        if operation is None:
            return response
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
            completed_auth_transition = (
                response.status_code == HTTPStatus.UNAUTHORIZED
                and operation["operationId"].startswith("auth_")
                and "test_configured_account_lifecycle" in observation["test"]
            )
            if (
                HTTPStatus.OK <= response.status_code < HTTPStatus.MULTIPLE_CHOICES
                or completed_auth_transition
            ):
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
            api_contract().validate_response(
                wrapped_request, DjangoOpenAPIResponse(response)
            )
        except Exception as error:  # noqa: BLE001 - Collect violations across the suite.
            messages: list[str] = []
            current: BaseException | None = error
            while current is not None:
                messages.append(f"{type(current).__name__}: {current}")
                current = current.__cause__
            observation["error"] = "\n".join(messages)
        CONTRACT_OBSERVATIONS.append(observation)
        return response
