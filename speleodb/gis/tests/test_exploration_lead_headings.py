"""Lead directions survive writes and reject values the map cannot render."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from typing import Any
from urllib.parse import urlencode

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.response import Response
from rest_framework.test import APIClient

from speleodb.api.v2.serializers.exploration_lead import ExplorationLeadSerializer
from speleodb.api.v2.tests.factories import ExplorationLeadFactory
from speleodb.api.v2.tests.factories import UserProjectPermissionFactory
from speleodb.common.enums import PermissionLevel

if TYPE_CHECKING:
    from speleodb.gis.models import ExplorationLead
    from speleodb.surveys.models import Project
    from speleodb.users.models import User


def test_headings_are_preserved_in_lead_write() -> None:
    serializer = ExplorationLeadSerializer(
        data={"latitude": 20, "longitude": -87, "headings": [0, 22.5, 359.9]}
    )
    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data["headings"] == [0, 22.5, 359.9]


@pytest.mark.parametrize(
    "headings",
    [[-1], [360], [float("nan")], [float("inf")], [None], [True], [0, 1, 2, 3], None],
)
def test_invalid_headings_rejected(headings: Any) -> None:
    serializer = ExplorationLeadSerializer(data={"headings": headings}, partial=True)
    assert not serializer.is_valid()
    assert "headings" in serializer.errors


def test_heading_reset_and_omission_have_different_meanings() -> None:
    reset = ExplorationLeadSerializer(data={"headings": []}, partial=True)
    assert reset.is_valid(), reset.errors
    assert reset.validated_data["headings"] == []
    omitted = ExplorationLeadSerializer(data={"description": "Edited"}, partial=True)
    assert omitted.is_valid(), omitted.errors
    assert "headings" not in omitted.validated_data


@pytest.fixture
def lead_client(project: Project, user: User) -> tuple[APIClient, ExplorationLead]:
    UserProjectPermissionFactory.create(
        project=project, target=user, level=PermissionLevel.READ_AND_WRITE
    )
    token, _ = Token.objects.get_or_create(user=user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    lead = ExplorationLeadFactory.create(
        project=project,
        description="Native comment with <unusual> notation !E!",
        headings=[90],
        longitude=-87,
        latitude=20,
    )
    return client, lead


def patch_lead(
    client: APIClient, lead: ExplorationLead, data: dict[str, Any], encoding: str
) -> Response:
    url = reverse("api:v2:exploration-lead-detail", kwargs={"id": lead.pk})
    body = data.copy()
    if encoding != "json" and "headings" in body:
        body["headings"] = json.dumps(body["headings"])
    if encoding == "urlencoded":
        response = client.patch(
            url, data=urlencode(body), content_type="application/x-www-form-urlencoded"
        )
    else:
        response = client.patch(url, data=body, format=encoding)
    assert isinstance(response, Response)
    return response


@pytest.mark.django_db
@pytest.mark.parametrize("encoding", ["json", "multipart", "urlencoded"])
def test_heading_reset_and_omission_persist_through_each_request_encoding(
    lead_client: tuple[APIClient, ExplorationLead], encoding: str
) -> None:
    client, lead = lead_client
    description = lead.description
    response = patch_lead(client, lead, {"longitude": -87}, encoding)
    assert response.status_code == status.HTTP_200_OK, response.data
    lead.refresh_from_db()
    assert lead.headings == [90]

    response = patch_lead(client, lead, {"headings": []}, encoding)
    assert response.status_code == status.HTTP_200_OK, response.data
    lead.refresh_from_db()
    assert lead.headings == response.data["headings"] == []
    assert lead.description == description

    # Retain FloatField's accepted numeric-string coercion in every transport.
    response = patch_lead(client, lead, {"headings": ["22.5", 270]}, encoding)
    assert response.status_code == status.HTTP_200_OK, response.data
    lead.refresh_from_db()
    assert lead.headings == response.data["headings"] == [22.5, 270]
    assert lead.description == description
    geojson = client.get(
        reverse(
            "api:v2:project-exploration-leads-geojson", kwargs={"id": lead.project_id}
        )
    )
    assert geojson.status_code == status.HTTP_200_OK
    assert geojson.json()["features"][0]["properties"]["headings"] == [22.5, 270]


@pytest.mark.django_db
@pytest.mark.parametrize("encoding", ["json", "multipart", "urlencoded"])
@pytest.mark.parametrize("headings", [{"north": 0}, [True], ["NaN"], [0, 90, 180, 270]])
def test_invalid_heading_writes_preserve_existing_data(
    lead_client: tuple[APIClient, ExplorationLead], encoding: str, headings: Any
) -> None:
    client, lead = lead_client
    description, modified = lead.description, lead.modified_date
    response = patch_lead(client, lead, {"headings": headings}, encoding)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "headings" in response.data["errors"]
    lead.refresh_from_db()
    assert lead.headings == [90]
    assert lead.description == description
    assert lead.modified_date == modified
