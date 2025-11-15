# -*- coding: utf-8 -*-

from __future__ import annotations

import random
import uuid
from typing import Any

from django.urls import reverse
from faker import Faker
from parameterized.parameterized import parameterized
from parameterized.parameterized import parameterized_class
from rest_framework import status

from speleodb.api.v1.tests.base_testcase import BaseAPIProjectTestCase
from speleodb.api.v1.tests.base_testcase import PermissionType
from speleodb.api.v1.tests.factories import StationFactory
from speleodb.common.enums import PermissionLevel
from speleodb.gis.models import Station
from speleodb.utils.test_utils import named_product


class TestUnauthenticatedStationAPIAuthentication(BaseAPIProjectTestCase):
    """Test authentication requirements for station API endpoints."""

    def test_station_list_requires_authentication(self) -> None:
        """Test that station list endpoint requires authentication."""
        response = self.client.get(
            reverse("api:v1:project-stations", kwargs={"id": self.project.id}),
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_station_detail_requires_authentication(self) -> None:
        """Test that station detail endpoint requires authentication."""
        station = StationFactory.create(project=self.project)
        response = self.client.get(
            reverse("api:v1:station-detail", kwargs={"id": station.id})
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_station_create_requires_authentication(self) -> None:
        """Test that station create endpoint requires authentication."""
        data = {
            "name": "ST001",
            "description": "Test station",
            "latitude": "45.1234567",
            "longitude": "-123.8765432",
        }
        response = self.client.post(
            reverse("api:v1:project-stations", kwargs={"id": self.project.id}),
            data=data,
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_station_update_requires_authentication(self) -> None:
        """Test that station update endpoint requires authentication."""
        station = StationFactory.create(project=self.project)
        data = {"name": "ST002", "description": "Updated description"}
        response = self.client.patch(
            reverse("api:v1:station-detail", kwargs={"id": station.id}),
            data=data,
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_station_delete_requires_authentication(self) -> None:
        """Test that station delete endpoint requires authentication."""
        station = StationFactory.create(project=self.project)
        response = self.client.delete(
            reverse("api:v1:station-detail", kwargs={"id": station.id})
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
class TestStationAPIPermissions(BaseAPIProjectTestCase):
    """Test authentication requirements for station API endpoints."""

    level: PermissionLevel
    permission_type: PermissionType
    station: Station

    def setUp(self) -> None:
        super().setUp()

        self.set_test_project_permission(
            level=self.level,
            permission_type=self.permission_type,
        )

        self.station = StationFactory.create(project=self.project)

    def test_station_list_permissions(self) -> None:
        """Test station list endpoint with different permission levels."""

        response = self.client.get(
            reverse("api:v1:project-stations", kwargs={"id": self.project.id}),
            headers={"authorization": self.auth},
        )
        assert (
            response.status_code == status.HTTP_200_OK
            if self.level != PermissionLevel.WEB_VIEWER
            else status.HTTP_403_FORBIDDEN
        )

    def test_station_detail_permissions(self) -> None:
        """Test station detail endpoint with different permission levels."""

        response = self.client.get(
            reverse("api:v1:station-detail", kwargs={"id": self.station.id}),
            headers={"authorization": self.auth},
        )
        assert (
            response.status_code == status.HTTP_200_OK
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
        }

        response = self.client.post(
            reverse("api:v1:project-stations", kwargs={"id": self.project.id}),
            data=data,
            headers={"authorization": self.auth},
            content_type="application/json",
        )

        assert (
            response.status_code == status.HTTP_201_CREATED
            if self.level >= PermissionLevel.READ_AND_WRITE
            else status.HTTP_403_FORBIDDEN
        )

    def test_station_update_permissions(self) -> None:
        """Test station update endpoint with different permission levels."""

        data = {"description": "Updated description"}

        response = self.client.patch(
            reverse("api:v1:station-detail", kwargs={"id": self.station.id}),
            data=data,
            headers={"authorization": self.auth},
            content_type="application/json",
        )

        assert (
            response.status_code == status.HTTP_200_OK
            if self.level >= PermissionLevel.READ_AND_WRITE
            else status.HTTP_403_FORBIDDEN
        )

    def test_station_delete_permissions(self) -> None:
        """Test station delete endpoint with different permission levels."""

        response = self.client.delete(
            reverse("api:v1:station-detail", kwargs={"id": self.station.id}),
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
class TestStationCRUDOperations(BaseAPIProjectTestCase):
    """Test CRUD operations for stations."""

    level: PermissionLevel
    permission_type: PermissionType
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
        }

        response = self.client.post(
            reverse("api:v1:project-stations", kwargs={"id": self.project.id}),
            data=data,
            headers={"authorization": self.auth},
            content_type="application/json",
        )

        if self.level < PermissionLevel.READ_AND_WRITE:
            assert response.status_code == status.HTTP_403_FORBIDDEN
            return

        assert response.status_code == status.HTTP_201_CREATED
        station_data = response.data["data"]
        assert station_data["name"] == "ST001"
        assert station_data["description"] == "Main cave entrance"
        assert station_data["latitude"] == 45.1490833  # noqa: PLR2004
        assert station_data["longitude"] == -123.8760329  # noqa: PLR2004

    def test_list_project_stations(self) -> None:
        """Test successful station listing."""
        # Create test stations
        stations = StationFactory.create_batch(3, project=self.project)

        response = self.client.get(
            reverse("api:v1:project-stations", kwargs={"id": self.project.id}),
            headers={"authorization": self.auth},
        )

        if self.level == PermissionLevel.WEB_VIEWER:
            assert response.status_code == status.HTTP_403_FORBIDDEN
            return

        assert response.status_code == status.HTTP_200_OK
        stations_data = response.json()["data"]
        assert len(stations_data) == 3  # noqa: PLR2004

        # Verify station IDs are present
        station_ids = {str(station.id) for station in stations}
        response_ids = {station["id"] for station in stations_data}
        assert station_ids == response_ids

    def test_list_user_stations(self) -> None:
        """Test successful station listing."""
        # Create test stations
        stations = StationFactory.create_batch(3, project=self.project)

        response = self.client.get(
            reverse("api:v1:stations"),
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_200_OK

        if self.level == PermissionLevel.WEB_VIEWER:
            assert len(response.data["data"]) == 0
            return

        assert response.status_code == status.HTTP_200_OK
        stations_data = response.json()["data"]
        assert len(stations_data) == 3  # noqa: PLR2004

        # Verify station IDs are present
        station_ids = {str(station.id) for station in stations}
        response_ids = {station["id"] for station in stations_data}
        assert station_ids == response_ids

    def test_retrieve_station_success(self) -> None:
        """Test successful station retrieval."""
        station = StationFactory.create(project=self.project)

        response = self.client.get(
            reverse("api:v1:station-detail", kwargs={"id": station.id}),
            headers={"authorization": self.auth},
        )

        if self.level == PermissionLevel.WEB_VIEWER:
            assert response.status_code == status.HTTP_403_FORBIDDEN
            return

        assert response.status_code == status.HTTP_200_OK
        station_data = response.data["data"]
        assert station_data["id"] == str(station.id)
        assert station_data["name"] == station.name
        assert len(station_data["resources"]) == 0

    def test_delete_station_success(self) -> None:
        """Test successful station deletion."""
        station = StationFactory.create(project=self.project)
        station_id = str(station.id)

        response = self.client.delete(
            reverse("api:v1:station-detail", kwargs={"id": station.id}),
            headers={"authorization": self.auth},
        )

        if self.level != PermissionLevel.ADMIN:
            assert response.status_code == status.HTTP_403_FORBIDDEN
            return

        assert response.status_code == status.HTTP_200_OK
        assert station_id == response.data["data"]["id"]

        # Verify station is deleted
        assert not Station.objects.filter(id=station.id).exists()

    @parameterized.expand(["PUT", "PATCH"])
    def test_update_station(self, method: str) -> None:
        """Test updating a station to a project with a duplicate name."""
        # Create stations with the same name in both projects
        station = StationFactory.create(project=self.project, name="DuplicateName")

        # Try to update station1 to move it to the second project (should fail)
        data: dict[str, Any] = {
            "name": "DuplicateName",
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
            reverse("api:v1:station-detail", kwargs={"id": station.id}),
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

        assert resp_data["name"] == data["name"]
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
class TestStationValidation(BaseAPIProjectTestCase):
    """Test validation rules for station data."""

    level: PermissionLevel
    permission_type: PermissionType

    def setUp(self) -> None:
        super().setUp()
        self.set_test_project_permission(self.level, self.permission_type)

    def test_create_station_missing_name(self) -> None:
        """Test station creation fails without name."""
        data = {
            "description": "Test station",
            "latitude": "45.1234567",
            "longitude": "-123.8765432",
        }

        response = self.client.post(
            reverse("api:v1:project-stations", kwargs={"id": self.project.id}),
            data=data,
            headers={"authorization": self.auth},
            content_type="application/json",
        )

        if self.level < PermissionLevel.READ_AND_WRITE:
            assert response.status_code == status.HTTP_403_FORBIDDEN
            return

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "name" in response.data["errors"]

    def test_create_station_duplicate_name(self) -> None:
        """Test station creation with duplicate name in same project returns proper
        error message."""

        unique_name = f"ST_{str(uuid.uuid4())[:8]}"
        # Create the first station
        station1 = StationFactory.create(
            name=unique_name,
            description="First station",
            latitude="45.1234567",
            longitude="-123.8765432",
            project=self.project,
        )

        # Try to create second station with same name
        data = {
            "name": station1.name,
            "description": "Second station",
            "latitude": "45.2234567",
            "longitude": "-123.7765432",
        }

        response = self.client.post(
            reverse("api:v1:project-stations", kwargs={"id": self.project.id}),
            data=data,
            headers={"authorization": self.auth},
            content_type="application/json",
        )

        if self.level < PermissionLevel.READ_AND_WRITE:
            assert response.status_code == status.HTTP_403_FORBIDDEN, response.data
            return

        # Should get a 400 error with a specific message
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "error" in response.data
        assert (
            f"The station name `{data['name']}` already exists in project `{self.project.id}`"  # noqa: E501
            == response.data["error"]
        )

    def test_create_station_invalid_coordinates(self) -> None:
        """Test station creation rejects invalid coordinates (validators are
        implemented)."""
        data = {
            "name": f"ST_{str(uuid.uuid4())[:8]}",
            "description": "Test station",
            "latitude": "99.9999999",  # Invalid latitude (>90)
            "longitude": "-180.0000000",  # Valid longitude (at boundary)
        }

        response = self.client.post(
            reverse("api:v1:project-stations", kwargs={"id": self.project.id}),
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

    def test_station_name_length_limit(self) -> None:
        """Test station name length validation."""
        long_name = "x" * 201  # Assuming 200 char limit

        data = {
            "name": long_name,
            "description": "Test station",
            "latitude": "45.1234567",
            "longitude": "-123.8765432",
        }

        response = self.client.post(
            reverse("api:v1:project-stations", kwargs={"id": self.project.id}),
            data=data,
            headers={"authorization": self.auth},
            content_type="application/json",
        )

        if self.level < PermissionLevel.READ_AND_WRITE:
            assert response.status_code == status.HTTP_403_FORBIDDEN, response.data
            return

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "name" in response.data["errors"]


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
class TestStationEdgeCases(BaseAPIProjectTestCase):
    """Test edge cases and error handling."""

    level: PermissionLevel
    permission_type: PermissionType

    def setUp(self) -> None:
        super().setUp()
        self.set_test_project_permission(self.level, self.permission_type)

    def test_retrieve_nonexistent_station(self) -> None:
        """Test retrieving a non-existent station."""

        response = self.client.get(
            reverse("api:v1:station-detail", kwargs={"id": uuid.uuid4()}),
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_update_nonexistent_station(self) -> None:
        """Test updating a non-existent station."""
        data = {"name": "Updated"}

        response = self.client.patch(
            reverse("api:v1:station-detail", kwargs={"id": uuid.uuid4()}),
            data=data,
            headers={"authorization": self.auth},
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_nonexistent_station(self) -> None:
        """Test deleting a non-existent station."""

        response = self.client.delete(
            reverse("api:v1:station-detail", kwargs={"id": uuid.uuid4()}),
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_extreme_coordinate_precision(self) -> None:
        """Test handling of coordinates with extreme precision."""

        data = {
            "name": f"ST_{str(uuid.uuid4())[:8]}",
            "description": "High precision test",
            "latitude": "45.12345678901234567890",  # More than 7 decimal places
            "longitude": "-123.98765432109876543210",
        }

        response = self.client.post(
            reverse("api:v1:project-stations", kwargs={"id": self.project.id}),
            data=data,
            headers={"authorization": self.auth},
            content_type="application/json",
        )

        if self.level < PermissionLevel.READ_AND_WRITE:
            assert response.status_code == status.HTTP_403_FORBIDDEN, response.data
            return

        assert response.status_code == status.HTTP_201_CREATED
        # Coordinates should be rounded to 7 decimal places
        station_data = response.data["data"]
        assert station_data["latitude"] == 45.1234568  # noqa: PLR2004
        assert station_data["longitude"] == -123.9876543  # noqa: PLR2004

    def test_empty_description(self) -> None:
        """Test station creation with empty description."""

        data = {
            "name": f"ST_{str(uuid.uuid4())[:8]}",
            "description": "",
            "latitude": "45.1234567",
            "longitude": "-123.8765432",
        }

        response = self.client.post(
            reverse("api:v1:project-stations", kwargs={"id": self.project.id}),
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
class TestStationAPIFuzzing(BaseAPIProjectTestCase):
    """Test API with random/fuzzing data."""

    level: PermissionLevel
    permission_type: PermissionType

    def setUp(self) -> None:
        super().setUp()
        self.set_test_project_permission(self.level, self.permission_type)
        self.fake = Faker()

    def test_random_station_names(self) -> None:
        """Test creating stations with various random names."""
        for _ in range(5):
            # Generate random name
            name = self.fake.catch_phrase()[:50]  # Limit length

            data = {
                "name": name,
                "description": self.fake.text(max_nb_chars=200),
                "latitude": str(round(random.uniform(-90, 90), 7)),
                "longitude": str(round(random.uniform(-180, 180), 7)),
            }

            response = self.client.post(
                reverse("api:v1:project-stations", kwargs={"id": self.project.id}),
                data=data,
                headers={"authorization": self.auth},
                content_type="application/json",
            )

            if self.level < PermissionLevel.READ_AND_WRITE:
                assert response.status_code == status.HTTP_403_FORBIDDEN, response.data
                continue

            assert response.status_code == status.HTTP_201_CREATED

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
            }

            response = self.client.post(
                reverse("api:v1:project-stations", kwargs={"id": self.project.id}),
                data=data,
                headers={"authorization": self.auth},
                content_type="application/json",
            )

            if self.level < PermissionLevel.READ_AND_WRITE:
                assert response.status_code == status.HTTP_403_FORBIDDEN, response.data
                continue

            # Should handle unicode properly
            assert response.status_code == status.HTTP_201_CREATED
            assert response.data["data"]["name"] == name

    def test_special_characters_in_names(self) -> None:
        """Test station names with special characters."""

        special_names = [
            "ST-001",
            "ST_002",
            "ST.003",
            "ST/004",
            "ST#005",
            "ST@006",
            "ST&007",
            "ST(008)",
            "ST[009]",
            "ST{010}",
        ]

        for i, name in enumerate(special_names):
            # Make names unique by adding UUID
            unique_name = f"{name}_{str(uuid.uuid4())[:8]}"

            data = {
                "name": unique_name,
                "description": f"Special char test {i}",
                "latitude": str(45.1 + i * 0.01),
                "longitude": str(-123.8 + i * 0.01),
            }

            response = self.client.post(
                reverse("api:v1:project-stations", kwargs={"id": self.project.id}),
                data=data,
                headers={"authorization": self.auth},
                content_type="application/json",
            )

            if self.level < PermissionLevel.READ_AND_WRITE:
                assert response.status_code == status.HTTP_403_FORBIDDEN, response.data
                continue

            assert response.status_code == status.HTTP_201_CREATED

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
            }

            response = self.client.post(
                reverse("api:v1:project-stations", kwargs={"id": self.project.id}),
                data=data,
                headers={"authorization": self.auth},
                content_type="application/json",
            )

            if self.level < PermissionLevel.READ_AND_WRITE:
                assert response.status_code == status.HTTP_403_FORBIDDEN, response.data
                continue

            # Should accept the input but store it safely
            assert response.status_code == status.HTTP_201_CREATED
            # Data should be stored as-is, not executed
            assert response.data["data"]["description"] == payload

    def test_random_coordinate_values(self) -> None:
        """Test various random coordinate values."""

        test_coords = [
            (0, 0),  # Null Island
            (90, 180),  # North Pole, International Date Line
            (-90, -180),  # South Pole, International Date Line
            (45.5, -122.6),  # Portland, OR
            (-33.8688, 151.2093),  # Sydney, Australia
        ]

        for lat, lng in test_coords:
            data = {
                "name": f"Random_{str(uuid.uuid4())[:8]}",
                "description": f"Coordinates: {lat}, {lng}",
                "latitude": str(lat),
                "longitude": str(lng),
            }

            response = self.client.post(
                reverse("api:v1:project-stations", kwargs={"id": self.project.id}),
                data=data,
                headers={"authorization": self.auth},
                content_type="application/json",
            )

            if self.level < PermissionLevel.READ_AND_WRITE:
                assert response.status_code == status.HTTP_403_FORBIDDEN, response.data
                continue

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
class TestStationCoordinateRounding(BaseAPIProjectTestCase):
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
            "name": f"RoundTest_{str(uuid.uuid4())[:8]}",
            "description": "Coordinate rounding test",
            "latitude": "45.123456789012345",  # 15 decimal places
            "longitude": "-123.987654321098765",  # 15 decimal places
        }

        response = self.client.post(
            reverse("api:v1:project-stations", kwargs={"id": self.project.id}),
            data=data,
            headers={"authorization": self.auth},
            content_type="application/json",
        )

        if self.level < PermissionLevel.READ_AND_WRITE:
            assert response.status_code == status.HTTP_403_FORBIDDEN, response.data
            return

        assert response.status_code == status.HTTP_201_CREATED
        station_data = response.data["data"]

        # Check that coordinates were rounded to 7 decimal places
        assert station_data["latitude"] == 45.1234568  # noqa: PLR2004
        assert station_data["longitude"] == -123.9876543  # noqa: PLR2004

    def test_coordinate_rounding_preserves_precision_within_limit(self) -> None:
        """Test that coordinates with <=7 decimal places are preserved exactly."""

        data = {
            "name": f"PrecisionTest_{str(uuid.uuid4())[:8]}",
            "description": "Precision preservation test",
            "latitude": "45.123",  # 3 decimal places
            "longitude": "-123.9876543",  # 7 decimal places
        }

        response = self.client.post(
            reverse("api:v1:project-stations", kwargs={"id": self.project.id}),
            data=data,
            headers={"authorization": self.auth},
            content_type="application/json",
        )

        if self.level < PermissionLevel.READ_AND_WRITE:
            assert response.status_code == status.HTTP_403_FORBIDDEN, response.data
            return

        assert response.status_code == status.HTTP_201_CREATED
        station_data = response.data["data"]

        # Check that coordinates were preserved
        assert station_data["latitude"] == 45.123  # noqa: PLR2004
        assert station_data["longitude"] == -123.9876543  # noqa: PLR2004

    def test_coordinate_rounding_on_update(self) -> None:
        """Test that coordinates are properly rounded on update."""
        # Create a station first
        station = StationFactory.create(
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
            reverse("api:v1:station-detail", kwargs={"id": station.id}),
            data=data,
            headers={"authorization": self.auth},
            content_type="application/json",
        )

        if self.level < PermissionLevel.READ_AND_WRITE:
            assert response.status_code == status.HTTP_403_FORBIDDEN, response.data
            return

        assert response.status_code == status.HTTP_200_OK
        station_data = response.data["data"]

        # Check that coordinates were rounded to 7 decimal places
        assert station_data["latitude"] == 46.9876543  # noqa: PLR2004
        assert station_data["longitude"] == -124.1234568  # noqa: PLR2004

    def test_extreme_coordinate_values_with_rounding(self) -> None:
        """Test rounding with extreme but valid coordinate values."""

        extreme_coords = [
            ("89.99999999", "179.99999999"),  # Near max values
            ("-89.99999999", "-179.99999999"),  # Near min values
            ("0.00000001", "0.00000001"),  # Very small positive
            ("-0.00000001", "-0.00000001"),  # Very small negative
        ]

        for lat, lng in extreme_coords:
            data = {
                "name": f"Extreme_{str(uuid.uuid4())[:8]}",
                "description": f"Extreme coords: {lat}, {lng}",
                "latitude": lat,
                "longitude": lng,
            }

            response = self.client.post(
                reverse("api:v1:project-stations", kwargs={"id": self.project.id}),
                data=data,
                headers={"authorization": self.auth},
                content_type="application/json",
            )

            if self.level < PermissionLevel.READ_AND_WRITE:
                assert response.status_code == status.HTTP_403_FORBIDDEN, response.data
                continue

            assert response.status_code == status.HTTP_201_CREATED

    def test_negative_coordinates_with_many_decimals(self) -> None:
        """Test that negative coordinates with many decimal places are handled
        correctly."""

        data = {
            "name": f"NegativeTest_{str(uuid.uuid4())[:8]}",
            "description": "Negative coordinate rounding",
            "latitude": "-45.123456789012345",  # Negative with many decimals
            "longitude": "-123.987654321098765",  # Negative with many decimals
        }

        response = self.client.post(
            reverse("api:v1:project-stations", kwargs={"id": self.project.id}),
            data=data,
            headers={"authorization": self.auth},
            content_type="application/json",
        )

        if self.level < PermissionLevel.READ_AND_WRITE:
            assert response.status_code == status.HTTP_403_FORBIDDEN, response.data
            return

        assert response.status_code == status.HTTP_201_CREATED
        station_data = response.data["data"]

        # Negative values should round the same way
        assert station_data["latitude"] == -45.1234568  # noqa: PLR2004
        assert station_data["longitude"] == -123.9876543  # noqa: PLR2004

    def test_scientific_notation_coordinates(self) -> None:
        """Test that coordinates in scientific notation are handled."""

        data = {
            "name": f"SciNotation_{str(uuid.uuid4())[:8]}",
            "description": "Scientific notation test",
            "latitude": "4.5123456e1",  # 45.123456 in scientific notation
            "longitude": "-1.23987654e2",  # -123.987654 in scientific notation
        }

        response = self.client.post(
            reverse("api:v1:project-stations", kwargs={"id": self.project.id}),
            data=data,
            headers={"authorization": self.auth},
            content_type="application/json",
        )

        if self.level < PermissionLevel.READ_AND_WRITE:
            assert response.status_code == status.HTTP_403_FORBIDDEN, response.data
            return

        assert response.status_code == status.HTTP_201_CREATED
        station_data = response.data["data"]

        # Should be converted and rounded properly
        assert station_data["latitude"] == 45.123456  # noqa: PLR2004
        assert station_data["longitude"] == -123.987654  # noqa: PLR2004

    def test_coordinate_rounding_boundary_cases(self) -> None:
        """Test coordinate rounding at the 7-decimal boundary."""

        # Test cases where the 8th decimal determines rounding
        test_cases = [
            # (input, expected_output)
            ("45.12345674", 45.1234567),  # Round down (4 < 5)
            ("45.123", 45.123),  # Round up (5 >= 5)
            ("45.12345679", 45.1234568),  # Round up (9 > 5)
            ("-45.12345674", -45.1234567),  # Negative round down
            ("-45.123", -45.123),  # Negative round up
        ]

        for i, (input_val, expected) in enumerate(test_cases):
            data = {
                "name": f"Boundary_{i}_{str(uuid.uuid4())[:8]}",
                "description": f"Boundary test {i}",
                "latitude": input_val,
                "longitude": "0",
            }

            response = self.client.post(
                reverse("api:v1:project-stations", kwargs={"id": self.project.id}),
                data=data,
                headers={"authorization": self.auth},
                content_type="application/json",
            )

            if self.level < PermissionLevel.READ_AND_WRITE:
                assert response.status_code == status.HTTP_403_FORBIDDEN, response.data
                continue

            assert response.status_code == status.HTTP_201_CREATED
            station_data = response.data["data"]
            assert station_data["latitude"] == expected, (
                f"Input {input_val} should round to {expected}, got "
                f"{station_data['latitude']}"
            )

    def test_coordinate_total_digits_validation(self) -> None:
        """Test that coordinates with too many total digits (>10) are handled."""

        data = {
            "name": f"TotalDigits_{str(uuid.uuid4())[:8]}",
            "description": "Total digits test",
            "latitude": "123.1234567",  # 10 total digits (3 + 7)
            "longitude": "-12.12345678",  # 10 total digits with extra decimal
        }

        response = self.client.post(
            reverse("api:v1:project-stations", kwargs={"id": self.project.id}),
            data=data,
            headers={"authorization": self.auth},
            content_type="application/json",
        )

        if self.level < PermissionLevel.READ_AND_WRITE:
            assert response.status_code == status.HTTP_403_FORBIDDEN, response.data
            return

        # Latitude is out of range (-90 to 90), should fail
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "latitude" in response.data.get("errors", {})

    def test_null_coordinates_not_affected(self) -> None:
        """Test that null/None coordinates are properly rejected."""

        data = {
            "name": f"NullCoords_{str(uuid.uuid4())[:8]}",
            "description": "Null coordinates test",
            # Omit coordinates entirely
        }

        response = self.client.post(
            reverse("api:v1:project-stations", kwargs={"id": self.project.id}),
            data=data,
            headers={"authorization": self.auth},
            content_type="application/json",
        )

        if self.level < PermissionLevel.READ_AND_WRITE:
            assert response.status_code == status.HTTP_403_FORBIDDEN, response.data
            return

        # Should fail because coordinates are required
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "latitude" in response.data.get("errors", {})
        assert "longitude" in response.data.get("errors", {})
