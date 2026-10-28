"""The Stalagmight software choice uses the normal project API contract."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
from django.urls import reverse
from parameterized.parameterized import parameterized
from rest_framework import status

from speleodb.api.v2.tests.base_testcase import BaseAPITestCase
from speleodb.api.v2.tests.factories import ProjectFactory
from speleodb.api.v2.tests.factories import UserProjectPermissionFactory
from speleodb.api.v2.views.file import request_uploaded_geojson
from speleodb.common.enums import PermissionLevel
from speleodb.common.enums import ProjectType
from speleodb.surveys.models import Project
from speleodb.testing.api_contract import assert_api_response
from speleodb.testing.api_contract import contract_schema

UNSUPPORTED_PROJECT_TYPES = (
    ProjectType.STALAGMIGHT,
    ProjectType.STICKMAPS,
    ProjectType.THERION,
    ProjectType.WALLS,
    ProjectType.OTHER,
)


class TestStalagmightProjectAPI(BaseAPITestCase):
    def test_invalid_software_choice_does_not_create_project(self) -> None:
        response = self.client.post(
            reverse("api:v2:projects"),
            data={
                "name": "Invalid software survey",
                "description": "A near-miss is not a valid software choice",
                "country": "US",
                "type": "stalagmights",
            },
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.data
        assert "type" in response.data["errors"]
        assert not Project.objects.filter(name="Invalid software survey").exists()
        assert_api_response(response)

    @parameterized.expand(["stalagmight", "STALAGMIGHT", "Stalagmight"])
    def test_create_normalizes_choice_and_serializes_read_responses(
        self, project_type: str
    ) -> None:
        response = self.client.post(
            reverse("api:v2:projects"),
            data={
                "name": "Stalagmight survey",
                "description": "Native survey source history",
                "country": "US",
                "type": project_type,
            },
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_201_CREATED, response.data
        assert_api_response(response)
        project = Project.objects.get(pk=response.data["id"])
        assert project.type == ProjectType.STALAGMIGHT
        assert response.data["type"] == "STALAGMIGHT"
        detail = self.client.get(
            reverse("api:v2:project-detail", kwargs={"id": project.pk}),
            headers={"authorization": self.auth},
        )
        assert detail.status_code == status.HTTP_200_OK, detail.data
        assert detail.data["type"] == "STALAGMIGHT"
        assert_api_response(detail)
        listing = self.client.get(
            reverse("api:v2:projects"), headers={"authorization": self.auth}
        )
        assert listing.status_code == status.HTTP_200_OK, listing.data
        assert [item["type"] for item in listing.data] == ["STALAGMIGHT"]
        assert_api_response(listing)

    @parameterized.expand(["put", "patch"])
    def test_update_existing_project_to_stalagmight(self, method: str) -> None:
        project = ProjectFactory.create(
            created_by=self.user.email, type=ProjectType.ARIANE
        )
        UserProjectPermissionFactory.create(
            target=self.user, project=project, level=PermissionLevel.ADMIN
        )
        data: dict[str, str] = {"type": "Stalagmight"}
        if method == "put":
            data.update(
                name=project.name, description=project.description, country="US"
            )
        response = getattr(self.client, method)(
            reverse("api:v2:project-detail", kwargs={"id": project.pk}),
            data=data,
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_200_OK, response.data
        assert_api_response(response)
        project.refresh_from_db()
        assert project.type == ProjectType.STALAGMIGHT
        assert response.data["type"] == "STALAGMIGHT"

    @parameterized.expand(["put", "patch"])
    def test_read_only_permission_cannot_change_project_type(self, method: str) -> None:
        project = ProjectFactory.create(
            created_by=self.user.email, type=ProjectType.COMPASS
        )
        UserProjectPermissionFactory.create(
            target=self.user, project=project, level=PermissionLevel.READ_ONLY
        )
        response = getattr(self.client, method)(
            reverse("api:v2:project-detail", kwargs={"id": project.pk}),
            data={"type": "STALAGMIGHT"},
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN, response.data
        project.refresh_from_db()
        assert project.type == ProjectType.COMPASS

    def test_invalid_software_update_preserves_project_type(self) -> None:
        project = ProjectFactory.create(
            created_by=self.user.email, type=ProjectType.STALAGMIGHT
        )
        UserProjectPermissionFactory.create(
            target=self.user, project=project, level=PermissionLevel.ADMIN
        )
        response = self.client.patch(
            reverse("api:v2:project-detail", kwargs={"id": project.pk}),
            data={"type": "stalagmights"},
            format="json",
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.data
        assert "type" in response.data["errors"]
        project.refresh_from_db()
        assert project.type == ProjectType.STALAGMIGHT
        assert_api_response(response)


@pytest.mark.parametrize("project_type", UNSUPPORTED_PROJECT_TYPES)
def test_unsupported_software_uses_existing_upload_behavior(
    project_type: ProjectType,
) -> None:
    project = Project(type=project_type, exclude_geojson=False)

    assert request_uploaded_geojson(project, "a" * 40, [Path("project.tml")]) == (
        "not_requested"
    )
    assert project.exclude_geojson is False


@pytest.mark.parametrize("project_type", UNSUPPORTED_PROJECT_TYPES)
def test_operator_exclusion_remains_independent_of_software(
    project_type: ProjectType,
) -> None:
    project = Project(type=project_type, exclude_geojson=True)

    assert request_uploaded_geojson(project, "a" * 40, [Path("project.tml")]) == (
        "skipped"
    )
    assert project.exclude_geojson is True


def test_project_choice_schema_includes_stalagmight() -> None:
    document: dict[str, Any] = contract_schema()
    for path, method in (
        ("/api/v2/projects/", "post"),
        ("/api/v2/projects/{id}/", "put"),
        ("/api/v2/projects/{id}/", "patch"),
    ):
        content = document["paths"][path][method]["requestBody"]["content"]
        for media in content.values():
            choice = media["schema"]["properties"]["type"]
            assert "STALAGMIGHT" in choice["description"]
            for value in ("stalagmight", "STALAGMIGHT", "Stalagmight"):
                assert re.fullmatch(choice["pattern"], value)
            assert re.fullmatch(choice["pattern"], "stalagmights") is None
    for name in ("Project", "ProjectWithGeoJson"):
        choice = document["components"]["schemas"][name]["properties"]["type"]
        assert "STALAGMIGHT" in choice["enum"]
