# -*- coding: utf-8 -*-

"""
Backend integration contracts for station map data and resource deletion.
Authorization and individual CRUD behavior live in their endpoint tests.
"""

from __future__ import annotations

from django.urls import reverse
from rest_framework import status

from speleodb.api.v2.tests.base_testcase import BaseAPIProjectTestCase
from speleodb.api.v2.tests.base_testcase import PermissionType
from speleodb.api.v2.tests.factories import StationResourceFactory
from speleodb.api.v2.tests.factories import SubSurfaceStationFactory
from speleodb.common.enums import PermissionLevel
from speleodb.gis.models import Station
from speleodb.gis.models import StationResource


class TestMapViewerIntegration(BaseAPIProjectTestCase):
    """Protect resource aggregation and station deletion across API reads."""

    level = PermissionLevel.ADMIN
    permission_type = PermissionType.USER

    def setUp(self) -> None:
        super().setUp()

        self.set_test_project_permission(
            level=self.level,
            permission_type=self.permission_type,
        )
        self.auth = self.header_prefix + self.token.key

    def test_station_deletion_workflow(self) -> None:
        """Test deleting a station and its resources (as frontend delete would do)."""
        # Create station with resources
        station = SubSurfaceStationFactory.create(project=self.project)
        resources = [StationResourceFactory.create_note(station)]

        # Verify station exists with resources
        assert Station.objects.filter(id=station.id).exists()
        assert StationResource.objects.filter(station=station).count() == len(resources)

        station_id = str(station.id)

        # Delete station via API
        response = self.client.delete(
            reverse("api:v2:station-detail", kwargs={"id": station.id}),
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_200_OK, (
            response.status_code,
            self.level,
            self.permission_type,
        )

        assert station_id == response.data["id"]

        # Verify station and all resources are deleted
        assert not Station.objects.filter(id=station.id).exists()
        assert StationResource.objects.filter(station_id=station.id).count() == 0

        # Verify station no longer appears in map data
        response = self.client.get(
            reverse("api:v2:project-stations-geojson", kwargs={"id": self.project.id}),
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["features"]) == 0

    def test_multiple_stations_workflow(self) -> None:
        """Test workflow with multiple stations in a project."""
        # Create multiple stations with different characteristics
        stations_data = [
            {
                "name": "Cave Entrance",
                "description": "Main entrance to the cave system",
                "latitude": 20.194500,
                "longitude": -87.497500,
            },
            {
                "name": "Station Alpha",
                "description": "Major station with three passages",
                "latitude": 20.196200,
                "longitude": -87.499100,
            },
            {
                "name": "Deep Chamber",
                "description": "Large chamber at depth",
                "latitude": 20.195800,
                "longitude": -87.498600,
            },
        ]

        created_stations: list[Station] = []
        for station_data in stations_data:
            station = SubSurfaceStationFactory.create(
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
            reverse("api:v2:project-stations-geojson", kwargs={"id": self.project.id}),
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_200_OK, (
            response.status_code,
            self.level,
            self.permission_type,
        )

        geojson_data = response.data
        assert geojson_data["type"] == "FeatureCollection"
        assert len(geojson_data["features"]) == 3  # noqa: PLR2004

        # Verify each station in the map data
        features_by_name = {
            f["properties"]["name"]: f for f in geojson_data["features"]
        }

        for station_data in stations_data:
            feature = features_by_name[station_data["name"]]
            assert feature["type"] == "Feature"
            assert feature["geometry"]["type"] == "Point"
            assert feature["geometry"]["coordinates"] == [
                float(station_data["longitude"]),  # type: ignore[arg-type]
                float(station_data["latitude"]),  # type: ignore[arg-type]
            ]

        # Test station list API
        response = self.client.get(
            reverse("api:v2:project-stations", kwargs={"id": self.project.id}),
            headers={"authorization": self.auth},
        )

        assert response.status_code == status.HTTP_200_OK, (
            response.status_code,
            self.level,
            self.permission_type,
        )
        stations_list = response.json()
        assert len(stations_list) == 3  # noqa: PLR2004

        # Verify resource counts in list format
        stations_by_name = {s["name"]: s for s in stations_list}
        for i, station_data in enumerate(stations_data):
            _station = stations_by_name[station_data["name"]]
            assert len(_station["resources"]) == i + 1

        response = self.client.get(
            reverse("api:v2:station-detail", kwargs={"id": created_stations[0].id}),
            headers={"authorization": self.auth},
        )
        assert response.status_code == status.HTTP_200_OK
        assert (
            response.json()["resources"]
            == stations_by_name[created_stations[0].name]["resources"]
        )
