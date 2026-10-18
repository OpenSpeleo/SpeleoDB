"""Resolver coverage and real anonymous wire behavior for every current API."""

from __future__ import annotations

import json
import re
from hashlib import sha256
from typing import TYPE_CHECKING
from typing import Any

import pytest
from django.conf import settings
from django.urls import resolve
from rest_framework import status

from speleodb.api.schema_inventory import current_api_routes
from speleodb.testing.api_contract import assert_api_response
from speleodb.testing.api_contract import contract_schema
from speleodb.testing.api_contract import request_property_names

if TYPE_CHECKING:
    from django.test import Client

ROUTES = current_api_routes()


def concrete_route(route: str) -> str:
    values = {
        "uuid": "00000000-0000-0000-0000-000000000001",
        "int": "1",
        "gitsha": "a" * 40,
        "blobsha": "a" * 40,
        "gis_token": "a" * 40,
        "user_token": "a" * 40,
        "ogc_typed_id": "a" * 40 + "_points",
        "download_format": "dump",
        "upload_format": "auto",
    }
    return re.sub(
        r"<(?:(?P<converter>[^:>]+):)?[^>]+>",
        lambda match: values.get(match["converter"] or "str", "missing"),
        route,
    )


def test_every_current_resolver_operation_is_documented() -> None:
    document = contract_schema()
    expected = {(route["path"], route["method"]) for route in ROUTES}
    actual = {
        (path, method)
        for path, item in document["paths"].items()
        for method in item
        if method in {"get", "post", "put", "patch", "delete"}
    }
    assert expected == actual
    assert all(not path.startswith("/api/v1/") for path in document["paths"])
    identifiers = [
        document["paths"][path][method]["operationId"] for path, method in actual
    ]
    assert len(identifiers) == len(set(identifiers))


def test_durable_evidence_matches_current_contract() -> None:
    registry = json.loads(
        (settings.BASE_DIR / "docs/api-contract-coverage.json").read_text()
    )
    assert (
        registry["schema_sha256"]
        == sha256((settings.BASE_DIR / "OpenAPI.yaml").read_bytes()).hexdigest()
    )
    expected = {
        operation["operationId"]: (path, method.upper())
        for path, item in contract_schema()["paths"].items()
        for method, operation in item.items()
        if method in {"get", "post", "put", "patch", "delete"}
    }
    assert registry["canonical_operations"] == len(expected)
    assert registry["resolver_operations"] == len(ROUTES)
    assert set(registry["operations"]) == set(expected)
    assert registry["source_reports"]
    assert all(source["exit_status"] == 0 for source in registry["source_reports"])
    source_hashes = {source["schema_sha256"] for source in registry["source_reports"]}
    assert registry["schema_sha256"] in source_hashes
    for identifier, (path, method) in expected.items():
        evidence = registry["operations"][identifier]
        assert (evidence["path"], evidence["method"]) == (path, method)
        assert evidence["observed_response_branches"]
        assert evidence["tests"]
        assert set(evidence["observed_schema_sha256"]) <= source_hashes
        assert (
            evidence["successful_response_observed"]
            or evidence["completed_auth_transition_observed"]
            or evidence["configured_unavailable_reason"]
        )


@pytest.mark.parametrize(
    ("path", "method"),
    [
        ("/api/v2/user/gis_views/", "post"),
        ("/api/v2/user/gis_views/{id}/", "put"),
        ("/api/v2/user/gis_views/{id}/", "patch"),
    ],
)
def test_gis_view_inputs_describe_nested_project_writes(path: str, method: str) -> None:
    document = contract_schema()
    content = document["paths"][path][method]["requestBody"]["content"]
    schema = content["application/json"]["schema"]
    assert "projects" in (request_property_names(schema) or set())
    nested = schema["properties"]["projects"]["items"]
    assert request_property_names(nested) == {"project_id", "commit_sha", "use_latest"}
    for media in ("multipart/form-data", "application/x-www-form-urlencoded"):
        if method != "patch":
            assert media not in content
        else:
            assert "projects" not in (
                request_property_names(content[media]["schema"]) or set()
            )


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
    "route", ROUTES, ids=lambda route: route["method"].upper() + " " + route["route"]
)
def test_every_route_anonymous_response_matches_contract(
    client: Client, route: dict[str, Any]
) -> None:
    path = concrete_route(route["route"])
    assert resolve(path).url_name == route["name"]
    response = client.generic(
        route["method"].upper(),
        path,
        data="{}" if route["method"] != "get" else "",
        content_type="application/json",
    )
    assert response.status_code < status.HTTP_500_INTERNAL_SERVER_ERROR
    assert_api_response(response)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "route",
    [route for route in ROUTES if route["path"].startswith("/_allauth/")],
    ids=lambda route: route["method"] + " " + route["path"],
)
def test_allauth_compatibility_alias_uses_same_view_and_response(
    client: Client, route: dict[str, Any]
) -> None:
    canonical = concrete_route(route["route"])
    alias = canonical.replace("/_allauth/", "/api/auth/", 1)
    canonical_view: Any = resolve(canonical).func
    alias_view: Any = resolve(alias).func
    assert canonical_view.view_class is alias_view.view_class
    assert canonical_view.view_initkwargs == alias_view.view_initkwargs
    original = client.generic(
        route["method"].upper(), canonical, data="{}", content_type="application/json"
    )
    mirrored = client.generic(
        route["method"].upper(), alias, data="{}", content_type="application/json"
    )
    assert original.status_code == mirrored.status_code
    assert original.headers.get("Content-Type") == mirrored.headers.get("Content-Type")
    assert_api_response(mirrored)
