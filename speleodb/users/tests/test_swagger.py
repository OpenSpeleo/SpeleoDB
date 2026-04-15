# -*- coding: utf-8 -*-

from __future__ import annotations

from io import StringIO
from typing import TYPE_CHECKING

import pytest
from django.core.management import call_command
from django.urls import reverse
from rest_framework import status

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
