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
    from speleodb.gis.models.explo_lead import ExplorationLeadDirection
    from speleodb.surveys.models import Project
    from speleodb.users.models import User


def test_directions_and_checked_states_are_preserved_in_lead_write() -> None:
    directions: list[ExplorationLeadDirection] = [
        {"heading": 0, "checked": False},
        {"heading": 22.5, "checked": True},
        {"heading": None, "checked": False},
    ]
    serializer = ExplorationLeadSerializer(
        data={"latitude": 20, "longitude": -87, "directions": directions}
    )
    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data["directions"] == directions


@pytest.mark.parametrize(
    "directions",
    [
        [],
        None,
        {},
        [0],
        [{"heading": -1, "checked": False}],
        [{"heading": 360, "checked": False}],
        [{"heading": float("nan"), "checked": False}],
        [{"heading": float("inf"), "checked": False}],
        [{"heading": True, "checked": False}],
        [{"heading": 0, "checked": "false"}],
        [{"heading": 0, "checked": 1}],
        [{"heading": 0, "checked": None}],
        [{"heading": 0}],
        [{"checked": False}],
        [{"heading": 0, "checked": False}] * 4,
    ],
)
def test_invalid_directions_rejected(directions: Any) -> None:
    serializer = ExplorationLeadSerializer(
        data={"directions": directions}, partial=True
    )
    assert not serializer.is_valid()
    assert "directions" in serializer.errors


def test_undirected_reset_and_omission_have_different_meanings() -> None:
    directions: list[ExplorationLeadDirection] = [{"heading": None, "checked": True}]
    reset = ExplorationLeadSerializer(data={"directions": directions}, partial=True)
    assert reset.is_valid(), reset.errors
    assert reset.validated_data["directions"] == directions
    omitted = ExplorationLeadSerializer(data={"description": "Edited"}, partial=True)
    assert omitted.is_valid(), omitted.errors
    assert "directions" not in omitted.validated_data


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
        directions=[{"heading": 90, "checked": True}],
        longitude=-87,
        latitude=20,
    )
    return client, lead


def patch_lead(
    client: APIClient, lead: ExplorationLead, data: dict[str, Any], encoding: str
) -> Response:
    url = reverse("api:v2:exploration-lead-detail", kwargs={"id": lead.pk})
    body = data.copy()
    if encoding != "json" and "directions" in body:
        body["directions"] = json.dumps(body["directions"])
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
def test_checked_directions_persist_through_each_request_encoding(
    lead_client: tuple[APIClient, ExplorationLead], encoding: str
) -> None:
    client, lead = lead_client
    description = lead.description
    response = patch_lead(client, lead, {"longitude": -87}, encoding)
    assert response.status_code == status.HTTP_200_OK, response.data
    lead.refresh_from_db()
    assert lead.directions == [{"heading": 90, "checked": True}]
    assert response.data["is_fully_checked"] is True

    # Clearing a bearing preserves the completion state of its undirected lead.
    directions: list[ExplorationLeadDirection] = [{"heading": None, "checked": True}]
    response = patch_lead(client, lead, {"directions": directions}, encoding)
    assert response.status_code == status.HTTP_200_OK, response.data
    lead.refresh_from_db()
    assert lead.directions == response.data["directions"] == directions
    assert lead.description == description
    assert response.data["is_fully_checked"] is True

    # Retain FloatField's accepted numeric-string coercion in every transport.
    response = patch_lead(
        client,
        lead,
        {
            "directions": [
                {"heading": "22.5", "checked": True},
                {"heading": 270, "checked": False},
            ]
        },
        encoding,
    )
    assert response.status_code == status.HTTP_200_OK, response.data
    lead.refresh_from_db()
    directions = [
        {"heading": 22.5, "checked": True},
        {"heading": 270, "checked": False},
    ]
    assert lead.directions == response.data["directions"] == directions
    assert lead.description == description
    assert response.data["is_fully_checked"] is False
    for url in [
        reverse(
            "api:v2:project-exploration-leads-geojson", kwargs={"id": lead.project_id}
        ),
        reverse("api:v2:exploration-lead-all-geojson"),
    ]:
        geojson = client.get(url)
        assert geojson.status_code == status.HTTP_200_OK
        properties = geojson.json()["features"][0]["properties"]
        assert properties["directions"] == directions
        assert properties["is_fully_checked"] is False


@pytest.mark.django_db
@pytest.mark.parametrize("encoding", ["json", "multipart", "urlencoded"])
@pytest.mark.parametrize(
    "directions",
    [
        [],
        [{"heading": 90, "checked": "false"}],
        [{"heading": 0, "checked": False}] * 4,
    ],
)
def test_invalid_direction_writes_preserve_existing_data(
    lead_client: tuple[APIClient, ExplorationLead], encoding: str, directions: Any
) -> None:
    client, lead = lead_client
    saved = {
        field: getattr(lead, field)
        for field in [
            "description",
            "directions",
            "modified_date",
            "latitude",
            "longitude",
        ]
    }
    response = patch_lead(
        client,
        lead,
        {"directions": directions, "description": "Must not save"},
        encoding,
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "directions" in response.data["errors"]
    lead.refresh_from_db()
    assert {field: getattr(lead, field) for field in saved} == saved


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("count", "mask"),
    [(count, mask) for count in range(1, 4) for mask in range(2**count)],
)
def test_individual_and_bulk_checked_states_preserve_every_entry(
    lead_client: tuple[APIClient, ExplorationLead], count: int, mask: int
) -> None:
    client, lead = lead_client
    directions: list[ExplorationLeadDirection] = [
        {"heading": 90, "checked": bool(mask & (1 << index))} for index in range(count)
    ]
    response = patch_lead(
        client, lead, {"directions": directions, "is_fully_checked": False}, "json"
    )
    assert response.status_code == status.HTTP_200_OK, response.data
    lead.refresh_from_db()
    assert lead.directions == directions
    assert lead.is_fully_checked is (mask == 2**count - 1)
    assert response.data["is_fully_checked"] is lead.is_fully_checked

    directions[-1]["heading"] = 337.5
    response = patch_lead(client, lead, {"directions": directions}, "json")
    assert response.status_code == status.HTTP_200_OK, response.data
    lead.refresh_from_db()
    assert lead.directions == directions
    if count > 1:
        response = patch_lead(client, lead, {"directions": directions[1:]}, "json")
        assert response.status_code == status.HTTP_200_OK, response.data
        lead.refresh_from_db()
        assert lead.directions == directions[1:]


@pytest.mark.django_db
def test_checked_undirected_creation_remains_available_to_reads(
    lead_client: tuple[APIClient, ExplorationLead],
) -> None:
    client, existing_lead = lead_client
    response = client.post(
        reverse(
            "api:v2:project-exploration-leads", kwargs={"id": existing_lead.project_id}
        ),
        data={"description": "No bearing recorded", "latitude": 20, "longitude": -87},
        format="json",
    )
    assert response.status_code == status.HTTP_201_CREATED, response.data
    assert response.data["directions"] == [{"heading": None, "checked": False}]
    assert response.data["is_fully_checked"] is False
    lead_id = response.data["id"]
    response = client.patch(
        reverse("api:v2:exploration-lead-detail", kwargs={"id": lead_id}),
        data={"directions": [{"heading": None, "checked": True}]},
        format="json",
    )
    assert response.status_code == status.HTTP_200_OK, response.data
    listed = client.get(
        reverse(
            "api:v2:project-exploration-leads", kwargs={"id": existing_lead.project_id}
        )
    )
    assert listed.status_code == status.HTTP_200_OK
    assert {record["id"] for record in listed.data} == {str(existing_lead.pk), lead_id}
    assert all(record["is_fully_checked"] for record in listed.data)
    for url in [
        reverse(
            "api:v2:project-exploration-leads-geojson",
            kwargs={"id": existing_lead.project_id},
        ),
        reverse("api:v2:exploration-lead-all-geojson"),
    ]:
        geojson = client.get(url)
        assert geojson.status_code == status.HTTP_200_OK
        features = geojson.json()["features"]
        assert {feature["id"] for feature in features} == {
            str(existing_lead.pk),
            lead_id,
        }
        assert all(feature["properties"]["is_fully_checked"] for feature in features)
