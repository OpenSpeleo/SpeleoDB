"""Regressions for real wire observation and empty media validation."""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

import pytest
from django.conf import settings
from django.http import HttpResponse
from django.http import StreamingHttpResponse
from django.test import Client
from django.test import RequestFactory
from django.test import override_settings
from openapi_core import Config
from openapi_core import OpenAPI
from openapi_core.contrib.django import DjangoOpenAPIRequest
from openapi_core.contrib.django import DjangoOpenAPIResponse
from openapi_core.validation.request.exceptions import ParameterValidationError
from openapi_core.validation.response.exceptions import DataValidationError
from rest_framework import status

from speleodb.testing.api_contract import CONTRACT_OBSERVATIONS
from speleodb.testing.api_contract import ContractRequestParametersValidator
from speleodb.testing.api_contract import ContractResponseValidator
from speleodb.testing.api_contract import contract_schema
from speleodb.testing.api_contract import is_successful_observation

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture
def observed_client() -> Generator[Client]:
    observer = "speleodb.testing.api_contract.APIContractMiddleware"
    middleware = list(settings.MIDDLEWARE)
    if observer in middleware:
        # Audit invocations exercise the session fixture's actual ordering.
        assert middleware[0] == observer
        assert middleware.count(observer) == 1
    else:
        middleware.insert(0, observer)
    with override_settings(MIDDLEWARE=middleware, ACCOUNT_RATE_LIMITS={}):
        yield Client(enforce_csrf_checks=True)


@pytest.mark.django_db
def test_observer_keeps_authentication_mounts_distinct(observed_client: Client) -> None:
    paths = ["/_allauth/browser/v1/config", "/api/auth/browser/v1/config"]
    start = len(CONTRACT_OBSERVATIONS)
    for path in paths:
        response = observed_client.get(path)
        assert response.status_code == status.HTTP_200_OK
    observations = CONTRACT_OBSERVATIONS[start:]
    assert [item["path"] for item in observations] == paths
    assert [item["alias"] for item in observations] == [False, True]
    identifiers = [item["operation_id"] for item in observations]
    assert identifiers == [
        contract_schema()["paths"][path]["get"]["operationId"] for path in paths
    ]
    assert len(set(identifiers)) == len(paths)
    assert all("error" not in item for item in observations)
    assert all(item["request_parameters_validated"] for item in observations)


@pytest.mark.django_db
@pytest.mark.parametrize("mount", ["/_allauth/", "/api/auth/"])
def test_observer_sees_browser_csrf_rejection(
    observed_client: Client, mount: str
) -> None:
    path = f"{mount}browser/v1/auth/login"
    start = len(CONTRACT_OBSERVATIONS)
    # Malformed JSON would reach allauth's 400 parser branch if CSRF did not
    # reject this request first. No CSRF cookie or token has been obtained.
    response = observed_client.post(path, data="{", content_type="application/json")
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response["Content-Type"].startswith("text/html")
    observations = CONTRACT_OBSERVATIONS[start:]
    assert len(observations) == 1
    observation = observations[0]
    assert observation["path"] == path
    assert observation["status"] == response.status_code
    assert observation["media_type"] == "text/html"
    assert "error" not in observation


@pytest.mark.django_db
def test_observer_validates_real_empty_html_error(observed_client: Client) -> None:
    path = "/_allauth/app/v1/auth/login"
    start = len(CONTRACT_OBSERVATIONS)
    response = observed_client.post(path, data="{", content_type="application/json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.content == b""
    assert response["Content-Type"].startswith("text/html")
    observations = CONTRACT_OBSERVATIONS[start:]
    assert len(observations) == 1
    assert observations[0]["path"] == path
    assert observations[0]["status"] == response.status_code
    assert "error" not in observations[0]


@pytest.mark.django_db
def test_observer_includes_discovery_outside_api_prefix(
    observed_client: Client,
) -> None:
    path = "/.well-known/passkey-endpoints"
    start = len(CONTRACT_OBSERVATIONS)
    response = observed_client.get(path)
    assert response.status_code == status.HTTP_200_OK
    observations = CONTRACT_OBSERVATIONS[start:]
    assert len(observations) == 1
    assert observations[0]["path"] == path
    assert "error" not in observations[0]


@pytest.mark.django_db
@pytest.mark.parametrize("service", ["git-upload-pack", "git-receive-pack"])
def test_git_packet_rejection_is_observed_without_success_credit(
    observed_client: Client, service: str
) -> None:
    missing_project = "00000000-0000-4000-8000-000000000099"
    path = f"/git/{missing_project}.git/{service}"
    start = len(CONTRACT_OBSERVATIONS)
    response = observed_client.post(
        path, data=b"0000", content_type=f"application/x-{service}-request"
    )
    assert response.status_code == status.HTTP_200_OK
    assert isinstance(response, StreamingHttpResponse)
    # Reading the observer must preserve the stream that the real client sees.
    assert b"\x02SpeleoDB: " in b"".join(response.streaming_content)
    observations = CONTRACT_OBSERVATIONS[start:]
    assert len(observations) == 1
    observation = observations[0]
    assert observation["path"] == f"/git/{{id}}.git/{service}"
    assert observation["protocol_error"] is True
    assert not is_successful_observation(observation)
    assert not observation.get("request_parameters_validated", False)
    assert "error" not in observation


@pytest.mark.parametrize(
    ("media_type", "schema", "body", "valid"),
    [
        ("text/plain", {"type": "string"}, b"", True),
        ("text/html", {"type": "string", "maxLength": 0}, b"", True),
        ("application/octet-stream", {"type": "string", "format": "binary"}, b"", True),
        ("application/json", {"type": "object"}, b"", False),
        ("application/json", {"type": "string", "minLength": 0}, b"", False),
        ("application/json", {"type": "string", "minLength": 0}, b'""', True),
        ("text/plain", {"type": "string", "minLength": 1}, b"", False),
    ],
)
def test_empty_payload_retains_media_and_schema_validation(
    media_type: str, schema: dict[str, Any], body: bytes, valid: bool
) -> None:
    # Real framework requests/responses and the public OpenAPI validator avoid
    # mutating the active observer's cached canonical contract or evidence.
    document = {
        "openapi": "3.0.3",
        "info": {"title": "Empty payload regression", "version": "1"},
        "paths": {
            "/payload": {
                "get": {
                    "responses": {
                        "200": {
                            "description": "Payload",
                            "content": {media_type: {"schema": schema}},
                        }
                    }
                }
            }
        },
    }
    validator = OpenAPI.from_dict(
        document, config=Config(response_validator_cls=ContractResponseValidator)
    )
    request = DjangoOpenAPIRequest(RequestFactory().get("/payload"))
    response = DjangoOpenAPIResponse(HttpResponse(body, content_type=media_type))
    if valid:
        validator.validate_response(request, response)
    else:
        with pytest.raises(DataValidationError):
            validator.validate_response(request, response)


@pytest.mark.parametrize(
    ("array", "allow_empty", "value", "valid"),
    [
        (False, True, "", True),
        (False, False, "", False),
        (False, None, "", False),
        (False, True, None, False),
        (False, True, " ", False),
        (False, True, "1", True),
        (False, True, "-1", False),
        (False, True, "3", False),
        (True, True, "", True),
        (True, False, "", False),
        (True, True, "1,2,3", False),
        (True, True, "1,2,3,4", True),
    ],
)
def test_empty_query_exception_preserves_normal_parameter_constraints(
    *, array: bool, allow_empty: bool | None, value: str | None, valid: bool
) -> None:
    parameter: dict[str, Any] = {
        "name": "value",
        "in": "query",
        "required": True,
        "schema": (
            {"type": "array", "items": {"type": "number"}, "minItems": 4, "maxItems": 4}
            if array
            else {"type": "integer", "minimum": 0, "maximum": 2}
        ),
    }
    if array:
        parameter.update(style="form", explode=False)
    if allow_empty is not None:
        parameter["allowEmptyValue"] = allow_empty
    document = {
        "openapi": "3.0.3",
        "info": {"title": "Empty query regression", "version": "1"},
        "paths": {
            "/parameter": {
                "get": {
                    "parameters": [parameter],
                    "responses": {"200": {"description": "Result"}},
                }
            }
        },
    }
    contract = OpenAPI.from_dict(document)
    validator = ContractRequestParametersValidator(contract.spec)
    request = DjangoOpenAPIRequest(
        RequestFactory().get("/parameter", {} if value is None else {"value": value})
    )
    if valid:
        validator.validate(request)
    else:
        with pytest.raises(ParameterValidationError):
            validator.validate(request)
