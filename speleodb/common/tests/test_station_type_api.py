# -*- coding: utf-8 -*-
"""Tests for SubSurfaceStation type field API endpoints."""

from __future__ import annotations

import uuid

from django.urls import reverse
from parameterized.parameterized import parameterized
from parameterized.parameterized import parameterized_class
from rest_framework import status

from speleodb.api.v1.tests.base_testcase import BaseAPIProjectTestCase
from speleodb.api.v1.tests.base_testcase import PermissionType
from speleodb.api.v1.tests.factories import SubSurfaceStationFactory
from speleodb.common.enums import PermissionLevel
from speleodb.common.enums import SubSurfaceStationType
from speleodb.gis.models import SubSurfaceStation
from speleodb.utils.test_utils import named_product


class TestUnauthenticatedStationTypeAPI(BaseAPIProjectTestCase):
    """Test authentication requirements for station type API endpoints."""

    def test_create_station_with_type_requires_auth(self) -> None:
        """Test that creating a station with type requires authentication."""
        data = {
            "name": "Test Station",
            "description": "Test station",
            "latitude": "45.1234567",
            "longitude": "-123.8765432",
            "type": "sensor",
        }
        response = self.client.post(
            reverse("api:v1:project-stations", kwargs={"id": self.project.id}),
            data=data,
            content_type="application/json",
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
class TestStationTypeCreation(BaseAPIProjectTestCase):
    """Test station creation with different types."""

    level: PermissionLevel
    permission_type: PermissionType

    def setUp(self) -> None:
        super().setUp()
        self.set_test_project_permission(
            level=self.level,
            permission_type=self.permission_type,
        )

    @parameterized.expand(
        [
            ("sensor", SubSurfaceStationType.SENSOR),
            ("biology", SubSurfaceStationType.BIOLOGY),
            ("bone", SubSurfaceStationType.BONE),
            ("artifact", SubSurfaceStationType.ARTIFACT),
            ("geology", SubSurfaceStationType.GEOLOGY),
        ]
    )
    def test_create_station_with_type(
        self, type_value: str, expected: SubSurfaceStationType
    ) -> None:
        """Test creating stations with each valid type."""
        data = {
            "name": f"Station_{type_value}_{str(uuid.uuid4())[:8]}",
            "description": f"Test {type_value} station",
            "latitude": "45.1234567",
            "longitude": "-123.8765432",
            "type": type_value,
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
        assert station_data["type"] == expected

    def test_create_station_without_type_fails(self) -> None:
        """Test that creating a station without type fails."""
        data = {
            "name": f"NoType_{str(uuid.uuid4())[:8]}",
            "description": "Station without type",
            "latitude": "45.1234567",
            "longitude": "-123.8765432",
            # type is not provided
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
        assert "type" in response.data.get("errors", {})

    def test_create_station_with_invalid_type_fails(self) -> None:
        """Test that creating a station with invalid type fails."""
        data = {
            "name": f"InvalidType_{str(uuid.uuid4())[:8]}",
            "description": "Station with invalid type",
            "latitude": "45.1234567",
            "longitude": "-123.8765432",
            "type": "invalid_type",
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
        assert "type" in response.data.get("errors", {})


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
class TestStationTypeModification(BaseAPIProjectTestCase):
    """Test that station type cannot be modified after creation."""

    level: PermissionLevel
    permission_type: PermissionType

    def setUp(self) -> None:
        super().setUp()
        self.set_test_project_permission(
            level=self.level,
            permission_type=self.permission_type,
        )
        # Create a sensor station to test modifications
        self.station = SubSurfaceStationFactory.create(
            project=self.project,
            type=SubSurfaceStationType.SENSOR,
        )

    def test_patch_type_fails(self) -> None:
        """Test that PATCH to change type fails."""
        data = {"type": "bone"}

        response = self.client.patch(
            reverse("api:v1:station-detail", kwargs={"id": self.station.id}),
            data=data,
            headers={"authorization": self.auth},
            content_type="application/json",
        )

        if self.level < PermissionLevel.READ_AND_WRITE:
            assert response.status_code == status.HTTP_403_FORBIDDEN
            return

        # Should fail because type cannot be changed
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "type" in response.data.get("errors", {})

        # Verify station type unchanged
        self.station.refresh_from_db()
        assert self.station.type == SubSurfaceStationType.SENSOR

    def test_put_with_type_fails(self) -> None:
        """Test that PUT with type fails."""
        data = {
            "name": "Updated Name",
            "description": "Updated description",
            "latitude": "45.1234567",
            "longitude": "-123.8765432",
            "type": "artifact",  # Trying to change type
        }

        response = self.client.put(
            reverse("api:v1:station-detail", kwargs={"id": self.station.id}),
            data=data,
            headers={"authorization": self.auth},
            content_type="application/json",
        )

        if self.level < PermissionLevel.READ_AND_WRITE:
            assert response.status_code == status.HTTP_403_FORBIDDEN
            return

        # Should fail because type cannot be changed
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "type" in response.data.get("errors", {})

    def test_patch_other_fields_works(self) -> None:
        """Test that PATCH to change other fields works."""
        data = {
            "name": "Updated Station Name",
            "description": "Updated description",
        }

        response = self.client.patch(
            reverse("api:v1:station-detail", kwargs={"id": self.station.id}),
            data=data,
            headers={"authorization": self.auth},
            content_type="application/json",
        )

        if self.level < PermissionLevel.READ_AND_WRITE:
            assert response.status_code == status.HTTP_403_FORBIDDEN
            return

        assert response.status_code == status.HTTP_200_OK
        station_data = response.data["data"]
        assert station_data["name"] == "Updated Station Name"
        assert station_data["description"] == "Updated description"
        # Type should remain unchanged
        assert station_data["type"] == SubSurfaceStationType.SENSOR

    def test_put_with_same_type_works(self) -> None:
        """Test that PUT with the same type value works (no actual change)."""
        data = {
            "name": "Updated Name",
            "description": "Updated description",
            "latitude": "45.1234567",
            "longitude": "-123.8765432",
            "type": "sensor",  # Same as existing type
        }

        response = self.client.put(
            reverse("api:v1:station-detail", kwargs={"id": self.station.id}),
            data=data,
            headers={"authorization": self.auth},
            content_type="application/json",
        )

        if self.level < PermissionLevel.READ_AND_WRITE:
            assert response.status_code == status.HTTP_403_FORBIDDEN
            return

        # Should succeed because type is not actually changing
        assert response.status_code == status.HTTP_200_OK
        station_data = response.data["data"]
        assert station_data["name"] == "Updated Name"
        assert station_data["type"] == "sensor"


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
class TestStationTypeRetrieval(BaseAPIProjectTestCase):
    """Test that station type is correctly returned in responses."""

    level: PermissionLevel
    permission_type: PermissionType

    def setUp(self) -> None:
        super().setUp()
        self.set_test_project_permission(
            level=self.level,
            permission_type=self.permission_type,
        )

    def test_get_station_includes_type(self) -> None:
        """Test that GET station includes type in response."""
        station = SubSurfaceStationFactory.create(
            project=self.project, type=SubSurfaceStationType.BONE
        )

        response = self.client.get(
            reverse("api:v1:station-detail", kwargs={"id": station.id}),
            headers={"authorization": self.auth},
        )

        if self.level == PermissionLevel.WEB_VIEWER:
            assert response.status_code == status.HTTP_403_FORBIDDEN
            return

        assert response.status_code == status.HTTP_200_OK
        station_data = response.data["data"]
        assert "type" in station_data
        assert station_data["type"] == "bone"

    def test_list_stations_includes_types(self) -> None:
        """Test that listing stations includes types for all."""
        SubSurfaceStationFactory.create(
            project=self.project,
            type=SubSurfaceStationType.SENSOR,
            name="Sensor Station",
        )
        SubSurfaceStationFactory.create(
            project=self.project,
            type=SubSurfaceStationType.BIOLOGY,
            name="Biology Station",
        )
        SubSurfaceStationFactory.create(
            project=self.project, type=SubSurfaceStationType.BONE, name="Bone Station"
        )
        SubSurfaceStationFactory.create(
            project=self.project,
            type=SubSurfaceStationType.ARTIFACT,
            name="Artifact Station",
        )
        SubSurfaceStationFactory.create(
            project=self.project,
            type=SubSurfaceStationType.GEOLOGY,
            name="Geology Station",
        )

        response = self.client.get(
            reverse("api:v1:project-stations", kwargs={"id": self.project.id}),
            headers={"authorization": self.auth},
        )

        if self.level == PermissionLevel.WEB_VIEWER:
            assert response.status_code == status.HTTP_403_FORBIDDEN
            return

        assert response.status_code == status.HTTP_200_OK
        stations_data = response.json()["data"]
        assert len(stations_data) == 5  # noqa: PLR2004

        types = {s["type"] for s in stations_data}
        assert types == {"sensor", "biology", "bone", "artifact", "geology"}


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
class TestStationTypeGeoJSON(BaseAPIProjectTestCase):
    """Test that station type is correctly returned in GeoJSON responses."""

    level: PermissionLevel
    permission_type: PermissionType

    def setUp(self) -> None:
        super().setUp()
        self.set_test_project_permission(
            level=self.level,
            permission_type=self.permission_type,
        )

    def test_geojson_includes_type(self) -> None:
        """Test that GeoJSON endpoint includes type in properties."""
        SubSurfaceStationFactory.create(
            project=self.project, type=SubSurfaceStationType.ARTIFACT, name="Artifact"
        )

        response = self.client.get(
            reverse("api:v1:project-stations-geojson", kwargs={"id": self.project.id}),
            headers={"authorization": self.auth},
        )

        if self.level == PermissionLevel.WEB_VIEWER:
            assert response.status_code == status.HTTP_403_FORBIDDEN
            return

        assert response.status_code == status.HTTP_200_OK
        geojson = response.json()

        assert geojson["type"] == "FeatureCollection"
        assert len(geojson["features"]) == 1

        feature = geojson["features"][0]
        assert feature["type"] == "Feature"
        assert feature["properties"]["type"] == "artifact"
        assert feature["properties"]["station_type"] == "subsurface"

    def test_all_stations_geojson_includes_types(self) -> None:
        """Test that all-stations GeoJSON endpoint includes types."""
        SubSurfaceStationFactory.create(
            project=self.project, type=SubSurfaceStationType.SENSOR, name="Sensor"
        )
        SubSurfaceStationFactory.create(
            project=self.project, type=SubSurfaceStationType.BONE, name="Bone"
        )

        response = self.client.get(
            reverse("api:v1:subsurface-stations-geojson"),
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_200_OK
        geojson = response.json()

        assert geojson["type"] == "FeatureCollection"

        if self.level == PermissionLevel.WEB_VIEWER:
            # WEB_VIEWER can't see stations
            assert len(geojson["features"]) == 0
            return

        assert len(geojson["features"]) == 2  # noqa: PLR2004

        types = {f["properties"]["type"] for f in geojson["features"]}
        assert types == {"sensor", "bone"}


class TestStationTypeValidationEdgeCases(BaseAPIProjectTestCase):
    """Test edge cases for station type validation."""

    def setUp(self) -> None:
        super().setUp()
        self.set_test_project_permission(
            level=PermissionLevel.ADMIN,
            permission_type=PermissionType.USER,
        )

    @parameterized.expand(
        [
            ("SENSOR",),  # Uppercase
            ("Sensor",),  # Mixed case
            ("BIOLOGY",),  # Uppercase
            ("Biology",),  # Mixed case
            ("BONE",),  # Uppercase
            ("Bone",),  # Mixed case
            ("ARTIFACT",),  # Uppercase
            ("Artifact",),  # Mixed case
            ("GEOLOGY",),  # Uppercase
            ("Geology",),  # Mixed case
        ]
    )
    def test_type_case_sensitive(self, type_value: str) -> None:
        """Test that type is case-sensitive (must be lowercase)."""
        data = {
            "name": f"CaseTest_{str(uuid.uuid4())[:8]}",
            "description": "Case sensitivity test",
            "latitude": "45.1234567",
            "longitude": "-123.8765432",
            "type": type_value,
        }

        response = self.client.post(
            reverse("api:v1:project-stations", kwargs={"id": self.project.id}),
            data=data,
            headers={"authorization": self.auth},
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "type" in response.data.get("errors", {})

    @parameterized.expand(
        [
            (" sensor",),  # Leading space
            ("sensor ",),  # Trailing space
            (" sensor ",),  # Both
            ("  bone  ",),  # Multiple spaces
        ]
    )
    def test_type_whitespace_rejected(self, type_value: str) -> None:
        """Test that type with whitespace is rejected."""
        data = {
            "name": f"WhitespaceTest_{str(uuid.uuid4())[:8]}",
            "description": "Whitespace test",
            "latitude": "45.1234567",
            "longitude": "-123.8765432",
            "type": type_value,
        }

        response = self.client.post(
            reverse("api:v1:project-stations", kwargs={"id": self.project.id}),
            data=data,
            headers={"authorization": self.auth},
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "type" in response.data.get("errors", {})

    def test_type_null_rejected(self) -> None:
        """Test that null type is rejected."""
        data = {
            "name": f"NullTest_{str(uuid.uuid4())[:8]}",
            "description": "Null type test",
            "latitude": "45.1234567",
            "longitude": "-123.8765432",
            "type": None,
        }

        response = self.client.post(
            reverse("api:v1:project-stations", kwargs={"id": self.project.id}),
            data=data,
            headers={"authorization": self.auth},
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "type" in response.data.get("errors", {})

    def test_type_empty_string_rejected(self) -> None:
        """Test that empty string type is rejected."""
        data = {
            "name": f"EmptyTest_{str(uuid.uuid4())[:8]}",
            "description": "Empty type test",
            "latitude": "45.1234567",
            "longitude": "-123.8765432",
            "type": "",
        }

        response = self.client.post(
            reverse("api:v1:project-stations", kwargs={"id": self.project.id}),
            data=data,
            headers={"authorization": self.auth},
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "type" in response.data.get("errors", {})

    @parameterized.expand(
        [
            ("research",),  # Similar but invalid
            ("bones",),  # Plural
            ("artifacts",),  # Plural
            ("scientific",),  # Adjective
            ("archeological",),  # Related term
        ]
    )
    def test_similar_but_invalid_types(self, type_value: str) -> None:
        """Test that similar but invalid type values are rejected."""
        data = {
            "name": f"SimilarTest_{str(uuid.uuid4())[:8]}",
            "description": "Similar type test",
            "latitude": "45.1234567",
            "longitude": "-123.8765432",
            "type": type_value,
        }

        response = self.client.post(
            reverse("api:v1:project-stations", kwargs={"id": self.project.id}),
            data=data,
            headers={"authorization": self.auth},
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "type" in response.data.get("errors", {})


class TestStationTypeIntegration(BaseAPIProjectTestCase):
    """Integration tests for station type functionality."""

    def setUp(self) -> None:
        super().setUp()
        self.set_test_project_permission(
            level=PermissionLevel.ADMIN,
            permission_type=PermissionType.USER,
        )

    def test_create_update_delete_with_type(self) -> None:
        """Test full CRUD workflow with station type."""
        # Create a bone station
        create_data = {
            "name": f"IntegrationTest_{str(uuid.uuid4())[:8]}",
            "description": "Integration test station",
            "latitude": "45.1234567",
            "longitude": "-123.8765432",
            "type": "bone",
        }

        create_response = self.client.post(
            reverse("api:v1:project-stations", kwargs={"id": self.project.id}),
            data=create_data,
            headers={"authorization": self.auth},
            content_type="application/json",
        )

        assert create_response.status_code == status.HTTP_201_CREATED
        station_id = create_response.data["data"]["id"]
        assert create_response.data["data"]["type"] == "bone"

        # Read the station
        get_response = self.client.get(
            reverse("api:v1:station-detail", kwargs={"id": station_id}),
            headers={"authorization": self.auth},
        )

        assert get_response.status_code == status.HTTP_200_OK
        assert get_response.data["data"]["type"] == "bone"

        # Update (other fields, not type)
        update_data = {"description": "Updated description"}
        update_response = self.client.patch(
            reverse("api:v1:station-detail", kwargs={"id": station_id}),
            data=update_data,
            headers={"authorization": self.auth},
            content_type="application/json",
        )

        assert update_response.status_code == status.HTTP_200_OK
        assert update_response.data["data"]["description"] == "Updated description"
        assert update_response.data["data"]["type"] == "bone"  # Type unchanged

        # Try to update type (should fail)
        type_update_data = {"type": "artifact"}
        type_update_response = self.client.patch(
            reverse("api:v1:station-detail", kwargs={"id": station_id}),
            data=type_update_data,
            headers={"authorization": self.auth},
            content_type="application/json",
        )

        assert type_update_response.status_code == status.HTTP_400_BAD_REQUEST

        # Delete the station
        delete_response = self.client.delete(
            reverse("api:v1:station-detail", kwargs={"id": station_id}),
            headers={"authorization": self.auth},
        )

        assert delete_response.status_code == status.HTTP_200_OK

        # Verify deletion
        assert not SubSurfaceStation.objects.filter(id=station_id).exists()

    def test_multiple_stations_same_type_same_project(self) -> None:
        """Test creating multiple stations with same type in same project."""
        for i in range(3):
            data = {
                "name": f"SameType_{i}_{str(uuid.uuid4())[:8]}",
                "description": f"Same type station {i}",
                "latitude": f"45.123456{i}",
                "longitude": f"-123.876543{i}",
                "type": "artifact",
            }

            response = self.client.post(
                reverse("api:v1:project-stations", kwargs={"id": self.project.id}),
                data=data,
                headers={"authorization": self.auth},
                content_type="application/json",
            )

            assert response.status_code == status.HTTP_201_CREATED
            assert response.data["data"]["type"] == "artifact"

        # Verify all 3 stations exist
        stations = SubSurfaceStation.objects.filter(
            project=self.project, type="artifact"
        )
        assert stations.count() == 3  # noqa: PLR2004
