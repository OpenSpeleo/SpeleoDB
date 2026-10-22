# -*- coding: utf-8 -*-

from __future__ import annotations

import uuid
from typing import Any

from django.urls import reverse
from parameterized.parameterized import parameterized
from parameterized.parameterized import parameterized_class
from rest_framework import status

from speleodb.api.v2.tests.base_testcase import BaseAPIProjectTestCase
from speleodb.api.v2.tests.base_testcase import PermissionType
from speleodb.api.v2.tests.factories import SubSurfaceStationFactory
from speleodb.common.enums import PermissionLevel
from speleodb.gis.models import Station
from speleodb.gis.models import SubSurfaceStation
from speleodb.utils.sanitize import sanitize_text
from speleodb.utils.test_utils import named_product


class TestUnauthenticatedStationAPIAuthentication(BaseAPIProjectTestCase):
    """Test authentication requirements for station API endpoints."""

    def test_station_list_requires_authentication(self) -> None:
        """Test that station list endpoint requires authentication."""
        response = self.client.get(
            reverse("api:v2:project-stations", kwargs={"id": self.project.id}),
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_station_detail_requires_authentication(self) -> None:
        """Test that station detail endpoint requires authentication."""
        station = SubSurfaceStationFactory.create(project=self.project)
        response = self.client.get(
            reverse("api:v2:station-detail", kwargs={"id": station.id})
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_station_create_requires_authentication(self) -> None:
        """Test that station create endpoint requires authentication."""
        data = {
            "name": "ST001",
            "description": "Test station",
            "latitude": "45.1234567",
            "longitude": "-123.8765432",
            "type": "sensor",
        }
        response = self.client.post(
            reverse("api:v2:project-stations", kwargs={"id": self.project.id}),
            data=data,
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_station_update_requires_authentication(self) -> None:
        """Test that station update endpoint requires authentication."""
        station = SubSurfaceStationFactory.create(project=self.project)
        data = {"name": "ST002", "description": "Updated description"}
        response = self.client.patch(
            reverse("api:v2:station-detail", kwargs={"id": station.id}),
            data=data,
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_station_delete_requires_authentication(self) -> None:
        """Test that station delete endpoint requires authentication."""
        station = SubSurfaceStationFactory.create(project=self.project)
        response = self.client.delete(
            reverse("api:v2:station-detail", kwargs={"id": station.id})
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN


@parameterized_class(
    [
        "level",
        "permission_type",
    ],
    [
        (level, permission_type)
        for level, permission_type in named_product(
            level=[
                PermissionLevel.ADMIN,
                PermissionLevel.READ_AND_WRITE,
                PermissionLevel.READ_ONLY,
                PermissionLevel.WEB_VIEWER,
            ],
            permission_type=[PermissionType.USER, PermissionType.TEAM],
        )
        if (level, permission_type) != (PermissionLevel.ADMIN, PermissionType.TEAM)
    ],
)
class TestStationAPIPermissions(BaseAPIProjectTestCase):
    """Test authentication requirements for station API endpoints."""

    level: PermissionLevel
    permission_type: PermissionType
    station: SubSurfaceStation

    def setUp(self) -> None:
        super().setUp()

        self.set_test_project_permission(
            level=self.level,
            permission_type=self.permission_type,
        )

        self.station = SubSurfaceStationFactory.create(project=self.project)

    def test_station_list_permissions(self) -> None:
        """Test station list endpoint with different permission levels."""

        response = self.client.get(
            reverse("api:v2:project-stations", kwargs={"id": self.project.id}),
            headers={"authorization": self.auth},
        )
        assert response.status_code == (
            status.HTTP_200_OK
            if self.level != PermissionLevel.WEB_VIEWER
            else status.HTTP_403_FORBIDDEN
        )

    def test_station_detail_permissions(self) -> None:
        """Test station detail endpoint with different permission levels."""

        response = self.client.get(
            reverse("api:v2:station-detail", kwargs={"id": self.station.id}),
            headers={"authorization": self.auth},
        )
        assert response.status_code == (
            status.HTTP_200_OK
            if self.level != PermissionLevel.WEB_VIEWER
            else status.HTTP_403_FORBIDDEN
        )

    def test_station_create_permissions(self) -> None:
        """Test station create endpoint with different permission levels."""

        data = {
            "name": f"ST{self.level:03d}_{str(uuid.uuid4())[:8]}",
            "description": "Test station",
            "latitude": "45.1234567",
            "longitude": "-123.8765432",
            "type": "sensor",
        }

        response = self.client.post(
            reverse("api:v2:project-stations", kwargs={"id": self.project.id}),
            data=data,
            headers={"authorization": self.auth},
            content_type="application/json",
        )

        assert response.status_code == (
            status.HTTP_201_CREATED
            if self.level >= PermissionLevel.READ_AND_WRITE
            else status.HTTP_403_FORBIDDEN
        )

    @parameterized.expand(["put", "patch"])
    def test_station_update_permissions(self, method: str) -> None:
        """Test station update endpoint with different permission levels."""

        data = {
            "name": self.station.name,
            "description": "Updated description",
            "latitude": "1.0",
            "longitude": "2.0",
            "type": self.station.type,
        }

        response = getattr(self.client, method)(
            reverse("api:v2:station-detail", kwargs={"id": self.station.id}),
            data=data,
            headers={"authorization": self.auth},
            content_type="application/json",
        )

        assert response.status_code == (
            status.HTTP_200_OK
            if self.level >= PermissionLevel.READ_AND_WRITE
            else status.HTTP_403_FORBIDDEN
        )

    def test_station_delete_permissions(self) -> None:
        """Test station delete endpoint with different permission levels."""

        response = self.client.delete(
            reverse("api:v2:station-detail", kwargs={"id": self.station.id}),
            headers={"authorization": self.auth},
        )

        assert response.status_code == (
            status.HTTP_200_OK
            if self.level == PermissionLevel.ADMIN
            else status.HTTP_403_FORBIDDEN
        )

    def test_station_geojson_permissions(self) -> None:
        response = self.client.get(
            reverse("api:v2:project-stations-geojson", kwargs={"id": self.project.id}),
            headers={"authorization": self.auth},
        )
        assert response.status_code == (
            status.HTTP_403_FORBIDDEN
            if self.level == PermissionLevel.WEB_VIEWER
            else status.HTTP_200_OK
        )

    def test_user_station_list_filters_by_permission(self) -> None:
        response = self.client.get(
            reverse("api:v2:subsurface-stations"),
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_200_OK
        assert {row["id"] for row in response.data} == (
            set()
            if self.level == PermissionLevel.WEB_VIEWER
            else {str(self.station.id)}
        )


class TestStationCRUDOperations(BaseAPIProjectTestCase):
    """Test CRUD operations for stations."""

    level = PermissionLevel.ADMIN
    permission_type = PermissionType.USER
    station: Station

    def setUp(self) -> None:
        super().setUp()

        self.set_test_project_permission(
            level=self.level,
            permission_type=self.permission_type,
        )

    def test_create_station_success(self) -> None:
        """Test successful station creation."""
        data = {
            "name": "ST001",
            "description": "Main cave entrance",
            "latitude": "45.14908328409823490234567",
            "longitude": "-123.876032940239093049235432",
            "type": "sensor",
        }

        response = self.client.post(
            reverse("api:v2:project-stations", kwargs={"id": self.project.id}),
            data=data,
            headers={"authorization": self.auth},
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        station_data = response.data
        assert station_data["name"] == "ST001"
        assert station_data["description"] == "Main cave entrance"
        assert station_data["latitude"] == 45.1490833  # noqa: PLR2004
        assert station_data["longitude"] == -123.8760329  # noqa: PLR2004

    def test_list_project_stations(self) -> None:
        """Test successful station listing."""
        # Create test stations
        stations = SubSurfaceStationFactory.create_batch(3, project=self.project)

        response = self.client.get(
            reverse("api:v2:project-stations", kwargs={"id": self.project.id}),
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_200_OK
        stations_data = response.json()
        assert len(stations_data) == 3  # noqa: PLR2004

        # Verify station IDs are present
        station_ids = {str(station.id) for station in stations}
        response_ids = {station["id"] for station in stations_data}
        assert station_ids == response_ids

    def test_list_user_stations(self) -> None:
        """Test successful station listing."""
        # Create test stations
        stations = SubSurfaceStationFactory.create_batch(3, project=self.project)

        response = self.client.get(
            reverse("api:v2:subsurface-stations"),
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_200_OK

        assert response.status_code == status.HTTP_200_OK
        stations_data = response.json()
        assert len(stations_data) == 3  # noqa: PLR2004

        # Verify station IDs are present
        station_ids = {str(station.id) for station in stations}
        response_ids = {station["id"] for station in stations_data}
        assert station_ids == response_ids

    def test_retrieve_station_success(self) -> None:
        """Test successful station retrieval."""
        station = SubSurfaceStationFactory.create(project=self.project)

        response = self.client.get(
            reverse("api:v2:station-detail", kwargs={"id": station.id}),
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_200_OK
        station_data = response.data
        assert station_data["id"] == str(station.id)
        assert station_data["name"] == station.name
        assert len(station_data["resources"]) == 0

    def test_delete_station_success(self) -> None:
        """Test successful station deletion."""
        station = SubSurfaceStationFactory.create(project=self.project)
        station_id = str(station.id)

        response = self.client.delete(
            reverse("api:v2:station-detail", kwargs={"id": station.id}),
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_200_OK
        assert station_id == response.data["id"]

        # Verify station is deleted
        assert not Station.objects.filter(id=station.id).exists()

    @parameterized.expand(["PUT", "PATCH"])
    def test_update_station(self, method: str) -> None:
        """Test updating a station to a project with a duplicate name."""
        # Create stations with the same name in both projects
        station = SubSurfaceStationFactory.create(
            project=self.project, name="DuplicateName"
        )

        # Try to update station1 to move it to the second project (should fail)
        data: dict[str, Any] = {
            "name": "DuplicateName",
            "description": "Updated description",
        }

        match method:
            case "PUT":
                # PUT requires all fields including type (must match existing)
                data.update(latitude=12.3, longitude=-30.23, type="sensor")
                client_method = self.client.put

            case "PATCH":
                client_method = self.client.patch

            case _:
                raise ValueError(f"Unknown method received: {method}")

        response = client_method(
            reverse("api:v2:station-detail", kwargs={"id": station.id}),
            data=data,
            headers={"authorization": self.auth},
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_200_OK, (
            response.status_code,
            self.level,
            self.permission_type,
        )

        resp_data = response.data

        assert resp_data["name"] == data["name"]
        assert resp_data["description"] == data["description"]

        if method == "PUT":
            assert resp_data["latitude"] == data["latitude"]
            assert resp_data["longitude"] == data["longitude"]


class TestStationValidation(BaseAPIProjectTestCase):
    """Test validation rules for station data."""

    level = PermissionLevel.ADMIN
    permission_type = PermissionType.USER

    def setUp(self) -> None:
        super().setUp()
        self.set_test_project_permission(self.level, self.permission_type)

    def test_create_station_missing_name(self) -> None:
        """Test station creation fails without name."""
        data = {
            "description": "Test station",
            "latitude": "45.1234567",
            "longitude": "-123.8765432",
            "type": "sensor",
        }

        response = self.client.post(
            reverse("api:v2:project-stations", kwargs={"id": self.project.id}),
            data=data,
            headers={"authorization": self.auth},
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "name" in response.data["errors"]

    def test_create_station_invalid_coordinates(self) -> None:
        """Test station creation rejects invalid coordinates (validators are
        implemented)."""
        data = {
            "name": f"ST_{str(uuid.uuid4())[:8]}",
            "description": "Test station",
            "latitude": "99.9999999",  # Invalid latitude (>90)
            "longitude": "-180.0000000",  # Valid longitude (at boundary)
            "type": "sensor",
        }

        response = self.client.post(
            reverse("api:v2:project-stations", kwargs={"id": self.project.id}),
            data=data,
            headers={"authorization": self.auth},
            content_type="application/json",
        )

        # Coordinate validation IS implemented - latitude must be between -90 and 90
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "latitude" in response.data.get("errors", {})

    def test_station_name_length_limit(self) -> None:
        """Test station name length validation."""
        long_name = "x" * 201  # Assuming 200 char limit

        data = {
            "name": long_name,
            "description": "Test station",
            "latitude": "45.1234567",
            "longitude": "-123.8765432",
            "type": "sensor",
        }

        response = self.client.post(
            reverse("api:v2:project-stations", kwargs={"id": self.project.id}),
            data=data,
            headers={"authorization": self.auth},
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "name" in response.data["errors"]


class TestStationEdgeCases(BaseAPIProjectTestCase):
    """Test edge cases and error handling."""

    level = PermissionLevel.ADMIN
    permission_type = PermissionType.USER

    def setUp(self) -> None:
        super().setUp()
        self.set_test_project_permission(self.level, self.permission_type)

    def test_retrieve_nonexistent_station(self) -> None:
        """Test retrieving a non-existent station."""

        response = self.client.get(
            reverse("api:v2:station-detail", kwargs={"id": uuid.uuid4()}),
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_update_nonexistent_station(self) -> None:
        """Test updating a non-existent station."""
        data = {"name": "Updated"}

        response = self.client.patch(
            reverse("api:v2:station-detail", kwargs={"id": uuid.uuid4()}),
            data=data,
            headers={"authorization": self.auth},
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_nonexistent_station(self) -> None:
        """Test deleting a non-existent station."""

        response = self.client.delete(
            reverse("api:v2:station-detail", kwargs={"id": uuid.uuid4()}),
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestStationAPIFuzzing(BaseAPIProjectTestCase):
    """Test API with random/fuzzing data."""

    level = PermissionLevel.ADMIN
    permission_type = PermissionType.USER

    def setUp(self) -> None:
        super().setUp()
        self.set_test_project_permission(self.level, self.permission_type)

    def test_unicode_station_names(self) -> None:
        """Test creating stations with unicode characters."""
        unicode_names = [
            "Station αβγ",
            "駅 🚉",
            "Станция №1",
            "محطة ١",  # noqa: RUF001
            "स्टेशन १",
        ]

        for name in unicode_names:
            data = {
                "name": name,
                "description": "Unicode test",
                "latitude": "45.1234567",
                "longitude": "-123.8765432",
                "type": "sensor",
            }

            response = self.client.post(
                reverse("api:v2:project-stations", kwargs={"id": self.project.id}),
                data=data,
                headers={"authorization": self.auth},
                content_type="application/json",
            )

            # Should handle unicode properly (sanitization strips combining marks)
            assert response.status_code == status.HTTP_201_CREATED
            assert response.data["name"] == sanitize_text(name)

    def test_xss_injection_attempts(self) -> None:
        """Test that potential XSS payloads are handled safely."""

        xss_payloads = [
            '<script>alert("XSS")</script>',
            '"><script>alert("XSS")</script>',
            "';alert(String.fromCharCode(88,83,83))//",
            '<img src=x onerror=alert("XSS")>',
            "<svg/onload=alert('XSS')>",
        ]

        for payload in xss_payloads:
            # Make names unique
            unique_name = f"{payload[:20]}_{str(uuid.uuid4())[:8]}"

            data = {
                "name": unique_name,
                "description": payload,
                "latitude": "45.1234567",
                "longitude": "-123.8765432",
                "type": "sensor",
            }

            response = self.client.post(
                reverse("api:v2:project-stations", kwargs={"id": self.project.id}),
                data=data,
                headers={"authorization": self.auth},
                content_type="application/json",
            )

            # Should accept the input but store it sanitized
            assert response.status_code == status.HTTP_201_CREATED
            stored = response.data["description"]
            assert "<script>" not in stored
            assert "<img" not in stored
            assert "<svg" not in stored
            assert stored == sanitize_text(payload)


class TestStationCoordinateRounding(BaseAPIProjectTestCase):
    """Test coordinate rounding functionality."""

    level = PermissionLevel.ADMIN
    permission_type = PermissionType.USER

    def setUp(self) -> None:
        super().setUp()
        self.set_test_project_permission(self.level, self.permission_type)

    def test_coordinate_rounding_on_update(self) -> None:
        """Test that coordinates are properly rounded on update."""
        # Create a station first
        station = SubSurfaceStationFactory.create(
            project=self.project,
            latitude=45.1,
            longitude=-123.9,
        )

        # Update with high precision coordinates
        data = {
            "latitude": "46.987654321098765",  # Many decimal places
            "longitude": "-124.123456789012345",  # Many decimal places
        }

        response = self.client.patch(
            reverse("api:v2:station-detail", kwargs={"id": station.id}),
            data=data,
            headers={"authorization": self.auth},
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_200_OK
        station_data = response.data

        # Check that coordinates were rounded to 7 decimal places
        assert station_data["latitude"] == 46.9876543  # noqa: PLR2004
        assert station_data["longitude"] == -124.1234568  # noqa: PLR2004

    def test_scientific_notation_coordinates(self) -> None:
        """Test that coordinates in scientific notation are handled."""

        data = {
            "name": f"SciNotation_{str(uuid.uuid4())[:8]}",
            "description": "Scientific notation test",
            "latitude": "4.5123456e1",  # 45.123456 in scientific notation
            "longitude": "-1.23987654e2",  # -123.987654 in scientific notation
            "type": "sensor",
        }

        response = self.client.post(
            reverse("api:v2:project-stations", kwargs={"id": self.project.id}),
            data=data,
            headers={"authorization": self.auth},
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        station_data = response.data

        # Should be converted and rounded properly
        assert station_data["latitude"] == 45.123456  # noqa: PLR2004
        assert station_data["longitude"] == -123.987654  # noqa: PLR2004

    def test_null_coordinates_not_affected(self) -> None:
        """Test that null/None coordinates are properly rejected."""

        data = {
            "name": f"NullCoords_{str(uuid.uuid4())[:8]}",
            "description": "Null coordinates test",
            # Omit coordinates entirely
        }

        response = self.client.post(
            reverse("api:v2:project-stations", kwargs={"id": self.project.id}),
            data=data,
            headers={"authorization": self.auth},
            content_type="application/json",
        )

        # Should fail because coordinates are required
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "latitude" in response.data.get("errors", {})
        assert "longitude" in response.data.get("errors", {})
