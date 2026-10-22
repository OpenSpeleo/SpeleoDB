# -*- coding: utf-8 -*-

from __future__ import annotations

from collections import Counter
from io import StringIO
from typing import TYPE_CHECKING
from typing import Any

import pytest
from django.core.management import call_command
from django.urls import reverse
from rest_framework import status

from speleodb.api.schema import SpeleoDBSchemaGenerator

if TYPE_CHECKING:
    from django.test.client import Client


def test_swagger_accessible_by_admin(admin_client: Client) -> None:
    url = reverse("api-docs")
    response = admin_client.get(url)
    assert response.status_code == status.HTTP_200_OK, response.data  # type: ignore[attr-defined]


@pytest.mark.django_db
def test_swagger_ui_accessible_by_unauthenticated_user(client: Client) -> None:
    url = reverse("api-docs")
    response = client.get(url)
    assert response.status_code == status.HTTP_200_OK, response.data  # type: ignore[attr-defined]


def test_api_schema_generated_successfully(admin_client: Client) -> None:
    url = reverse("api-schema")
    response = admin_client.get(url)
    assert response.status_code == status.HTTP_200_OK, response.data  # type: ignore[attr-defined]


@pytest.mark.django_db
def test_api_schema_no_warnings() -> None:
    """Schema generation must produce zero warnings.

    Uses drf-spectacular's ``spectacular`` management command with
    ``--fail-on-warn`` so any unresolvable view, missing serializer_class,
    or unknown field type causes a hard failure.
    """
    stdout = StringIO()
    stderr = StringIO()
    call_command(
        "spectacular",
        "--validate",
        "--fail-on-warn",
        stdout=stdout,
        stderr=stderr,
    )


def _collect_operation_ids(schema: dict[str, Any]) -> list[str]:
    """Walk every operation in the OpenAPI schema and return the list of
    ``operationId`` values (duplicates preserved)."""
    operation_ids: list[str] = []
    for methods in schema.get("paths", {}).values():
        if not isinstance(methods, dict):
            continue
        for method, operation in methods.items():
            if method.lower() not in {
                "get",
                "post",
                "put",
                "patch",
                "delete",
                "head",
                "options",
                "trace",
            }:
                continue
            if isinstance(operation, dict) and "operationId" in operation:
                operation_ids.append(operation["operationId"])
    return operation_ids


@pytest.mark.django_db
def test_schema_exports_only_supported_paths_and_unique_operation_ids() -> None:
    """Canonical, auth aliases and protocol APIs have distinct identities."""
    generator = SpeleoDBSchemaGenerator()
    schema = generator.get_schema(request=None, public=True)

    operation_ids = _collect_operation_ids(schema)
    duplicates = [
        (op_id, count) for op_id, count in Counter(operation_ids).items() if count > 1
    ]
    assert duplicates == [], (
        f"duplicate operationIds found in generated schema: {duplicates}"
    )

    assert operation_ids.count("v2_projects_list") == 1
    assert not any(identifier.startswith("v1_") for identifier in operation_ids)
    assert not any(path.startswith("/api/v1/") for path in schema["paths"])
    assert any(path.startswith("/_allauth/app/v1/") for path in schema["paths"])
    assert any(path.startswith("/api/auth/app/v1/") for path in schema["paths"])
