# -*- coding: utf-8 -*-

"""
Integration tests for the map viewer functionality.
Tests all API endpoints and operations used by the frontend map viewer.
"""

import json
from decimal import Decimal
from typing import Any

from django.test import TransactionTestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token

from speleodb.api.v1.tests.base_testcase import BaseAPIProjectTestCase
from speleodb.api.v1.tests.factories import ProjectFactory
from speleodb.api.v1.tests.factories import StationFactory
from speleodb.api.v1.tests.factories import StationResourceFactory
from speleodb.api.v1.tests.factories import UserFactory
from speleodb.surveys.models import PermissionLevel
from speleodb.surveys.models import Station
from speleodb.surveys.models import StationResource
from speleodb.surveys.models import UserPermission


class TestMapViewerIntegration(BaseAPIProjectTestCase):
    """Test all functionality used by the map viewer frontend."""

    def setUp(self) -> None:
        super().setUp()
        self.set_test_project_permission(PermissionLevel.READ_AND_WRITE)
        self.auth = self.header_prefix + self.token.key

    def test_station_creation_workflow(self) -> None:
        """Test the complete station creation workflow as used by the frontend."""
        # Test data for a station creation via right-click context menu
        station_data = {
            "name": "Test Junction Station",
            "description": "Created via right-click context menu with magnetic snap",
            "latitude": "20.194500",
            "longitude": "-87.497500",
            "project_id": str(self.project.id),
        }

        # Create station via API (as frontend would do)
        response = self.client.post(
            reverse("api:v1:station-list-create"),
            data=json.dumps(station_data),
            content_type="application/json",
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_201_CREATED
        station_data_response = response.data["data"]["station"]

        # Verify station data matches frontend expectations
        assert station_data_response["name"] == station_data["name"]
        assert station_data_response["description"] == station_data["description"]
        assert Decimal(station_data_response["latitude"]) == Decimal(
            station_data["latitude"]
        )
        assert Decimal(station_data_response["longitude"]) == Decimal(
            station_data["longitude"]
        )
        assert station_data_response["resource_count"] == 0
        assert "id" in station_data_response
        assert "created_by_email" in station_data_response
        assert "creation_date" in station_data_response

        station_id = station_data_response["id"]

        # Test loading stations for map display (as frontend does after creation)
        response = self.client.get(
            reverse("api:v1:stations-map"),
            {"project_id": str(self.project.id)},
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_200_OK
        geojson_data = response.data["data"]

        # Verify GeoJSON format for map display
        assert geojson_data["type"] == "FeatureCollection"
        assert len(geojson_data["features"]) == 1

        feature = geojson_data["features"][0]
        assert feature["type"] == "Feature"
        assert feature["geometry"]["type"] == "Point"
        assert feature["geometry"]["coordinates"] == [
            float(station_data["longitude"]),
            float(station_data["latitude"]),
        ]
        assert feature["properties"]["id"] == station_id
        assert feature["properties"]["name"] == station_data["name"]
        assert feature["properties"]["resource_count"] == 0

    def test_station_position_update_workflow(self) -> None:
        """Test updating station position via drag & drop (as frontend does)."""
        # Create a station
        station = StationFactory.create(
            project=self.project,
            latitude=Decimal("20.194500"),
            longitude=Decimal("-87.497500"),
        )

        # New position after drag & drop
        new_latitude = "20.195000"
        new_longitude = "-87.498000"

        # Update position (as frontend does on drag end) - MUST use JSON
        response = self.client.patch(
            reverse("api:v1:station-detail", kwargs={"id": station.id}),
            data=json.dumps({"latitude": new_latitude, "longitude": new_longitude}),
            content_type="application/json",
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_200_OK
        updated_station = response.data["data"]["station"]

        # Verify updated coordinates
        assert Decimal(updated_station["latitude"]) == Decimal(new_latitude)
        assert Decimal(updated_station["longitude"]) == Decimal(new_longitude)

        # Verify database was updated
        station.refresh_from_db()
        assert station.latitude == Decimal(new_latitude)
        assert station.longitude == Decimal(new_longitude)

    def test_station_with_resources_workflow(self) -> None:
        """Test the complete workflow of a station with multiple resources."""
        # Create station with demo resources (as fixtures would create)
        station = StationFactory.create(project=self.project)
        resources = StationResourceFactory.create_demo_resources(station)

        # Test detailed station retrieval (as modal would load)
        response = self.client.get(
            reverse("api:v1:station-detail", kwargs={"id": station.id}),
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_200_OK
        station_data = response.data["data"]["station"]

        # Verify station includes all resources
        assert station_data["resource_count"] == len(resources)
        assert len(station_data["resources"]) == len(resources)

        # Test each resource type
        resource_types = {r["resource_type"] for r in station_data["resources"]}
        expected_types = {"photo", "note", "sketch", "video"}
        assert resource_types == expected_types

        # Test map display includes resource count
        response = self.client.get(
            reverse("api:v1:stations-map"),
            {"project_id": str(self.project.id)},
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_200_OK
        feature = response.data["data"]["features"][0]
        assert feature["properties"]["resource_count"] == len(resources)

    def test_station_resource_creation_workflow(self) -> None:
        """Test creating new resources for a station (as frontend upload would do)."""
        station = StationFactory.create(project=self.project)

        # Test creating a note resource - MUST use JSON
        note_data = {
            "station_id": str(station.id),
            "resource_type": "note",
            "title": "Survey Notes from Frontend",
            "description": "Notes added via the station modal",
            "text_content": (
                "Temperature: 12°C\nVisibility: Good\nFlow: Minimal\n\nDetailed "
                "observations from the field survey."
            ),
        }

        response = self.client.post(
            reverse("api:v1:resource-list-create"),
            data=json.dumps(note_data),
            content_type="application/json",
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_201_CREATED
        resource_data = response.data["data"]["resource"]

        # Verify resource data
        assert resource_data["resource_type"] == note_data["resource_type"]
        assert resource_data["title"] == note_data["title"]
        assert resource_data["description"] == note_data["description"]
        assert resource_data["text_content"] == note_data["text_content"]
        assert "id" in resource_data
        assert "created_by_email" in resource_data

        # Test creating a sketch resource - MUST use JSON
        sketch_data = {
            "station_id": str(station.id),
            "resource_type": "sketch",
            "title": "Cave Cross-Section",
            "description": "Hand-drawn diagram of the passage",
            "text_content": """<svg width="300" height="200" xmlns="http://www.w3.org/2000/svg">
                <rect width="300" height="200" fill="#1e293b"/>
                <path d="M50 100 L250 100 M150 50 L150 150" stroke="#38bdf8" stroke-width="3" fill="none"/>
                <circle cx="150" cy="100" r="8" fill="#f59e0b"/>
                <text x="160" y="105" fill="#e2e8f0" font-size="12">Station</text>
            </svg>""",  # noqa: E501
        }

        response = self.client.post(
            reverse("api:v1:resource-list-create"),
            data=json.dumps(sketch_data),
            content_type="application/json",
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_201_CREATED

        # Verify station now has 2 resources
        response = self.client.get(
            reverse("api:v1:station-detail", kwargs={"id": station.id}),
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_200_OK
        station_data = response.data["data"]["station"]
        assert station_data["resource_count"] == 2  # noqa: PLR2004

    def test_station_deletion_workflow(self) -> None:
        """Test deleting a station and its resources (as frontend delete would do)."""
        # Create station with resources
        station = StationFactory.create(project=self.project)
        resources = StationResourceFactory.create_demo_resources(station)
        station_id = station.id

        # Verify station exists with resources
        assert Station.objects.filter(id=station_id).exists()
        assert StationResource.objects.filter(station=station).count() == len(resources)

        # Delete station via API
        response = self.client.delete(
            reverse("api:v1:station-detail", kwargs={"id": station_id}),
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_200_OK
        assert "deleted successfully" in response.data["data"]["message"]

        # Verify station and all resources are deleted
        assert not Station.objects.filter(id=station_id).exists()
        assert StationResource.objects.filter(station_id=station_id).count() == 0

        # Verify station no longer appears in map data
        response = self.client.get(
            reverse("api:v1:stations-map"),
            {"project_id": str(self.project.id)},
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_200_OK
        geojson_data = response.data["data"]
        assert len(geojson_data["features"]) == 0

    def test_multiple_stations_workflow(self) -> None:
        """Test workflow with multiple stations in a project."""
        # Create multiple stations with different characteristics
        stations_data = [
            {
                "name": "Cave Entrance",
                "description": "Main entrance to the cave system",
                "latitude": Decimal("20.194500"),
                "longitude": Decimal("-87.497500"),
            },
            {
                "name": "Station Alpha",
                "description": "Major station with three passages",
                "latitude": Decimal("20.196200"),
                "longitude": Decimal("-87.499100"),
            },
            {
                "name": "Deep Chamber",
                "description": "Large chamber at depth",
                "latitude": Decimal("20.195800"),
                "longitude": Decimal("-87.498600"),
            },
        ]

        created_stations: list[Station] = []
        for station_data in stations_data:
            station = StationFactory.create(
                project=self.project,
                name=station_data["name"],
                description=station_data["description"],
                latitude=station_data["latitude"],
                longitude=station_data["longitude"],
            )

            # Add different numbers of resources to each station
            num_resources = len(created_stations) + 1  # 1, 2, 3 resources respectively
            for _ in range(num_resources):
                StationResourceFactory.create_note(station)

            created_stations.append(station)

        # Test map data includes all stations with correct resource counts
        response = self.client.get(
            reverse("api:v1:stations-map"),
            {"project_id": str(self.project.id)},
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_200_OK
        geojson_data = response.data["data"]
        assert len(geojson_data["features"]) == 3  # noqa: PLR2004

        # Verify each station in the map data
        features_by_name = {
            f["properties"]["name"]: f for f in geojson_data["features"]
        }

        for i, station_data in enumerate(stations_data):
            feature = features_by_name[station_data["name"]]
            assert feature["geometry"]["coordinates"] == [
                float(station_data["longitude"]),  # type: ignore[arg-type]
                float(station_data["latitude"]),  # type: ignore[arg-type]
            ]
            assert feature["properties"]["resource_count"] == i + 1  # 1, 2, 3 resources

        # Test station list API
        response = self.client.get(
            reverse("api:v1:station-list-create"),
            {"project_id": str(self.project.id)},
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_200_OK
        stations_list = response.data["data"]["stations"]
        assert len(stations_list) == 3  # noqa: PLR2004

        # Verify resource counts in list format
        stations_by_name = {s["name"]: s for s in stations_list}
        for i, station_data in enumerate(stations_data):
            station = stations_by_name[station_data["name"]]
            assert station["resource_count"] == i + 1

    def test_station_permissions_workflow(self) -> None:
        """Test station operations with different permission levels."""
        station = StationFactory.create(project=self.project)

        # Test with READ_ONLY permissions
        self.set_test_project_permission(PermissionLevel.READ_ONLY)
        readonly_auth = self.header_prefix + self.token.key

        # Read operations should work
        response = self.client.get(
            reverse("api:v1:stations-map"),
            {"project_id": str(self.project.id)},
            headers={"authorization": readonly_auth},
        )
        assert response.status_code == status.HTTP_200_OK

        response = self.client.get(
            reverse("api:v1:station-detail", kwargs={"id": station.id}),
            headers={"authorization": readonly_auth},
        )
        assert response.status_code == status.HTTP_200_OK

        # Write operations should fail - MUST use JSON
        response = self.client.post(
            reverse("api:v1:station-list-create"),
            data=json.dumps(
                {
                    "name": "Test",
                    "latitude": "1.0",
                    "longitude": "1.0",
                    "project_id": str(self.project.id),
                }
            ),
            content_type="application/json",
            headers={"authorization": readonly_auth},
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

        response = self.client.patch(
            reverse("api:v1:station-detail", kwargs={"id": station.id}),
            data=json.dumps({"latitude": "2.0"}),
            content_type="application/json",
            headers={"authorization": readonly_auth},
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

        response = self.client.delete(
            reverse("api:v1:station-detail", kwargs={"id": station.id}),
            headers={"authorization": readonly_auth},
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestMapViewerWithFixtures(TransactionTestCase):
    """Test map viewer with realistic fixture data."""

    def setUp(self) -> None:
        # Create test project and user
        self.user = UserFactory.create()
        self.project = ProjectFactory.create(created_by=self.user)

        # Create auth token
        self.token = Token.objects.create(user=self.user)
        self.auth = f"Token {self.token.key}"

        # Create user permission
        UserPermission.objects.create(
            target=self.user, project=self.project, level=PermissionLevel.READ_AND_WRITE
        )

    def test_realistic_cave_survey_scenario(self) -> None:
        """Test a realistic cave survey scenario with demo stations and resources."""
        # Create demo stations as they would appear in a real cave survey
        demo_stations = StationFactory.create_demo_stations(self.project, count=3)

        # Add realistic resources to each station
        for i, station in enumerate(demo_stations):
            # Each station gets different types of resources
            if i == 0:  # Station Alpha - Main data collection point
                StationResourceFactory.create_photo(station)
                StationResourceFactory.create_note(station)
                StationResourceFactory.create_sketch(station)
                StationResourceFactory.create_video(station)
            elif i == 1:  # Equipment Station
                StationResourceFactory.create_photo(station)
                StationResourceFactory.create_note(station)
            else:  # Deep Chamber
                StationResourceFactory.create_sketch(station)

        # Test map viewer loads all stations
        response = self.client.get(
            "/api/v1/stations/map/",
            {"project_id": str(self.project.id)},
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_200_OK
        geojson_data = response.json()["data"]
        assert len(geojson_data["features"]) == 3  # noqa: PLR2004

        # Verify coordinates match expected cave survey locations
        feature_coords = [
            f["geometry"]["coordinates"] for f in geojson_data["features"]
        ]
        expected_coords = [
            [-87.497500, 20.194500],  # Station Alpha
            [-87.499100, 20.196200],  # Equipment Station
            [-87.498600, 20.195800],  # Deep Chamber
        ]

        for coord in expected_coords:
            assert coord in feature_coords

        # Test detailed station loading (as modal would do)
        station_alpha = demo_stations[0]  # Station with most resources
        response = self.client.get(
            f"/api/v1/stations/{station_alpha.id}/",
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_200_OK
        station_data = response.json()["data"]["station"]

        # Verify it has the expected 4 resources (photo, note, sketch, video)
        assert station_data["resource_count"] == 4  # noqa: PLR2004
        assert len(station_data["resources"]) == 4  # noqa: PLR2004

        resource_types = {r["resource_type"] for r in station_data["resources"]}
        assert resource_types == {"photo", "note", "sketch", "video"}

    def test_station_creation_with_realistic_names(self) -> None:
        """Test creating stations with realistic cave survey names."""
        station_names = [
            "A1",
            "A2",
            "B1",
            "Station-001",
            "Main-Chamber-1",
            "Side-Passage-Alpha",
            "Equipment-Point-1",
        ]

        created_stations: list[dict[str, Any]] = []
        for name in station_names:
            response = self.client.post(
                "/api/v1/stations/",
                data=json.dumps(
                    {
                        "name": name,
                        "description": f"Survey station {name}",
                        "latitude": str(20.1945 + len(created_stations) * 0.0001),
                        "longitude": str(-87.4975 + len(created_stations) * 0.0001),
                        "project_id": str(self.project.id),
                    }
                ),
                headers={"authorization": self.auth},
                content_type="application/json",
            )

            assert response.status_code == status.HTTP_201_CREATED
            created_stations.append(response.json()["data"]["station"])

        # Verify all stations appear in map data
        response = self.client.get(
            "/api/v1/stations/map/",
            {"project_id": str(self.project.id)},
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_200_OK
        geojson_data = response.json()["data"]
        assert len(geojson_data["features"]) == len(station_names)

        # Verify all names are present
        feature_names = {f["properties"]["name"] for f in geojson_data["features"]}
        assert feature_names == set(station_names)
