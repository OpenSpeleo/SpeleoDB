"""Tests for PointOfInterest API endpoints."""
# mypy: disable-error-code="attr-defined"

from decimal import Decimal
from typing import Any

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from speleodb.surveys.models import PointOfInterest

User: Any = get_user_model()


@pytest.mark.django_db
class TestPointOfInterestEndpoints:
    """Test cases for POI API endpoints."""

    @pytest.fixture
    def api_client(self):
        """Create an API client."""
        return APIClient()

    @pytest.fixture
    def user(self):
        """Create a test user."""
        return User.objects.create_user(
            email="testuser@example.com", password="testpass123"
        )

    @pytest.fixture
    def other_user(self):
        """Create another test user."""
        return User.objects.create_user(
            email="otheruser@example.com", password="otherpass123"
        )

    @pytest.fixture
    def poi(self, user):
        """Create a test POI."""
        return PointOfInterest.objects.create(
            name="Test POI",
            description="Test description",
            latitude=Decimal("45.123456"),
            longitude=Decimal("-122.654321"),
            created_by=user,
        )

    # List endpoint tests
    def test_list_pois_unauthenticated(self, api_client, poi):
        """Test listing POIs without authentication (should work - read-only)."""
        url = reverse("api:v1:poi-list-create")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert len(data["data"]["pois"]) == 1
        assert data["data"]["pois"][0]["name"] == "Test POI"

    def test_list_pois_authenticated(self, api_client, user, poi):
        """Test listing POIs with authentication."""
        api_client.force_authenticate(user=user)
        url = reverse("api:v1:poi-list-create")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert len(data["data"]["pois"]) == 1

    def test_list_pois_empty(self, api_client):
        """Test listing POIs when none exist."""
        url = reverse("api:v1:poi-list-create")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert len(data["data"]["pois"]) == 0

    def test_list_pois_multiple(self, api_client, user):
        """Test listing multiple POIs."""
        # Create multiple POIs
        for i in range(3):
            PointOfInterest.objects.create(
                name=f"POI {i}",
                latitude=Decimal(f"{45 + i}.0"),
                longitude=Decimal(f"{-122 - i}.0"),
                created_by=user,
            )

        url = reverse("api:v1:poi-list-create")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["data"]["pois"]) == 3

    # Retrieve endpoint tests
    def test_retrieve_poi_unauthenticated(self, api_client, poi):
        """Test retrieving a single POI without authentication (should work)."""
        url = reverse("api:v1:poi-detail", kwargs={"id": poi.id})
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["data"]["poi"]["name"] == "Test POI"
        assert data["data"]["poi"]["description"] == "Test description"

    def test_retrieve_poi_authenticated(self, api_client, user, poi):
        """Test retrieving a single POI with authentication."""
        api_client.force_authenticate(user=user)
        url = reverse("api:v1:poi-detail", kwargs={"id": poi.id})
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["data"]["poi"]["created_by_email"] == "testuser@example.com"

    def test_retrieve_poi_not_found(self, api_client):
        """Test retrieving a non-existent POI."""
        fake_uuid = "00000000-0000-0000-0000-000000000000"
        url = reverse("api:v1:poi-detail", kwargs={"id": fake_uuid})
        response = api_client.get(url)

        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        assert data["success"] is False

    # Create endpoint tests
    def test_create_poi_unauthenticated(self, api_client):
        """Test creating a POI without authentication (should fail)."""
        url = reverse("api:v1:poi-list-create")
        data = {
            "name": "New POI",
            "latitude": "45.0",
            "longitude": "-122.0",
        }

        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_create_poi_authenticated(self, api_client, user):
        """Test creating a POI with authentication."""
        api_client.force_authenticate(user=user)
        url = reverse("api:v1:poi-list-create")
        data = {
            "name": "New POI",
            "description": "New description",
            "latitude": "47.608013",
            "longitude": "-122.335167",
        }

        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        response_data = response.json()
        assert response_data["success"] is True
        assert response_data["data"]["poi"]["name"] == "New POI"
        assert (
            response_data["data"]["poi"]["created_by_email"] == "testuser@example.com"
        )

        # Verify POI was created in database
        poi = PointOfInterest.objects.get(name="New POI")
        assert poi.created_by == user

    def test_create_poi_minimal_data(self, api_client, user):
        """Test creating a POI with minimal data."""
        api_client.force_authenticate(user=user)
        url = reverse("api:v1:poi-list-create")
        data = {
            "name": "Minimal POI",
            "latitude": "0.0",
            "longitude": "0.0",
        }

        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        poi = PointOfInterest.objects.get(name="Minimal POI")
        assert poi.description == ""

    def test_create_poi_invalid_latitude(self, api_client, user):
        """Test creating a POI with invalid latitude."""
        api_client.force_authenticate(user=user)
        url = reverse("api:v1:poi-list-create")
        data = {
            "name": "Invalid POI",
            "latitude": "91.0",  # Invalid - > 90
            "longitude": "0.0",
        }

        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        response_data = response.json()
        assert "latitude" in response_data["errors"]

    def test_create_poi_invalid_longitude(self, api_client, user):
        """Test creating a POI with invalid longitude."""
        api_client.force_authenticate(user=user)
        url = reverse("api:v1:poi-list-create")
        data = {
            "name": "Invalid POI",
            "latitude": "0.0",
            "longitude": "181.0",  # Invalid - > 180
        }

        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        response_data = response.json()
        assert "longitude" in response_data["errors"]

    # Update endpoint tests
    def test_update_poi_unauthenticated(self, api_client, poi):
        """Test updating a POI without authentication (should fail)."""
        url = reverse("api:v1:poi-detail", kwargs={"id": poi.id})
        data = {"name": "Updated POI"}

        response = api_client.patch(url, data, format="json")

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_update_poi_as_creator(self, api_client, user, poi):
        """Test updating a POI as the creator."""
        api_client.force_authenticate(user=user)
        url = reverse("api:v1:poi-detail", kwargs={"id": poi.id})
        data = {
            "name": "Updated POI",
            "description": "Updated description",
        }

        response = api_client.patch(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert response_data["data"]["poi"]["name"] == "Updated POI"
        assert response_data["data"]["poi"]["description"] == "Updated description"

        # Verify in database
        poi.refresh_from_db()
        assert poi.name == "Updated POI"

    def test_update_poi_as_other_user(self, api_client, other_user, poi):
        """Test updating a POI as a different user (should succeed - any authenticated user can update)."""
        api_client.force_authenticate(user=other_user)
        url = reverse("api:v1:poi-detail", kwargs={"id": poi.id})
        data = {"description": "Updated by another user"}

        response = api_client.patch(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        poi.refresh_from_db()
        assert poi.description == "Updated by another user"

    def test_update_poi_coordinates(self, api_client, user, poi):
        """Test updating POI coordinates."""
        api_client.force_authenticate(user=user)
        url = reverse("api:v1:poi-detail", kwargs={"id": poi.id})
        data = {
            "latitude": "48.0",
            "longitude": "-123.0",
        }

        response = api_client.patch(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        poi.refresh_from_db()
        assert poi.latitude == Decimal("48.0")
        assert poi.longitude == Decimal("-123.0")

    def test_update_poi_invalid_data(self, api_client, user, poi):
        """Test updating POI with invalid data."""
        api_client.force_authenticate(user=user)
        url = reverse("api:v1:poi-detail", kwargs={"id": poi.id})
        data = {"latitude": "invalid"}

        response = api_client.patch(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_update_poi_duplicate_name(self, api_client, user, poi):
        """Test updating POI to a duplicate name."""
        # Create another POI
        other_poi = PointOfInterest.objects.create(
            name="Other POI",
            latitude=Decimal("0.0"),
            longitude=Decimal("0.0"),
            created_by=user,
        )

        api_client.force_authenticate(user=user)
        url = reverse("api:v1:poi-detail", kwargs={"id": poi.id})
        data = {"name": "Other POI"}  # Try to use existing name

        response = api_client.patch(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        response_data = response.json()
        assert "name" in response_data["errors"]

    # Delete endpoint tests
    def test_delete_poi_unauthenticated(self, api_client, poi):
        """Test deleting a POI without authentication (should fail)."""
        url = reverse("api:v1:poi-detail", kwargs={"id": poi.id})
        response = api_client.delete(url)

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_delete_poi_as_creator(self, api_client, user, poi):
        """Test deleting a POI as the creator."""
        api_client.force_authenticate(user=user)
        url = reverse("api:v1:poi-detail", kwargs={"id": poi.id})
        response = api_client.delete(url)

        assert response.status_code == status.HTTP_200_OK

        # Verify POI was deleted
        assert not PointOfInterest.objects.filter(id=poi.id).exists()

    def test_delete_poi_as_other_user(self, api_client, other_user, poi):
        """Test deleting a POI as a different user (should succeed - any authenticated user can delete)."""
        api_client.force_authenticate(user=other_user)
        url = reverse("api:v1:poi-detail", kwargs={"id": poi.id})
        response = api_client.delete(url)

        assert response.status_code == status.HTTP_200_OK
        assert not PointOfInterest.objects.filter(id=poi.id).exists()

    def test_delete_poi_not_found(self, api_client, user):
        """Test deleting a non-existent POI."""
        api_client.force_authenticate(user=user)
        fake_uuid = "00000000-0000-0000-0000-000000000000"
        url = reverse("api:v1:poi-detail", kwargs={"id": fake_uuid})
        response = api_client.delete(url)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    # Map endpoint tests
    def test_map_endpoint_unauthenticated(self, api_client, user):
        """Test map endpoint without authentication (should work)."""
        # Create POIs with different properties
        poi1 = PointOfInterest.objects.create(
            name="POI 1",
            description="Description 1",
            latitude=Decimal("45.0"),
            longitude=Decimal("-122.0"),
            created_by=user,
        )
        poi2 = PointOfInterest.objects.create(
            name="POI 2",
            latitude=Decimal("46.0"),
            longitude=Decimal("-123.0"),
            created_by=user,  # Using the same user
        )

        url = reverse("api:v1:pois-map")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["data"]["type"] == "FeatureCollection"
        assert len(data["data"]["features"]) == 2

        # Check first feature
        feature1 = data["data"]["features"][0]
        assert feature1["type"] == "Feature"
        assert feature1["geometry"]["type"] == "Point"
        assert feature1["properties"]["name"] == "POI 1"
        assert feature1["properties"]["created_by_email"] == "testuser@example.com"

        # Check second feature (same creator)
        feature2 = data["data"]["features"][1]
        assert feature2["properties"]["created_by_email"] == "testuser@example.com"

    def test_map_endpoint_empty(self, api_client):
        """Test map endpoint with no POIs."""
        url = reverse("api:v1:pois-map")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["data"]["type"] == "FeatureCollection"
        assert len(data["data"]["features"]) == 0

    def test_map_endpoint_coordinate_format(self, api_client, poi):
        """Test that map endpoint returns coordinates in correct GeoJSON format."""
        url = reverse("api:v1:pois-map")
        response = api_client.get(url)

        data = response.json()
        feature = data["data"]["features"][0]
        coordinates = feature["geometry"]["coordinates"]

        # GeoJSON format is [longitude, latitude]
        assert coordinates[0] == -122.654321  # longitude
        assert coordinates[1] == 45.123456  # latitude

    # Edge cases and error handling
    def test_invalid_http_methods(self, api_client, poi):
        """Test invalid HTTP methods return appropriate errors."""
        # Test PUT on list endpoint (should not be allowed)
        url = reverse("api:v1:poi-list-create")
        response = api_client.put(url, {}, format="json")
        assert response.status_code == status.HTTP_403_FORBIDDEN  # No auth provided

    def test_coordinate_precision_in_responses(self, api_client, user):
        """Test that coordinates maintain proper precision in API responses."""
        api_client.force_authenticate(user=user)

        # Create POI with precise coordinates
        url = reverse("api:v1:poi-list-create")
        data = {
            "name": "Precise POI",
            "latitude": "45.1234567",
            "longitude": "-122.7654321",
        }

        response = api_client.post(url, data, format="json")
        assert response.status_code == status.HTTP_201_CREATED

        # Check response maintains 7 decimal places
        poi_data = response.json()["data"]["poi"]
        assert poi_data["latitude"] == "45.1234567"
        assert poi_data["longitude"] == "-122.7654321"
