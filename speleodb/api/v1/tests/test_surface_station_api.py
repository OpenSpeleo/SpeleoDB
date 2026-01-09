# -*- coding: utf-8 -*-

from __future__ import annotations

import uuid
from enum import Enum
from typing import Any

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from speleodb.api.v1.tests.factories import SurfaceMonitoringNetworkFactory
from speleodb.api.v1.tests.factories import (
    SurfaceMonitoringNetworkUserPermissionFactory,
)
from speleodb.api.v1.tests.factories import SurfaceStationFactory
from speleodb.api.v1.tests.factories import TokenFactory
from speleodb.common.enums import PermissionLevel
from speleodb.gis.models import Station
from speleodb.gis.models import SurfaceMonitoringNetwork
from speleodb.gis.models import SurfaceStation
from speleodb.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


class PermissionType(Enum):
    USER = "user"


class TestUnauthenticatedSurfaceStationAPIAuthentication:
    """Test authentication requirements for surface station API endpoints."""

    @pytest.fixture
    def api_client(self) -> APIClient:
        return APIClient()

    @pytest.fixture
    def network(self) -> SurfaceMonitoringNetwork:
        return SurfaceMonitoringNetworkFactory.create()

    @pytest.fixture
    def station(self, network: SurfaceMonitoringNetwork) -> SurfaceStation:
        return SurfaceStationFactory.create(network=network)

    def test_station_list_requires_authentication(
        self, api_client: APIClient, network: SurfaceMonitoringNetwork
    ) -> None:
        """Test that station list endpoint requires authentication."""
        response = api_client.get(
            reverse("api:v1:network-stations", kwargs={"network_id": network.id}),
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_station_detail_requires_authentication(
        self, api_client: APIClient, station: SurfaceStation
    ) -> None:
        """Test that station detail endpoint requires authentication."""
        response = api_client.get(
            reverse("api:v1:station-detail", kwargs={"id": station.id})
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_station_create_requires_authentication(
        self, api_client: APIClient, network: SurfaceMonitoringNetwork
    ) -> None:
        """Test that station create endpoint requires authentication."""
        data = {
            "name": "ST001",
            "description": "Test station",
            "latitude": "45.1234567",
            "longitude": "-123.8765432",
        }
        response = api_client.post(
            reverse("api:v1:network-stations", kwargs={"network_id": network.id}),
            data=data,
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_station_update_requires_authentication(
        self, api_client: APIClient, station: SurfaceStation
    ) -> None:
        """Test that station update endpoint requires authentication."""
        data = {"name": "ST002", "description": "Updated description"}
        response = api_client.patch(
            reverse("api:v1:station-detail", kwargs={"id": station.id}),
            data=data,
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_station_delete_requires_authentication(
        self, api_client: APIClient, station: SurfaceStation
    ) -> None:
        """Test that station delete endpoint requires authentication."""
        response = api_client.delete(
            reverse("api:v1:station-detail", kwargs={"id": station.id})
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_surface_stations_list_requires_authentication(
        self, api_client: APIClient
    ) -> None:
        """Test that all surface stations endpoint requires authentication."""
        response = api_client.get(reverse("api:v1:surface-stations"))
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_surface_stations_geojson_requires_authentication(
        self, api_client: APIClient
    ) -> None:
        """Test that surface stations GeoJSON endpoint requires authentication."""
        response = api_client.get(reverse("api:v1:surface-stations-geojson"))
        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestSurfaceStationAPIPermissions:
    """Test permission requirements for surface station API endpoints."""

    @pytest.fixture
    def api_client(self) -> APIClient:
        return APIClient()

    @pytest.fixture(
        params=[
            PermissionLevel.ADMIN,
            PermissionLevel.READ_AND_WRITE,
            PermissionLevel.READ_ONLY,
        ]
    )
    def permission_level(self, request: pytest.FixtureRequest) -> PermissionLevel:
        return request.param  # type: ignore[no-any-return]

    @pytest.fixture
    def setup(self, permission_level: PermissionLevel) -> dict[str, Any]:
        """Setup user, network, and permissions."""
        user = UserFactory.create()
        token = TokenFactory.create(user=user)
        network = SurfaceMonitoringNetworkFactory.create()
        SurfaceMonitoringNetworkUserPermissionFactory.create(
            user=user, network=network, level=permission_level
        )
        station = SurfaceStationFactory.create(network=network)
        return {
            "user": user,
            "token": token,
            "network": network,
            "station": station,
            "level": permission_level,
            "auth": f"Token {token.key}",
        }

    def test_station_list_permissions(
        self,
        api_client: APIClient,
        setup: dict[str, Any],
    ) -> None:
        """Test station list endpoint with different permission levels."""
        response = api_client.get(
            reverse(
                "api:v1:network-stations", kwargs={"network_id": setup["network"].id}
            ),
            headers={"authorization": setup["auth"]},
        )
        # All permission levels can read
        assert response.status_code == status.HTTP_200_OK

    def test_station_detail_permissions(
        self,
        api_client: APIClient,
        setup: dict[str, Any],
    ) -> None:
        """Test station detail endpoint with different permission levels."""
        response = api_client.get(
            reverse("api:v1:station-detail", kwargs={"id": setup["station"].id}),
            headers={"authorization": setup["auth"]},
        )
        # All permission levels can read
        assert response.status_code == status.HTTP_200_OK

    def test_station_create_permissions(
        self,
        api_client: APIClient,
        setup: dict[str, Any],
    ) -> None:
        """Test station create endpoint with different permission levels."""
        data = {
            "name": f"ST{setup['level']:03d}_{str(uuid.uuid4())[:8]}",
            "description": "Test station",
            "latitude": "45.1234567",
            "longitude": "-123.8765432",
        }
        response = api_client.post(
            reverse(
                "api:v1:network-stations", kwargs={"network_id": setup["network"].id}
            ),
            data=data,
            headers={"authorization": setup["auth"]},
            content_type="application/json",
        )
        expected = (
            status.HTTP_201_CREATED
            if setup["level"] >= PermissionLevel.READ_AND_WRITE
            else status.HTTP_403_FORBIDDEN
        )
        assert response.status_code == expected

    def test_station_update_permissions(
        self,
        api_client: APIClient,
        setup: dict[str, Any],
    ) -> None:
        """Test station update endpoint with different permission levels."""
        data = {"description": "Updated description"}
        response = api_client.patch(
            reverse("api:v1:station-detail", kwargs={"id": setup["station"].id}),
            data=data,
            headers={"authorization": setup["auth"]},
            content_type="application/json",
        )
        expected = (
            status.HTTP_200_OK
            if setup["level"] >= PermissionLevel.READ_AND_WRITE
            else status.HTTP_403_FORBIDDEN
        )
        assert response.status_code == expected

    def test_station_delete_permissions(
        self,
        api_client: APIClient,
        setup: dict[str, Any],
    ) -> None:
        """Test station delete endpoint with different permission levels."""
        response = api_client.delete(
            reverse("api:v1:station-detail", kwargs={"id": setup["station"].id}),
            headers={"authorization": setup["auth"]},
        )
        expected = (
            status.HTTP_200_OK
            if setup["level"] == PermissionLevel.ADMIN
            else status.HTTP_403_FORBIDDEN
        )
        assert response.status_code == expected


class TestSurfaceStationCRUDOperations:
    """Test CRUD operations for surface stations."""

    @pytest.fixture
    def api_client(self) -> APIClient:
        return APIClient()

    @pytest.fixture
    def setup_with_admin(self) -> dict[str, Any]:
        """Setup user with ADMIN permission."""
        user = UserFactory.create()
        token = TokenFactory.create(user=user)
        network = SurfaceMonitoringNetworkFactory.create()
        SurfaceMonitoringNetworkUserPermissionFactory.create(
            user=user, network=network, level=PermissionLevel.ADMIN
        )
        return {
            "user": user,
            "token": token,
            "network": network,
            "auth": f"Token {token.key}",
        }

    def test_create_station_success(
        self,
        api_client: APIClient,
        setup_with_admin: dict[str, Any],
    ) -> None:
        """Test successful station creation."""
        data = {
            "name": "Surface Station 001",
            "description": "Surface monitoring point",
            "latitude": "45.14908328409823490234567",
            "longitude": "-123.876032940239093049235432",
        }
        response = api_client.post(
            reverse(
                "api:v1:network-stations",
                kwargs={"network_id": setup_with_admin["network"].id},
            ),
            data=data,
            headers={"authorization": setup_with_admin["auth"]},
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        station_data = response.data["data"]
        assert station_data["name"] == "Surface Station 001"
        assert station_data["description"] == "Surface monitoring point"
        # Coordinates should be rounded to 7 decimal places
        assert station_data["latitude"] == 45.1490833  # noqa: PLR2004
        assert station_data["longitude"] == -123.8760329  # noqa: PLR2004

    def test_list_network_stations(
        self,
        api_client: APIClient,
        setup_with_admin: dict[str, Any],
    ) -> None:
        """Test successful station listing for a network."""
        # Create test stations
        stations = [
            SurfaceStationFactory.create(network=setup_with_admin["network"])
            for _ in range(3)
        ]
        response = api_client.get(
            reverse(
                "api:v1:network-stations",
                kwargs={"network_id": setup_with_admin["network"].id},
            ),
            headers={"authorization": setup_with_admin["auth"]},
        )
        assert response.status_code == status.HTTP_200_OK
        stations_data = response.json()["data"]
        assert len(stations_data) == 3  # noqa: PLR2004
        station_ids = {str(station.id) for station in stations}
        response_ids = {station["id"] for station in stations_data}
        assert station_ids == response_ids

    def test_list_all_user_surface_stations(
        self,
        api_client: APIClient,
        setup_with_admin: dict[str, Any],
    ) -> None:
        """Test listing all surface stations user has access to."""
        # Create stations in user's network
        for _ in range(2):
            SurfaceStationFactory.create(network=setup_with_admin["network"])

        # Create another network with stations that user doesn't have access to
        other_network = SurfaceMonitoringNetworkFactory.create()
        SurfaceStationFactory.create(network=other_network)

        response = api_client.get(
            reverse("api:v1:surface-stations"),
            headers={"authorization": setup_with_admin["auth"]},
        )
        assert response.status_code == status.HTTP_200_OK
        stations_data = response.json()["data"]
        # User should only see their 2 stations, not the one in other network
        assert len(stations_data) == 2  # noqa: PLR2004

    def test_retrieve_station_success(
        self,
        api_client: APIClient,
        setup_with_admin: dict[str, Any],
    ) -> None:
        """Test successful station retrieval."""
        station = SurfaceStationFactory.create(network=setup_with_admin["network"])
        response = api_client.get(
            reverse("api:v1:station-detail", kwargs={"id": station.id}),
            headers={"authorization": setup_with_admin["auth"]},
        )
        assert response.status_code == status.HTTP_200_OK
        station_data = response.data["data"]
        assert station_data["id"] == str(station.id)
        assert station_data["name"] == station.name
        assert "resources" in station_data

    def test_delete_station_success(
        self,
        api_client: APIClient,
        setup_with_admin: dict[str, Any],
    ) -> None:
        """Test successful station deletion."""
        station = SurfaceStationFactory.create(network=setup_with_admin["network"])
        station_id = str(station.id)
        response = api_client.delete(
            reverse("api:v1:station-detail", kwargs={"id": station.id}),
            headers={"authorization": setup_with_admin["auth"]},
        )
        assert response.status_code == status.HTTP_200_OK
        assert station_id == response.data["data"]["id"]
        assert not Station.objects.filter(id=station.id).exists()

    def test_update_station(
        self,
        api_client: APIClient,
        setup_with_admin: dict[str, Any],
    ) -> None:
        """Test updating a station."""
        station = SurfaceStationFactory.create(
            network=setup_with_admin["network"], name="OldName"
        )
        data = {
            "name": "NewName",
            "description": "Updated description",
        }
        response = api_client.patch(
            reverse("api:v1:station-detail", kwargs={"id": station.id}),
            data=data,
            headers={"authorization": setup_with_admin["auth"]},
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_200_OK
        resp_data = response.data["data"]
        assert resp_data["name"] == "NewName"
        assert resp_data["description"] == "Updated description"


class TestSurfaceStationValidation:
    """Test validation rules for surface station data."""

    @pytest.fixture
    def api_client(self) -> APIClient:
        return APIClient()

    @pytest.fixture
    def setup_with_write(self) -> dict[str, Any]:
        """Setup user with READ_AND_WRITE permission."""
        user = UserFactory.create()
        token = TokenFactory.create(user=user)
        network = SurfaceMonitoringNetworkFactory.create()
        SurfaceMonitoringNetworkUserPermissionFactory.create(
            user=user, network=network, level=PermissionLevel.READ_AND_WRITE
        )
        return {
            "user": user,
            "token": token,
            "network": network,
            "auth": f"Token {token.key}",
        }

    def test_create_station_missing_name(
        self,
        api_client: APIClient,
        setup_with_write: dict[str, Any],
    ) -> None:
        """Test station creation fails without name."""
        data = {
            "description": "Test station",
            "latitude": "45.1234567",
            "longitude": "-123.8765432",
        }
        response = api_client.post(
            reverse(
                "api:v1:network-stations",
                kwargs={"network_id": setup_with_write["network"].id},
            ),
            data=data,
            headers={"authorization": setup_with_write["auth"]},
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "name" in response.data["errors"]

    def test_create_station_missing_coordinates(
        self,
        api_client: APIClient,
        setup_with_write: dict[str, Any],
    ) -> None:
        """Test station creation fails without coordinates."""
        data = {
            "name": "Test Station",
            "description": "Test station",
        }
        response = api_client.post(
            reverse(
                "api:v1:network-stations",
                kwargs={"network_id": setup_with_write["network"].id},
            ),
            data=data,
            headers={"authorization": setup_with_write["auth"]},
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "latitude" in response.data["errors"]
        assert "longitude" in response.data["errors"]

    def test_create_station_invalid_latitude(
        self,
        api_client: APIClient,
        setup_with_write: dict[str, Any],
    ) -> None:
        """Test station creation fails with invalid latitude."""
        data = {
            "name": f"ST_{str(uuid.uuid4())[:8]}",
            "description": "Test station",
            "latitude": "99.9999999",  # Invalid - must be -90 to 90
            "longitude": "-123.8765432",
        }
        response = api_client.post(
            reverse(
                "api:v1:network-stations",
                kwargs={"network_id": setup_with_write["network"].id},
            ),
            data=data,
            headers={"authorization": setup_with_write["auth"]},
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "latitude" in response.data.get("errors", {})

    def test_create_station_name_too_long(
        self,
        api_client: APIClient,
        setup_with_write: dict[str, Any],
    ) -> None:
        """Test station creation fails with name too long."""
        data = {
            "name": "x" * 201,  # Assuming 100 char limit
            "description": "Test station",
            "latitude": "45.1234567",
            "longitude": "-123.8765432",
        }
        response = api_client.post(
            reverse(
                "api:v1:network-stations",
                kwargs={"network_id": setup_with_write["network"].id},
            ),
            data=data,
            headers={"authorization": setup_with_write["auth"]},
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "name" in response.data["errors"]


class TestSurfaceStationEdgeCases:
    """Test edge cases and error handling for surface stations."""

    @pytest.fixture
    def api_client(self) -> APIClient:
        return APIClient()

    @pytest.fixture
    def setup_with_admin(self) -> dict[str, Any]:
        """Setup user with ADMIN permission."""
        user = UserFactory.create()
        token = TokenFactory.create(user=user)
        network = SurfaceMonitoringNetworkFactory.create()
        SurfaceMonitoringNetworkUserPermissionFactory.create(
            user=user, network=network, level=PermissionLevel.ADMIN
        )
        return {
            "user": user,
            "token": token,
            "network": network,
            "auth": f"Token {token.key}",
        }

    def test_retrieve_nonexistent_station(
        self,
        api_client: APIClient,
        setup_with_admin: dict[str, Any],
    ) -> None:
        """Test retrieving a non-existent station."""
        response = api_client.get(
            reverse("api:v1:station-detail", kwargs={"id": uuid.uuid4()}),
            headers={"authorization": setup_with_admin["auth"]},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_update_nonexistent_station(
        self,
        api_client: APIClient,
        setup_with_admin: dict[str, Any],
    ) -> None:
        """Test updating a non-existent station."""
        data = {"name": "Updated"}
        response = api_client.patch(
            reverse("api:v1:station-detail", kwargs={"id": uuid.uuid4()}),
            data=data,
            headers={"authorization": setup_with_admin["auth"]},
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_nonexistent_station(
        self,
        api_client: APIClient,
        setup_with_admin: dict[str, Any],
    ) -> None:
        """Test deleting a non-existent station."""
        response = api_client.delete(
            reverse("api:v1:station-detail", kwargs={"id": uuid.uuid4()}),
            headers={"authorization": setup_with_admin["auth"]},
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_empty_description_allowed(
        self,
        api_client: APIClient,
        setup_with_admin: dict[str, Any],
    ) -> None:
        """Test station creation with empty description."""
        data = {
            "name": f"ST_{str(uuid.uuid4())[:8]}",
            "description": "",
            "latitude": "45.1234567",
            "longitude": "-123.8765432",
        }
        response = api_client.post(
            reverse(
                "api:v1:network-stations",
                kwargs={"network_id": setup_with_admin["network"].id},
            ),
            data=data,
            headers={"authorization": setup_with_admin["auth"]},
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_201_CREATED


class TestSurfaceStationCoordinateRounding:
    """Test coordinate rounding functionality for surface stations."""

    @pytest.fixture
    def api_client(self) -> APIClient:
        return APIClient()

    @pytest.fixture
    def setup_with_write(self) -> dict[str, Any]:
        """Setup user with WRITE permission."""
        user = UserFactory.create()
        token = TokenFactory.create(user=user)
        network = SurfaceMonitoringNetworkFactory.create()
        SurfaceMonitoringNetworkUserPermissionFactory.create(
            user=user, network=network, level=PermissionLevel.READ_AND_WRITE
        )
        return {
            "user": user,
            "token": token,
            "network": network,
            "auth": f"Token {token.key}",
        }

    def test_coordinate_rounding_on_create(
        self,
        api_client: APIClient,
        setup_with_write: dict[str, Any],
    ) -> None:
        """Test that coordinates are properly rounded to 7 decimal places."""
        data = {
            "name": f"RoundTest_{str(uuid.uuid4())[:8]}",
            "description": "Coordinate rounding test",
            "latitude": "45.123456789012345",
            "longitude": "-123.987654321098765",
        }
        response = api_client.post(
            reverse(
                "api:v1:network-stations",
                kwargs={"network_id": setup_with_write["network"].id},
            ),
            data=data,
            headers={"authorization": setup_with_write["auth"]},
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        station_data = response.data["data"]
        assert station_data["latitude"] == 45.1234568  # noqa: PLR2004
        assert station_data["longitude"] == -123.9876543  # noqa: PLR2004

    def test_coordinate_rounding_on_update(
        self,
        api_client: APIClient,
        setup_with_write: dict[str, Any],
    ) -> None:
        """Test that coordinates are properly rounded on update."""
        station = SurfaceStationFactory.create(
            network=setup_with_write["network"],
            latitude=45.1,
            longitude=-123.9,
        )
        data = {
            "latitude": "46.987654321098765",
            "longitude": "-124.123456789012345",
        }
        response = api_client.patch(
            reverse("api:v1:station-detail", kwargs={"id": station.id}),
            data=data,
            headers={"authorization": setup_with_write["auth"]},
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_200_OK
        station_data = response.data["data"]
        assert station_data["latitude"] == 46.9876543  # noqa: PLR2004
        assert station_data["longitude"] == -124.1234568  # noqa: PLR2004


class TestSurfaceStationGeoJSONEndpoint:
    """Test GeoJSON endpoints for surface stations."""

    @pytest.fixture
    def api_client(self) -> APIClient:
        return APIClient()

    @pytest.fixture
    def setup_with_read(self) -> dict[str, Any]:
        """Setup user with READ permission."""
        user = UserFactory.create()
        token = TokenFactory.create(user=user)
        network = SurfaceMonitoringNetworkFactory.create()
        SurfaceMonitoringNetworkUserPermissionFactory.create(
            user=user, network=network, level=PermissionLevel.READ_ONLY
        )
        return {
            "user": user,
            "token": token,
            "network": network,
            "auth": f"Token {token.key}",
        }

    def test_network_stations_geojson(
        self,
        api_client: APIClient,
        setup_with_read: dict[str, Any],
    ) -> None:
        """Test GeoJSON response for network stations."""
        station = SurfaceStationFactory.create(
            network=setup_with_read["network"],
            latitude=45.123,
            longitude=-123.456,
        )
        response = api_client.get(
            reverse(
                "api:v1:network-stations-geojson",
                kwargs={"network_id": setup_with_read["network"].id},
            ),
            headers={"authorization": setup_with_read["auth"]},
        )
        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert data["type"] == "FeatureCollection"
        assert len(data["features"]) == 1

        feature = data["features"][0]
        assert feature["type"] == "Feature"
        assert feature["geometry"]["type"] == "Point"
        assert feature["geometry"]["coordinates"] == [
            float(station.longitude),
            float(station.latitude),
        ]
        assert feature["id"] == str(station.id)
        assert feature["properties"]["station_type"] == "surface"
        assert feature["properties"]["network"] == str(setup_with_read["network"].id)
        assert feature["properties"]["project"] is None

    def test_all_surface_stations_geojson(
        self,
        api_client: APIClient,
        setup_with_read: dict[str, Any],
    ) -> None:
        """Test GeoJSON response for all user's surface stations."""
        # Create 2 stations in user's network
        SurfaceStationFactory.create(network=setup_with_read["network"])
        SurfaceStationFactory.create(network=setup_with_read["network"])

        # Create station in another network (user shouldn't see this)
        other_network = SurfaceMonitoringNetworkFactory.create()
        SurfaceStationFactory.create(network=other_network)

        response = api_client.get(
            reverse("api:v1:surface-stations-geojson"),
            headers={"authorization": setup_with_read["auth"]},
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["type"] == "FeatureCollection"
        # User should only see their 2 stations
        assert len(data["features"]) == 2  # noqa: PLR2004


class TestSurfaceStationFuzzing:
    """Test API with random/fuzzing data for surface stations."""

    @pytest.fixture
    def api_client(self) -> APIClient:
        return APIClient()

    @pytest.fixture
    def setup_with_write(self) -> dict[str, Any]:
        """Setup user with WRITE permission."""
        user = UserFactory.create()
        token = TokenFactory.create(user=user)
        network = SurfaceMonitoringNetworkFactory.create()
        SurfaceMonitoringNetworkUserPermissionFactory.create(
            user=user, network=network, level=PermissionLevel.READ_AND_WRITE
        )
        return {
            "user": user,
            "token": token,
            "network": network,
            "auth": f"Token {token.key}",
        }

    def test_unicode_station_names(
        self,
        api_client: APIClient,
        setup_with_write: dict[str, Any],
    ) -> None:
        """Test creating stations with unicode characters."""
        unicode_names = [
            "Station αβγ",
            "駅 🚉",
            "Станция №1",
        ]
        for name in unicode_names:
            data = {
                "name": name,
                "description": "Unicode test",
                "latitude": "45.1234567",
                "longitude": "-123.8765432",
            }
            response = api_client.post(
                reverse(
                    "api:v1:network-stations",
                    kwargs={"network_id": setup_with_write["network"].id},
                ),
                data=data,
                headers={"authorization": setup_with_write["auth"]},
                content_type="application/json",
            )
            assert response.status_code == status.HTTP_201_CREATED
            assert response.data["data"]["name"] == name

    def test_special_characters_in_names(
        self,
        api_client: APIClient,
        setup_with_write: dict[str, Any],
    ) -> None:
        """Test station names with special characters."""
        special_names = [
            "ST-001",
            "ST_002",
            "ST.003",
            "ST/004",
        ]
        for i, name in enumerate(special_names):
            unique_name = f"{name}_{str(uuid.uuid4())[:8]}"
            data = {
                "name": unique_name,
                "description": f"Special char test {i}",
                "latitude": str(45.1 + i * 0.01),
                "longitude": str(-123.8 + i * 0.01),
            }
            response = api_client.post(
                reverse(
                    "api:v1:network-stations",
                    kwargs={"network_id": setup_with_write["network"].id},
                ),
                data=data,
                headers={"authorization": setup_with_write["auth"]},
                content_type="application/json",
            )
            assert response.status_code == status.HTTP_201_CREATED

    def test_extreme_coordinate_values(
        self,
        api_client: APIClient,
        setup_with_write: dict[str, Any],
    ) -> None:
        """Test various coordinate values including edge cases."""
        test_coords = [
            (0, 0),  # Null Island
            (90, 180),  # North Pole, International Date Line
            (-90, -180),  # South Pole, International Date Line
            (45.5, -122.6),  # Portland, OR
        ]
        for lat, lng in test_coords:
            data = {
                "name": f"Coord_{str(uuid.uuid4())[:8]}",
                "description": f"Coordinates: {lat}, {lng}",
                "latitude": str(lat),
                "longitude": str(lng),
            }
            response = api_client.post(
                reverse(
                    "api:v1:network-stations",
                    kwargs={"network_id": setup_with_write["network"].id},
                ),
                data=data,
                headers={"authorization": setup_with_write["auth"]},
                content_type="application/json",
            )
            assert response.status_code == status.HTTP_201_CREATED


class TestSurfaceStationNoAccessToOtherNetworks:
    """Test that users cannot access stations in networks they don't have access to."""

    @pytest.fixture
    def api_client(self) -> APIClient:
        return APIClient()

    @pytest.fixture
    def setup(self) -> dict[str, Any]:
        """Setup two users with different network access."""
        user1 = UserFactory.create()
        token1 = TokenFactory.create(user=user1)
        network1 = SurfaceMonitoringNetworkFactory.create()
        SurfaceMonitoringNetworkUserPermissionFactory.create(
            user=user1, network=network1, level=PermissionLevel.ADMIN
        )
        station1 = SurfaceStationFactory.create(network=network1)

        user2 = UserFactory.create()
        token2 = TokenFactory.create(user=user2)
        network2 = SurfaceMonitoringNetworkFactory.create()
        SurfaceMonitoringNetworkUserPermissionFactory.create(
            user=user2, network=network2, level=PermissionLevel.ADMIN
        )
        station2 = SurfaceStationFactory.create(network=network2)

        return {
            "user1": user1,
            "auth1": f"Token {token1.key}",
            "network1": network1,
            "station1": station1,
            "user2": user2,
            "auth2": f"Token {token2.key}",
            "network2": network2,
            "station2": station2,
        }

    def test_user_cannot_read_other_network_stations(
        self,
        api_client: APIClient,
        setup: dict[str, Any],
    ) -> None:
        """Test user cannot read stations from a network they don't have access to."""
        # User1 trying to access user2's network stations
        response = api_client.get(
            reverse(
                "api:v1:network-stations",
                kwargs={"network_id": setup["network2"].id},
            ),
            headers={"authorization": setup["auth1"]},
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_user_cannot_create_in_other_network(
        self,
        api_client: APIClient,
        setup: dict[str, Any],
    ) -> None:
        """Test user cannot create stations in a network they don't have access to."""
        data = {
            "name": "Unauthorized Station",
            "latitude": "45.0",
            "longitude": "-123.0",
        }
        response = api_client.post(
            reverse(
                "api:v1:network-stations",
                kwargs={"network_id": setup["network2"].id},
            ),
            data=data,
            headers={"authorization": setup["auth1"]},
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_user_cannot_access_other_network_station_detail(
        self,
        api_client: APIClient,
        setup: dict[str, Any],
    ) -> None:
        """Test user cannot access station details from another network."""
        response = api_client.get(
            reverse("api:v1:station-detail", kwargs={"id": setup["station2"].id}),
            headers={"authorization": setup["auth1"]},
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_user_cannot_delete_other_network_station(
        self,
        api_client: APIClient,
        setup: dict[str, Any],
    ) -> None:
        """Test user cannot delete station from another network."""
        response = api_client.delete(
            reverse("api:v1:station-detail", kwargs={"id": setup["station2"].id}),
            headers={"authorization": setup["auth1"]},
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN
