"""Tests for PointOfInterest serializers."""

from __future__ import annotations

import pytest

from speleodb.api.v1.serializers.poi import PointOfInterestListSerializer
from speleodb.api.v1.serializers.poi import PointOfInterestMapSerializer
from speleodb.api.v1.serializers.poi import PointOfInterestSerializer
from speleodb.surveys.models import PointOfInterest
from speleodb.users.models import User


@pytest.mark.django_db
class TestPointOfInterestSerializer:
    """Test cases for PointOfInterestSerializer."""

    @pytest.fixture
    def user(self) -> User:
        """Create a test user."""
        return User.objects.create_user(
            email="testuser@example.com",
            password="testpass123",  # noqa: S106
        )

    @pytest.fixture
    def poi(self, user: User) -> PointOfInterest:
        """Create a test POI."""
        return PointOfInterest.objects.create(
            name="Test POI",
            description="Test description",
            latitude=45.123456,
            longitude=-122.654321,
            created_by=user,
        )

    def test_serialize_poi(self, poi: PointOfInterest) -> None:
        """Test serializing a POI to JSON."""
        serializer = PointOfInterestSerializer(poi)
        data = serializer.data

        assert data["id"] == str(poi.id)
        assert data["name"] == "Test POI"
        assert data["description"] == "Test description"
        assert data["latitude"] == 45.123456  # noqa: PLR2004
        assert data["longitude"] == -122.654321  # noqa: PLR2004
        assert data["created_by"] == poi.created_by.id
        assert data["created_by_email"] == "testuser@example.com"
        assert "creation_date" in data
        assert "modified_date" in data

    def test_deserialize_poi_create(self, user: User) -> None:
        """Test creating a POI from JSON data."""
        data = {
            "name": "New POI",
            "description": "New description",
            "latitude": "47.608013",
            "longitude": "-122.335167",
        }

        serializer = PointOfInterestSerializer(data=data)
        assert serializer.is_valid()

        # Set created_by in context
        class MockRequest:
            def __init__(self, user: User) -> None:
                self.user = user

        serializer.context["request"] = MockRequest(user)
        poi = serializer.save()

        assert poi.name == "New POI"
        assert poi.description == "New description"
        assert poi.latitude == 47.608013  # noqa: PLR2004
        assert poi.longitude == -122.335167  # noqa: PLR2004
        assert poi.created_by == user

    def test_deserialize_poi_update(self, poi: PointOfInterest) -> None:
        """Test updating a POI from JSON data."""
        data = {
            "name": "Updated POI",
            "description": "Updated description",
            "latitude": "48.0",
            "longitude": "-123.0",
        }

        serializer = PointOfInterestSerializer(poi, data=data)
        assert serializer.is_valid()

        updated_poi = serializer.save()

        assert updated_poi.name == "Updated POI"
        assert updated_poi.description == "Updated description"
        assert updated_poi.latitude == 48.0  # noqa: PLR2004
        assert updated_poi.longitude == -123.0  # noqa: PLR2004

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

    def test_coordinate_precision(self, user: User) -> None:
        """Test that coordinates are rounded to 7 decimal places."""
        data = {
            "name": "Precise POI",
            "latitude": "45.12345678901234",  # More than 7 decimal places
            "longitude": "-122.98765432109876",
        }

        serializer = PointOfInterestSerializer(data=data)
        assert serializer.is_valid()

        # Set created_by in context
        class MockRequest:
            def __init__(self, user: User) -> None:
                self.user = user

        serializer.context["request"] = MockRequest(user)
        poi = serializer.save()

        # Check that coordinates are rounded to 7 decimal places
        assert str(poi.latitude) == "45.1234568"
        assert str(poi.longitude) == "-122.9876543"

    def test_read_only_fields(self, poi: PointOfInterest) -> None:
        """Test that read-only fields cannot be updated."""
        original_id = poi.id
        original_created_by = poi.created_by
        original_creation_date = poi.creation_date

        data = {
            "id": "00000000-0000-0000-0000-000000000000",
            "name": poi.name,
            "latitude": str(poi.latitude),
            "longitude": str(poi.longitude),
            "created_by": 999,
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
class TestPointOfInterestListSerializer:
    """Test cases for PointOfInterestListSerializer."""

    @pytest.fixture
    def user(self) -> User:
        """Create a test user."""
        return User.objects.create_user(
            email="testuser@example.com",
            password="testpass123",  # noqa: S106
        )

    @pytest.fixture
    def poi(self, user: User) -> PointOfInterest:
        """Create a test POI."""
        return PointOfInterest.objects.create(
            name="List POI",
            description="This is a longer description that should not appear in view",
            latitude=45.123456,
            longitude=-122.654321,
            created_by=user,
        )

    def test_list_serializer_fields(self, poi: PointOfInterest) -> None:
        """Test that list serializer only includes minimal fields."""
        serializer = PointOfInterestListSerializer(poi)
        data = serializer.data

        # Should include these fields
        assert "id" in data
        assert "name" in data
        assert "latitude" in data
        assert "longitude" in data
        assert "creation_date" in data

        # Should NOT include these fields
        assert "description" not in data
        assert "created_by" not in data
        assert "created_by_email" not in data
        assert "modified_date" not in data

        # Verify values
        assert data["id"] == str(poi.id)
        assert data["name"] == "List POI"
        assert data["latitude"] == 45.123456  # noqa: PLR2004
        assert data["longitude"] == -122.654321  # noqa: PLR2004

    def test_list_serializer_multiple_pois(self, user: User) -> None:
        """Test serializing multiple POIs for list view."""
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
        serializer = PointOfInterestListSerializer(pois, many=True)
        data = serializer.data

        assert len(data) == 2  # noqa: PLR2004
        assert data[0]["name"] == "POI 1"
        assert data[1]["name"] == "POI 2"


@pytest.mark.django_db
class TestPointOfInterestMapSerializer:
    """Test cases for PointOfInterestMapSerializer."""

    @pytest.fixture
    def user(self) -> User:
        """Create a test user."""
        return User.objects.create_user(
            email="testuser@example.com",
            password="testpass123",  # noqa: S106
        )

    @pytest.fixture
    def poi(self, user: User) -> PointOfInterest:
        """Create a test POI."""
        return PointOfInterest.objects.create(
            name="Map POI",
            description="POI for map display",
            latitude=45.123456,
            longitude=-122.654321,
            created_by=user,
        )

    def test_map_serializer_geojson_format(self, poi: PointOfInterest) -> None:
        """Test that map serializer produces valid GeoJSON."""
        serializer = PointOfInterestMapSerializer(poi)
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
        assert properties["name"] == "Map POI"
        assert properties["description"] == "POI for map display"
        assert properties["created_by_email"] == "testuser@example.com"
        assert "creation_date" in properties

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
        serializer = PointOfInterestMapSerializer(pois, many=True)
        data = serializer.data

        assert len(data) == 2  # noqa: PLR2004
        assert all(feature["type"] == "Feature" for feature in data)
        assert data[0]["properties"]["name"] == "POI 1"
        assert data[1]["properties"]["name"] == "POI 2"

    def test_map_serializer_coordinate_order(self, poi: PointOfInterest) -> None:
        """Test that coordinates are in correct order [lng, lat] for GeoJSON."""
        serializer = PointOfInterestMapSerializer(poi)
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

        serializer = PointOfInterestMapSerializer(poi)
        data = serializer.data

        assert data["properties"]["description"] == ""

    def test_map_serializer_deleted_creator(self, user: User) -> None:
        """Test map serializer when creator user is deleted."""
        poi = PointOfInterest.objects.create(
            name="Orphaned POI",
            latitude=45.0,
            longitude=-122.0,
            created_by=user,
        )

        # Since the model uses CASCADE, deleting the user will delete the POI
        # So let's test what happens when we can't access the user email instead
        # This simulates a case where the user exists but has no email
        user.email = ""
        user.save()

        poi.refresh_from_db()
        serializer = PointOfInterestMapSerializer(poi)
        data = serializer.data

        # Should handle empty email gracefully
        assert data["properties"]["created_by_email"] == ""
