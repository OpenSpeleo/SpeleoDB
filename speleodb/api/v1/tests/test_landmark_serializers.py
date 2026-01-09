"""Tests for Landmark serializers."""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

from speleodb.api.v1.serializers.landmark import LandmarkGeoJSONSerializer
from speleodb.api.v1.serializers.landmark import LandmarkSerializer
from speleodb.gis.models import Landmark
from speleodb.users.models import User


@pytest.fixture
def user() -> User:
    """Create a test user."""
    return User.objects.create_user(
        email="testuser@example.com",
        password="testpass123",  # noqa: S106
    )


@pytest.fixture
def landmark(user: User) -> Landmark:
    """Create a test Landmark."""
    return Landmark.objects.create(
        name="Test Landmark",
        description="Test description",
        latitude=45.123456,
        longitude=-122.654321,
        user=user,
    )


@pytest.mark.django_db
class TestLandmarkSerializer:
    """Test cases for LandmarkSerializer."""

    def test_serialize_landmark(self, landmark: Landmark) -> None:
        """Test serializing a Landmark to JSON."""
        serializer = LandmarkSerializer(landmark)
        data = serializer.data

        assert data["id"] == str(landmark.id)
        assert data["name"] == "Test Landmark"
        assert data["description"] == "Test description"
        assert data["latitude"] == 45.123456  # noqa: PLR2004
        assert data["longitude"] == -122.654321  # noqa: PLR2004
        assert data["user"] == landmark.user.email
        assert "creation_date" in data
        assert "modified_date" in data

    def test_deserialize_landmark_create(self, user: User) -> None:
        """Test creating a Landmark from JSON data."""
        latitude = Decimal("47.608")
        longitude = Decimal("-122.3351432423467")
        data = {
            "name": "New Landmark",
            "description": "New description",
            "latitude": f"{latitude}",
            "longitude": f"{longitude}",
        }

        serializer = LandmarkSerializer(data=data)
        assert serializer.is_valid()

        # Set user in context
        class MockRequest:
            def __init__(self, user: User) -> None:
                self.user = user

        serializer.context["request"] = MockRequest(user)
        saved_landmark = serializer.save()

        assert saved_landmark.name == "New Landmark"
        assert saved_landmark.description == "New description"
        assert saved_landmark.latitude == round(latitude, 7)
        assert saved_landmark.longitude == round(longitude, 7)
        assert saved_landmark.user == user

    def test_deserialize_landmark_update(self, landmark: Landmark) -> None:
        """Test updating a Landmark from JSON data."""
        latitude = Decimal("-12.89493274807432")
        longitude = Decimal("-123.432")
        data = {
            "name": "Updated Landmark",
            "description": "Updated description",
            "latitude": f"{latitude}",
            "longitude": f"{longitude}",
        }

        serializer = LandmarkSerializer(landmark, data=data)
        assert serializer.is_valid()

        saved_landmark = serializer.save()

        assert saved_landmark.name == "Updated Landmark"
        assert saved_landmark.description == "Updated description"
        assert saved_landmark.latitude == round(latitude, 7)
        assert saved_landmark.longitude == round(longitude, 7)

    def test_validate_latitude_range(self) -> None:
        """Test latitude validation in serializer."""
        # Test invalid latitude > 90
        data = {
            "name": "Invalid Landmark",
            "latitude": "91.0",
            "longitude": "0.0",
        }

        serializer = LandmarkSerializer(data=data)
        assert not serializer.is_valid()
        assert "latitude" in serializer.errors

        # Test invalid latitude < -90
        data["latitude"] = "-91.0"
        serializer = LandmarkSerializer(data=data)
        assert not serializer.is_valid()
        assert "latitude" in serializer.errors

    def test_validate_longitude_range(self) -> None:
        """Test longitude validation in serializer."""
        # Test invalid longitude > 180
        data = {
            "name": "Invalid Landmark",
            "latitude": "0.0",
            "longitude": "181.0",
        }

        serializer = LandmarkSerializer(data=data)
        assert not serializer.is_valid()
        assert "longitude" in serializer.errors

        # Test invalid longitude < -180
        data["longitude"] = "-181.0"
        serializer = LandmarkSerializer(data=data)
        assert not serializer.is_valid()
        assert "longitude" in serializer.errors

    def test_read_only_fields(self, landmark: Landmark) -> None:
        """Test that read-only fields cannot be updated."""
        original_id = landmark.id
        original_user = landmark.user
        original_creation_date = landmark.creation_date
        data = {
            "id": uuid.uuid4(),
            "name": landmark.name,
            "latitude": f"{landmark.latitude}",
            "longitude": f"{landmark.longitude}",
            "user": "johndoe@example.com",
            "creation_date": "2020-01-01T00:00:00Z",
            "modified_date": "2020-01-01T00:00:00Z",
        }

        serializer = LandmarkSerializer(landmark, data=data)
        assert serializer.is_valid()
        updated_landmark = serializer.save()

        # Read-only fields should not change
        assert updated_landmark.id == original_id
        assert updated_landmark.user == original_user
        assert updated_landmark.creation_date == original_creation_date


@pytest.mark.django_db
class TestLandmarkGeoJSONSerializer:
    """Test cases for LandmarkGeoJSONSerializer."""

    def test_map_serializer_geojson_format(self, landmark: Landmark) -> None:
        """Test that map serializer produces valid GeoJSON."""
        serializer = LandmarkGeoJSONSerializer(landmark)
        data = serializer.data

        # Check GeoJSON structure
        assert data["type"] == "Feature"
        assert "geometry" in data
        assert "properties" in data

        # Check ID
        assert data["id"] == str(landmark.id)

        # Check geometry
        geometry = data["geometry"]
        assert geometry["type"] == "Point"
        assert geometry["coordinates"] == [-122.654321, 45.123456]

        # Check properties
        properties = data["properties"]
        assert properties["name"] == "Test Landmark"
        assert properties["description"] == "Test description"

    def test_map_serializer_feature_collection(self, user: User) -> None:
        """Test serializing multiple Landmarks as GeoJSON FeatureCollection."""
        _ = Landmark.objects.create(
            name="Landmark 1",
            latitude=45.0,
            longitude=-122.0,
            user=user,
        )
        _ = Landmark.objects.create(
            name="Landmark 2",
            latitude=46.0,
            longitude=-123.0,
            user=user,
        )

        landmarks = Landmark.objects.all()
        serializer = LandmarkGeoJSONSerializer(landmarks, many=True)
        data = serializer.data

        assert len(data) == 2  # noqa: PLR2004
        assert all(feature["type"] == "Feature" for feature in data)
        assert data[0]["properties"]["name"] == "Landmark 1"
        assert data[1]["properties"]["name"] == "Landmark 2"

    def test_map_serializer_coordinate_order(self, landmark: Landmark) -> None:
        """Test that coordinates are in correct order [lng, lat] for GeoJSON."""
        serializer = LandmarkGeoJSONSerializer(landmark)
        data = serializer.data

        coordinates = data["geometry"]["coordinates"]
        assert coordinates[0] == -122.654321  # longitude first  # noqa: PLR2004
        assert coordinates[1] == 45.123456  # latitude second  # noqa: PLR2004

    def test_map_serializer_null_description(self, user: User) -> None:
        """Test map serializer with null/empty description."""
        landmark = Landmark.objects.create(
            name="No Description Landmark",
            description="",
            latitude=45.0,
            longitude=-122.0,
            user=user,
        )

        serializer = LandmarkGeoJSONSerializer(landmark)
        data = serializer.data

        assert data["properties"]["description"] == ""
