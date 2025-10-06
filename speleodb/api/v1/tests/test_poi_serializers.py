"""Tests for PointOfInterest serializers."""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

from speleodb.api.v1.serializers.poi import PointOfInterestGeoJSONSerializer
from speleodb.api.v1.serializers.poi import PointOfInterestSerializer
from speleodb.surveys.models import PointOfInterest
from speleodb.users.models import User


@pytest.fixture
def user() -> User:
    """Create a test user."""
    return User.objects.create_user(
        email="testuser@example.com",
        password="testpass123",  # noqa: S106
    )


@pytest.fixture
def poi(user: User) -> PointOfInterest:
    """Create a test POI."""
    return PointOfInterest.objects.create(
        name="Test POI",
        description="Test description",
        latitude=45.123456,
        longitude=-122.654321,
        created_by=user,
    )


@pytest.mark.django_db
class TestPointOfInterestSerializer:
    """Test cases for PointOfInterestSerializer."""

    def test_serialize_poi(self, poi: PointOfInterest) -> None:
        """Test serializing a POI to JSON."""
        serializer = PointOfInterestSerializer(poi)
        data = serializer.data

        assert data["id"] == str(poi.id)
        assert data["name"] == "Test POI"
        assert data["description"] == "Test description"
        assert data["latitude"] == 45.123456  # noqa: PLR2004
        assert data["longitude"] == -122.654321  # noqa: PLR2004
        assert data["created_by"] == poi.created_by.email
        # assert data["created_by"] == "testuser@example.com"
        assert "creation_date" in data
        assert "modified_date" in data

    def test_deserialize_poi_create(self, user: User) -> None:
        """Test creating a POI from JSON data."""
        latitude = Decimal("47.608")
        longitude = Decimal("-122.3351432423467")
        data = {
            "name": "New POI",
            "description": "New description",
            "latitude": f"{latitude}",
            "longitude": f"{longitude}",
        }

        serializer = PointOfInterestSerializer(data=data)
        assert serializer.is_valid()

        # Set created_by in context
        class MockRequest:
            def __init__(self, user: User) -> None:
                self.user = user

        serializer.context["request"] = MockRequest(user)
        saved_poi = serializer.save()

        assert saved_poi.name == "New POI"
        assert saved_poi.description == "New description"
        assert saved_poi.latitude == round(latitude, 7)
        assert saved_poi.longitude == round(longitude, 7)
        assert saved_poi.created_by == user

    def test_deserialize_poi_update(self, poi: PointOfInterest) -> None:
        """Test updating a POI from JSON data."""
        latitude = Decimal("-12.89493274807432")
        longitude = Decimal("-123.432")
        data = {
            "name": "Updated POI",
            "description": "Updated description",
            "latitude": f"{latitude}",
            "longitude": f"{longitude}",
        }

        serializer = PointOfInterestSerializer(poi, data=data)
        assert serializer.is_valid()

        saved_poi = serializer.save()

        assert saved_poi.name == "Updated POI"
        assert saved_poi.description == "Updated description"
        assert saved_poi.latitude == round(latitude, 7)
        assert saved_poi.longitude == round(longitude, 7)

    def test_validate_latitude_range(self) -> None:
        """Test latitude validation in serializer."""
        # Test invalid latitude > 90
        data = {
            "name": "Invalid POI",
            "latitude": "91.0",
            "longitude": "0.0",
        }

        serializer = PointOfInterestSerializer(data=data)
        assert not serializer.is_valid()
        assert "latitude" in serializer.errors

        # Test invalid latitude < -90
        data["latitude"] = "-91.0"
        serializer = PointOfInterestSerializer(data=data)
        assert not serializer.is_valid()
        assert "latitude" in serializer.errors

    def test_validate_longitude_range(self) -> None:
        """Test longitude validation in serializer."""
        # Test invalid longitude > 180
        data = {
            "name": "Invalid POI",
            "latitude": "0.0",
            "longitude": "181.0",
        }

        serializer = PointOfInterestSerializer(data=data)
        assert not serializer.is_valid()
        assert "longitude" in serializer.errors

        # Test invalid longitude < -180
        data["longitude"] = "-181.0"
        serializer = PointOfInterestSerializer(data=data)
        assert not serializer.is_valid()
        assert "longitude" in serializer.errors

    def test_read_only_fields(self, poi: PointOfInterest) -> None:
        """Test that read-only fields cannot be updated."""
        original_id = poi.id
        original_created_by = poi.created_by
        original_creation_date = poi.creation_date

        data = {
            "id": uuid.uuid4(),
            "name": poi.name,
            "latitude": f"{poi.latitude}",
            "longitude": f"{poi.longitude}",
            "created_by": "johndoe@example.com",
            "creation_date": "2020-01-01T00:00:00Z",
            "modified_date": "2020-01-01T00:00:00Z",
        }

        serializer = PointOfInterestSerializer(poi, data=data)
        assert serializer.is_valid()
        updated_poi = serializer.save()

        # Read-only fields should not change
        assert updated_poi.id == original_id
        assert updated_poi.created_by == original_created_by
        assert updated_poi.creation_date == original_creation_date


@pytest.mark.django_db
class TestPointOfInterestGeoJSONSerializer:
    """Test cases for PointOfInterestGeoJSONSerializer."""

    def test_map_serializer_geojson_format(self, poi: PointOfInterest) -> None:
        """Test that map serializer produces valid GeoJSON."""
        serializer = PointOfInterestGeoJSONSerializer(poi)
        data = serializer.data

        # Check GeoJSON structure
        assert data["type"] == "Feature"
        assert "geometry" in data
        assert "properties" in data

        # Check geometry
        geometry = data["geometry"]
        assert geometry["type"] == "Point"
        assert geometry["coordinates"] == [-122.654321, 45.123456]

        # Check properties
        properties = data["properties"]
        assert properties["id"] == str(poi.id)
        assert properties["name"] == "Test POI"
        assert properties["description"] == "Test description"

    def test_map_serializer_feature_collection(self, user: User) -> None:
        """Test serializing multiple POIs as GeoJSON FeatureCollection."""
        _ = PointOfInterest.objects.create(
            name="POI 1",
            latitude=45.0,
            longitude=-122.0,
            created_by=user,
        )
        _ = PointOfInterest.objects.create(
            name="POI 2",
            latitude=46.0,
            longitude=-123.0,
            created_by=user,
        )

        pois = PointOfInterest.objects.all()
        serializer = PointOfInterestGeoJSONSerializer(pois, many=True)
        data = serializer.data

        assert len(data) == 2  # noqa: PLR2004
        assert all(feature["type"] == "Feature" for feature in data)
        assert data[0]["properties"]["name"] == "POI 1"
        assert data[1]["properties"]["name"] == "POI 2"

    def test_map_serializer_coordinate_order(self, poi: PointOfInterest) -> None:
        """Test that coordinates are in correct order [lng, lat] for GeoJSON."""
        serializer = PointOfInterestGeoJSONSerializer(poi)
        data = serializer.data

        coordinates = data["geometry"]["coordinates"]
        assert coordinates[0] == -122.654321  # longitude first  # noqa: PLR2004
        assert coordinates[1] == 45.123456  # latitude second  # noqa: PLR2004

    def test_map_serializer_null_description(self, user: User) -> None:
        """Test map serializer with null/empty description."""
        poi = PointOfInterest.objects.create(
            name="No Description POI",
            description="",
            latitude=45.0,
            longitude=-122.0,
            created_by=user,
        )

        serializer = PointOfInterestGeoJSONSerializer(poi)
        data = serializer.data

        assert data["properties"]["description"] == ""
