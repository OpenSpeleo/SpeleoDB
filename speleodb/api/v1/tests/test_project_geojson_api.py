# -*- coding: utf-8 -*-

from __future__ import annotations

import json
from typing import Any

from django.urls import reverse
from parameterized.parameterized import parameterized
from rest_framework import status

from speleodb.api.v1.tests.base_testcase import BaseAPIProjectTestCase
from speleodb.surveys.models import PermissionLevel


class TestProjectGeoJsonApiView(BaseAPIProjectTestCase):
    """Test suite for the ProjectGeoJsonApiView endpoint."""

    test_geojson: dict[str, Any] = {}

    def setUp(self) -> None:
        super().setUp()
        # Set up some test GeoJSON data
        self.test_geojson = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [-87.501234, 20.196710],
                    },
                    "properties": {"name": "Test Cave Entrance"},
                }
            ],
        }

    @parameterized.expand(
        [
            PermissionLevel.ADMIN,
            PermissionLevel.READ_AND_WRITE,
            PermissionLevel.READ_ONLY,
            PermissionLevel.WEB_VIEWER,
        ]
    )
    def test_get_project_geojson_with_permissions(self, level: PermissionLevel) -> None:
        """Test that users with read permissions can access GeoJSON data."""
        self.set_test_project_permission(level=level)

        # Set some test GeoJSON data
        self.project.geojson = self.test_geojson
        self.project.save()

        auth = self.header_prefix + self.token.key
        response = self.client.get(
            reverse(
                "api:v1:one_project_geojson_apiview", kwargs={"id": self.project.id}
            ),
            headers={"authorization": auth},
        )

        assert response.status_code == status.HTTP_200_OK, response.data
        assert response["Content-Type"] == "application/json"

        # Parse the response as JSON - expect SuccessResponse format
        response_data = json.loads(response.content)
        assert response_data["success"] is True
        assert "data" in response_data

        # Parse the data field directly as it contains the raw JSON string
        geojson_data = json.loads(response_data["data"])
        assert geojson_data == self.test_geojson

    def test_get_project_geojson_without_permissions(self) -> None:
        """Test that users without permissions cannot access GeoJSON data."""
        # Don't set any permissions for this user

        auth = self.header_prefix + self.token.key
        response = self.client.get(
            reverse(
                "api:v1:one_project_geojson_apiview", kwargs={"id": self.project.id}
            ),
            headers={"authorization": auth},
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_get_project_geojson_unauthenticated(self) -> None:
        """Test that unauthenticated users cannot access GeoJSON data."""
        response = self.client.get(
            reverse(
                "api:v1:one_project_geojson_apiview", kwargs={"id": self.project.id}
            ),
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_get_project_geojson_empty_data(self) -> None:
        """Test response when project has empty GeoJSON data."""
        self.set_test_project_permission(level=PermissionLevel.READ_ONLY)

        # Project should have empty geojson by default (empty dict)
        auth = self.header_prefix + self.token.key
        response = self.client.get(
            reverse(
                "api:v1:one_project_geojson_apiview", kwargs={"id": self.project.id}
            ),
            headers={"authorization": auth},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response["Content-Type"] == "application/json"

        # Should return empty dict as JSON within SuccessResponse format
        response_data = json.loads(response.content)
        assert response_data["success"] is True
        assert "data" in response_data

        # Parse the data field directly as it contains the raw JSON string
        geojson_data = json.loads(response_data["data"])
        assert geojson_data == {}

    def test_get_project_geojson_nonexistent_project(self) -> None:
        """Test response for non-existent project."""
        import uuid

        self.set_test_project_permission(level=PermissionLevel.READ_ONLY)

        fake_project_id = uuid.uuid4()
        auth = self.header_prefix + self.token.key
        response = self.client.get(
            reverse(
                "api:v1:one_project_geojson_apiview", kwargs={"id": fake_project_id}
            ),
            headers={"authorization": auth},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_get_project_geojson_complex_data(self) -> None:
        """Test with complex GeoJSON data including multiple features."""
        self.set_test_project_permission(level=PermissionLevel.READ_ONLY)

        complex_geojson = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [
                            [-87.501234, 20.196710],
                            [-87.501500, 20.196800],
                            [-87.501800, 20.196900],
                        ],
                    },
                    "properties": {
                        "name": "Cave Passage",
                        "length": 150.5,
                        "depth": -25.3,
                    },
                },
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [
                            [
                                [-87.501000, 20.196500],
                                [-87.502000, 20.196500],
                                [-87.502000, 20.197000],
                                [-87.501000, 20.197000],
                                [-87.501000, 20.196500],
                            ]
                        ],
                    },
                    "properties": {"name": "Cave Chamber", "area": 1250.0},
                },
            ],
        }

        # Set complex GeoJSON data
        self.project.geojson = complex_geojson
        self.project.save()

        auth = self.header_prefix + self.token.key
        response = self.client.get(
            reverse(
                "api:v1:one_project_geojson_apiview", kwargs={"id": self.project.id}
            ),
            headers={"authorization": auth},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response["Content-Type"] == "application/json"

        # Parse and verify the complex data within SuccessResponse format
        response_data = json.loads(response.content)
        assert response_data["success"] is True
        assert "data" in response_data

        # Parse the data field directly as it contains the raw JSON string
        geojson_data = json.loads(response_data["data"])
        assert geojson_data == complex_geojson
        assert len(geojson_data["features"]) == 2
        assert geojson_data["features"][0]["geometry"]["type"] == "LineString"
        assert geojson_data["features"][1]["geometry"]["type"] == "Polygon"

    def test_geojson_endpoint_performance_uses_with_geojson_manager(self) -> None:
        """Test that the endpoint properly loads geojson field."""
        self.set_test_project_permission(level=PermissionLevel.READ_ONLY)

        # Set some test data
        self.project.geojson = self.test_geojson
        self.project.save()

        auth = self.header_prefix + self.token.key
        response = self.client.get(
            reverse(
                "api:v1:one_project_geojson_apiview", kwargs={"id": self.project.id}
            ),
            headers={"authorization": auth},
        )

        assert response.status_code == status.HTTP_200_OK
        # Verify the data was loaded correctly within SuccessResponse format
        response_data = json.loads(response.content)
        assert response_data["success"] is True
        assert "data" in response_data

        # Parse the data field directly as it contains the raw JSON string
        geojson_data = json.loads(response_data["data"])
        assert geojson_data == self.test_geojson
