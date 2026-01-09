# -*- coding: utf-8 -*-

from __future__ import annotations

import uuid
from typing import Any

from django.urls import reverse
from parameterized.parameterized import parameterized
from parameterized.parameterized import parameterized_class
from rest_framework import status

from speleodb.api.v1.tests.base_testcase import BaseAPIProjectTestCase
from speleodb.api.v1.tests.base_testcase import PermissionType
from speleodb.api.v1.tests.factories import ExplorationLeadFactory
from speleodb.common.enums import PermissionLevel
from speleodb.gis.models import ExplorationLead
from speleodb.utils.test_utils import named_product


class TestUnauthenticatedExplorationLeadAPIAuthentication(BaseAPIProjectTestCase):
    """Test authentication requirements for exploration lead API endpoints."""

    def test_lead_list_requires_authentication(self) -> None:
        """Test that exploration lead list endpoint requires authentication."""
        response = self.client.get(
            reverse("api:v1:project-exploration-leads", kwargs={"id": self.project.id}),
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_lead_detail_requires_authentication(self) -> None:
        """Test that exploration lead detail endpoint requires authentication."""
        lead = ExplorationLeadFactory.create(project=self.project)
        response = self.client.get(
            reverse("api:v1:exploration-lead-detail", kwargs={"id": lead.id})
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_lead_create_requires_authentication(self) -> None:
        """Test that exploration lead create endpoint requires authentication."""
        data = {
            "description": "Test lead description",
            "latitude": "45.1234567",
            "longitude": "-123.8765432",
        }
        response = self.client.post(
            reverse("api:v1:project-exploration-leads", kwargs={"id": self.project.id}),
            data=data,
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_lead_update_requires_authentication(self) -> None:
        """Test that exploration lead update endpoint requires authentication."""
        lead = ExplorationLeadFactory.create(project=self.project)
        data = {"description": "Updated description"}
        response = self.client.patch(
            reverse("api:v1:exploration-lead-detail", kwargs={"id": lead.id}),
            data=data,
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_lead_delete_requires_authentication(self) -> None:
        """Test that exploration lead delete endpoint requires authentication."""
        lead = ExplorationLeadFactory.create(project=self.project)
        response = self.client.delete(
            reverse("api:v1:exploration-lead-detail", kwargs={"id": lead.id})
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN


@parameterized_class(
    [
        "level",
        "permission_type",
    ],
    named_product(
        level=[
            PermissionLevel.ADMIN,
            PermissionLevel.READ_AND_WRITE,
            PermissionLevel.READ_ONLY,
            PermissionLevel.WEB_VIEWER,
        ],
        permission_type=[PermissionType.USER, PermissionType.TEAM],
    ),
)
class TestExplorationLeadAPIPermissions(BaseAPIProjectTestCase):
    """Test permission requirements for exploration lead API endpoints."""

    level: PermissionLevel
    permission_type: PermissionType
    lead: ExplorationLead

    def setUp(self) -> None:
        super().setUp()

        self.set_test_project_permission(
            level=self.level,
            permission_type=self.permission_type,
        )

        self.lead = ExplorationLeadFactory.create(project=self.project)

    def test_lead_list_permissions(self) -> None:
        """Test exploration lead list endpoint with different permission levels."""
        response = self.client.get(
            reverse("api:v1:project-exploration-leads", kwargs={"id": self.project.id}),
            headers={"authorization": self.auth},
        )
        assert (
            response.status_code == status.HTTP_200_OK
            if self.level != PermissionLevel.WEB_VIEWER
            else status.HTTP_403_FORBIDDEN
        )

    def test_lead_detail_permissions(self) -> None:
        """Test exploration lead detail endpoint with different permission levels."""
        response = self.client.get(
            reverse("api:v1:exploration-lead-detail", kwargs={"id": self.lead.id}),
            headers={"authorization": self.auth},
        )
        assert (
            response.status_code == status.HTTP_200_OK
            if self.level != PermissionLevel.WEB_VIEWER
            else status.HTTP_403_FORBIDDEN
        )

    def test_lead_create_permissions(self) -> None:
        """Test exploration lead create endpoint with different permission levels."""
        data = {
            "description": f"Lead at level {self.level}",
            "latitude": "45.1234567",
            "longitude": "-123.8765432",
        }

        response = self.client.post(
            reverse("api:v1:project-exploration-leads", kwargs={"id": self.project.id}),
            data=data,
            headers={"authorization": self.auth},
            content_type="application/json",
        )

        assert (
            response.status_code == status.HTTP_201_CREATED
            if self.level >= PermissionLevel.READ_AND_WRITE
            else status.HTTP_403_FORBIDDEN
        )

    def test_lead_update_permissions(self) -> None:
        """Test exploration lead update endpoint with different permission levels."""
        data = {"description": "Updated description"}

        response = self.client.patch(
            reverse("api:v1:exploration-lead-detail", kwargs={"id": self.lead.id}),
            data=data,
            headers={"authorization": self.auth},
            content_type="application/json",
        )

        assert (
            response.status_code == status.HTTP_200_OK
            if self.level >= PermissionLevel.READ_AND_WRITE
            else status.HTTP_403_FORBIDDEN
        )

    def test_lead_delete_permissions(self) -> None:
        """Test exploration lead delete endpoint with different permission levels."""
        response = self.client.delete(
            reverse("api:v1:exploration-lead-detail", kwargs={"id": self.lead.id}),
            headers={"authorization": self.auth},
        )

        assert (
            response.status_code == status.HTTP_200_OK
            if self.level == PermissionLevel.ADMIN
            else status.HTTP_403_FORBIDDEN
        )


@parameterized_class(
    [
        "level",
        "permission_type",
    ],
    named_product(
        level=[
            PermissionLevel.ADMIN,
            PermissionLevel.READ_AND_WRITE,
            PermissionLevel.READ_ONLY,
            PermissionLevel.WEB_VIEWER,
        ],
        permission_type=[PermissionType.USER, PermissionType.TEAM],
    ),
)
class TestExplorationLeadCRUDOperations(BaseAPIProjectTestCase):
    """Test CRUD operations for exploration leads."""

    level: PermissionLevel
    permission_type: PermissionType

    def setUp(self) -> None:
        super().setUp()

        self.set_test_project_permission(
            level=self.level,
            permission_type=self.permission_type,
        )

    def test_create_lead_success(self) -> None:
        """Test successful exploration lead creation."""
        data = {
            "description": "Promising lead heading north",
            "latitude": "45.14908328409823490234567",
            "longitude": "-123.876032940239093049235432",
        }

        response = self.client.post(
            reverse("api:v1:project-exploration-leads", kwargs={"id": self.project.id}),
            data=data,
            headers={"authorization": self.auth},
            content_type="application/json",
        )

        if self.level < PermissionLevel.READ_AND_WRITE:
            assert response.status_code == status.HTTP_403_FORBIDDEN
            return

        assert response.status_code == status.HTTP_201_CREATED
        lead_data = response.data["data"]
        assert lead_data["description"] == "Promising lead heading north"
        assert lead_data["latitude"] == 45.1490833  # noqa: PLR2004
        assert lead_data["longitude"] == -123.8760329  # noqa: PLR2004

    def test_list_project_leads(self) -> None:
        """Test successful exploration lead listing."""
        # Create test leads
        leads = ExplorationLeadFactory.create_batch(3, project=self.project)

        response = self.client.get(
            reverse("api:v1:project-exploration-leads", kwargs={"id": self.project.id}),
            headers={"authorization": self.auth},
        )

        if self.level == PermissionLevel.WEB_VIEWER:
            assert response.status_code == status.HTTP_403_FORBIDDEN
            return

        assert response.status_code == status.HTTP_200_OK
        leads_data = response.json()["data"]
        assert len(leads_data) == 3  # noqa: PLR2004

        # Verify lead IDs are present
        lead_ids = {str(lead.id) for lead in leads}
        response_ids = {lead["id"] for lead in leads_data}
        assert lead_ids == response_ids

    def test_retrieve_lead_success(self) -> None:
        """Test successful exploration lead retrieval."""
        lead = ExplorationLeadFactory.create(project=self.project)

        response = self.client.get(
            reverse("api:v1:exploration-lead-detail", kwargs={"id": lead.id}),
            headers={"authorization": self.auth},
        )

        if self.level == PermissionLevel.WEB_VIEWER:
            assert response.status_code == status.HTTP_403_FORBIDDEN
            return

        assert response.status_code == status.HTTP_200_OK
        lead_data = response.data["data"]
        assert lead_data["id"] == str(lead.id)
        assert lead_data["description"] == lead.description

    def test_delete_lead_success(self) -> None:
        """Test successful exploration lead deletion."""
        lead = ExplorationLeadFactory.create(project=self.project)
        lead_id = str(lead.id)

        response = self.client.delete(
            reverse("api:v1:exploration-lead-detail", kwargs={"id": lead.id}),
            headers={"authorization": self.auth},
        )

        if self.level != PermissionLevel.ADMIN:
            assert response.status_code == status.HTTP_403_FORBIDDEN
            return

        assert response.status_code == status.HTTP_200_OK
        assert lead_id == response.data["data"]["id"]

        # Verify lead is deleted
        assert not ExplorationLead.objects.filter(id=lead.id).exists()

    @parameterized.expand(["PUT", "PATCH"])
    def test_update_lead(self, method: str) -> None:
        """Test updating an exploration lead."""
        lead = ExplorationLeadFactory.create(
            project=self.project, description="Original description"
        )

        data: dict[str, Any] = {
            "description": "Updated description",
        }

        match method:
            case "PUT":
                data.update(latitude=12.3, longitude=-30.23)
                client_method = self.client.put

            case "PATCH":
                client_method = self.client.patch

            case _:
                raise ValueError(f"Unknown method received: {method}")

        response = client_method(
            reverse("api:v1:exploration-lead-detail", kwargs={"id": lead.id}),
            data=data,
            headers={"authorization": self.auth},
            content_type="application/json",
        )

        if self.level < PermissionLevel.READ_AND_WRITE:
            assert response.status_code == status.HTTP_403_FORBIDDEN, (
                response.status_code,
                self.level,
                self.permission_type,
            )
            return

        assert response.status_code == status.HTTP_200_OK, (
            response.status_code,
            self.level,
            self.permission_type,
        )

        resp_data = response.data["data"]
        assert resp_data["description"] == data["description"]

        if method == "PUT":
            assert resp_data["latitude"] == data["latitude"]
            assert resp_data["longitude"] == data["longitude"]


@parameterized_class(
    [
        "level",
        "permission_type",
    ],
    named_product(
        level=[
            PermissionLevel.ADMIN,
            PermissionLevel.READ_AND_WRITE,
            PermissionLevel.READ_ONLY,
            PermissionLevel.WEB_VIEWER,
        ],
        permission_type=[PermissionType.USER, PermissionType.TEAM],
    ),
)
class TestExplorationLeadValidation(BaseAPIProjectTestCase):
    """Test validation rules for exploration lead data."""

    level: PermissionLevel
    permission_type: PermissionType

    def setUp(self) -> None:
        super().setUp()
        self.set_test_project_permission(self.level, self.permission_type)

    def test_create_lead_missing_coordinates(self) -> None:
        """Test exploration lead creation fails without coordinates."""
        data = {
            "description": "Test lead",
        }

        response = self.client.post(
            reverse("api:v1:project-exploration-leads", kwargs={"id": self.project.id}),
            data=data,
            headers={"authorization": self.auth},
            content_type="application/json",
        )

        if self.level < PermissionLevel.READ_AND_WRITE:
            assert response.status_code == status.HTTP_403_FORBIDDEN
            return

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "latitude" in response.data["errors"]
        assert "longitude" in response.data["errors"]

    def test_create_lead_invalid_coordinates(self) -> None:
        """Test exploration lead creation rejects invalid coordinates."""
        data = {
            "description": "Test lead",
            "latitude": "99.9999999",  # Invalid latitude (>90)
            "longitude": "-180.0000000",  # Valid longitude (at boundary)
        }

        response = self.client.post(
            reverse("api:v1:project-exploration-leads", kwargs={"id": self.project.id}),
            data=data,
            headers={"authorization": self.auth},
            content_type="application/json",
        )

        if self.level < PermissionLevel.READ_AND_WRITE:
            assert response.status_code == status.HTTP_403_FORBIDDEN, response.data
            return

        # Coordinate validation IS implemented - latitude must be between -90 and 90
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "latitude" in response.data.get("errors", {})


@parameterized_class(
    [
        "level",
        "permission_type",
    ],
    named_product(
        level=[
            PermissionLevel.ADMIN,
            PermissionLevel.READ_AND_WRITE,
            PermissionLevel.READ_ONLY,
            PermissionLevel.WEB_VIEWER,
        ],
        permission_type=[PermissionType.USER, PermissionType.TEAM],
    ),
)
class TestExplorationLeadEdgeCases(BaseAPIProjectTestCase):
    """Test edge cases and error handling."""

    level: PermissionLevel
    permission_type: PermissionType

    def setUp(self) -> None:
        super().setUp()
        self.set_test_project_permission(self.level, self.permission_type)

    def test_retrieve_nonexistent_lead(self) -> None:
        """Test retrieving a non-existent exploration lead."""
        response = self.client.get(
            reverse("api:v1:exploration-lead-detail", kwargs={"id": uuid.uuid4()}),
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_update_nonexistent_lead(self) -> None:
        """Test updating a non-existent exploration lead."""
        data = {"description": "Updated"}

        response = self.client.patch(
            reverse("api:v1:exploration-lead-detail", kwargs={"id": uuid.uuid4()}),
            data=data,
            headers={"authorization": self.auth},
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_nonexistent_lead(self) -> None:
        """Test deleting a non-existent exploration lead."""
        response = self.client.delete(
            reverse("api:v1:exploration-lead-detail", kwargs={"id": uuid.uuid4()}),
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_extreme_coordinate_precision(self) -> None:
        """Test handling of coordinates with extreme precision."""
        data = {
            "description": "High precision test",
            "latitude": "45.12345678901234567890",  # More than 7 decimal places
            "longitude": "-123.98765432109876543210",
        }

        response = self.client.post(
            reverse("api:v1:project-exploration-leads", kwargs={"id": self.project.id}),
            data=data,
            headers={"authorization": self.auth},
            content_type="application/json",
        )

        if self.level < PermissionLevel.READ_AND_WRITE:
            assert response.status_code == status.HTTP_403_FORBIDDEN, response.data
            return

        assert response.status_code == status.HTTP_201_CREATED
        # Coordinates should be rounded to 7 decimal places
        lead_data = response.data["data"]
        assert lead_data["latitude"] == 45.1234568  # noqa: PLR2004
        assert lead_data["longitude"] == -123.9876543  # noqa: PLR2004

    def test_empty_description(self) -> None:
        """Test exploration lead creation with empty description."""
        data = {
            "description": "",
            "latitude": "45.1234567",
            "longitude": "-123.8765432",
        }

        response = self.client.post(
            reverse("api:v1:project-exploration-leads", kwargs={"id": self.project.id}),
            data=data,
            headers={"authorization": self.auth},
            content_type="application/json",
        )

        if self.level < PermissionLevel.READ_AND_WRITE:
            assert response.status_code == status.HTTP_403_FORBIDDEN, response.data
            return

        assert response.status_code == status.HTTP_201_CREATED


@parameterized_class(
    [
        "level",
        "permission_type",
    ],
    named_product(
        level=[
            PermissionLevel.ADMIN,
            PermissionLevel.READ_AND_WRITE,
            PermissionLevel.READ_ONLY,
            PermissionLevel.WEB_VIEWER,
        ],
        permission_type=[PermissionType.USER, PermissionType.TEAM],
    ),
)
class TestExplorationLeadCoordinateRounding(BaseAPIProjectTestCase):
    """Test coordinate rounding functionality."""

    level: PermissionLevel
    permission_type: PermissionType

    def setUp(self) -> None:
        super().setUp()
        self.set_test_project_permission(self.level, self.permission_type)

    def test_coordinate_rounding_on_create(self) -> None:
        """Test that coordinates are properly rounded to 7 decimal places on
        creation."""

        data = {
            "description": "Coordinate rounding test",
            "latitude": "45.123456789012345",  # 15 decimal places
            "longitude": "-123.987654321098765",  # 15 decimal places
        }

        response = self.client.post(
            reverse("api:v1:project-exploration-leads", kwargs={"id": self.project.id}),
            data=data,
            headers={"authorization": self.auth},
            content_type="application/json",
        )

        if self.level < PermissionLevel.READ_AND_WRITE:
            assert response.status_code == status.HTTP_403_FORBIDDEN, response.data
            return

        assert response.status_code == status.HTTP_201_CREATED
        lead_data = response.data["data"]

        # Check that coordinates were rounded to 7 decimal places
        assert lead_data["latitude"] == 45.1234568  # noqa: PLR2004
        assert lead_data["longitude"] == -123.9876543  # noqa: PLR2004

    def test_coordinate_rounding_on_update(self) -> None:
        """Test that coordinates are properly rounded on update."""
        # Create a lead first
        lead = ExplorationLeadFactory.create(
            project=self.project,
            latitude=45.1,
            longitude=-123.9,
        )

        # Update with high precision coordinates
        data = {
            "latitude": "46.987654321098765",
            "longitude": "-124.123456789012345",
        }

        response = self.client.patch(
            reverse("api:v1:exploration-lead-detail", kwargs={"id": lead.id}),
            data=data,
            headers={"authorization": self.auth},
            content_type="application/json",
        )

        if self.level < PermissionLevel.READ_AND_WRITE:
            assert response.status_code == status.HTTP_403_FORBIDDEN, response.data
            return

        assert response.status_code == status.HTTP_200_OK
        lead_data = response.data["data"]

        # Check that coordinates were rounded to 7 decimal places
        assert lead_data["latitude"] == 46.9876543  # noqa: PLR2004
        assert lead_data["longitude"] == -124.1234568  # noqa: PLR2004


@parameterized_class(
    [
        "level",
        "permission_type",
    ],
    named_product(
        level=[
            PermissionLevel.ADMIN,
            PermissionLevel.READ_AND_WRITE,
            PermissionLevel.READ_ONLY,
            PermissionLevel.WEB_VIEWER,
        ],
        permission_type=[PermissionType.USER, PermissionType.TEAM],
    ),
)
class TestExplorationLeadGeoJSON(BaseAPIProjectTestCase):
    """Test GeoJSON endpoint for exploration leads."""

    level: PermissionLevel
    permission_type: PermissionType

    def setUp(self) -> None:
        super().setUp()
        self.set_test_project_permission(self.level, self.permission_type)

    def test_geojson_endpoint(self) -> None:
        """Test that GeoJSON endpoint returns correct format."""
        # Create test leads
        ExplorationLeadFactory.create_batch(2, project=self.project)

        response = self.client.get(
            reverse(
                "api:v1:project-exploration-leads-geojson",
                kwargs={"id": self.project.id},
            ),
            headers={"authorization": self.auth},
        )

        if self.level == PermissionLevel.WEB_VIEWER:
            assert response.status_code == status.HTTP_403_FORBIDDEN
            return

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Verify GeoJSON structure
        assert data["type"] == "FeatureCollection"
        assert len(data["features"]) == 2  # noqa: PLR2004

        # Verify feature structure
        feature = data["features"][0]
        assert feature["type"] == "Feature"
        assert feature["geometry"]["type"] == "Point"
        assert len(feature["geometry"]["coordinates"]) == 2  # noqa: PLR2004
        assert "id" in feature
        assert "description" in feature["properties"]
        assert "project" in feature["properties"]
