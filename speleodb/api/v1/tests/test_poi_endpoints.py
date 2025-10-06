"""Tests for PointOfInterest API endpoints."""

from __future__ import annotations

import uuid

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from speleodb.surveys.models import PointOfInterest
from speleodb.users.models import User


@pytest.mark.django_db
class TestPointOfInterestEndpoints:
    """Test cases for POI API endpoints."""

    @pytest.fixture
    def api_client(self) -> APIClient:
        """Create an API client."""
        return APIClient()

    @pytest.fixture
    def user(self) -> User:
        """Create a test user."""
        return User.objects.create_user(
            email="testuser@example.com",
            password="testpass123",  # noqa: S106
        )

    @pytest.fixture
    def other_user(self) -> User:
        """Create another test user."""
        return User.objects.create_user(
            email="otheruser@example.com",
            password="otherpass123",  # noqa: S106
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

    # List endpoint tests
    def test_list_pois_unauthenticated(
        self, api_client: APIClient, poi: PointOfInterest
    ) -> None:
        """Test listing POIs without authentication (should work - read-only)."""
        url = reverse("api:v1:pois")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_list_pois_authenticated(
        self, api_client: APIClient, user: User, poi: PointOfInterest
    ) -> None:
        """Test listing POIs with authentication."""
        api_client.force_authenticate(user=user)
        url = reverse("api:v1:pois")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert len(data["data"]["pois"]) == 1

    def test_list_pois_empty(self, api_client: APIClient, user: User) -> None:
        """Test listing POIs when none exist."""
        api_client.force_authenticate(user=user)
        url = reverse("api:v1:pois")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert len(data["data"]["pois"]) == 0

    def test_list_pois_multiple(self, api_client: APIClient, user: User) -> None:
        """Test listing multiple POIs."""
        # Create multiple POIs
        for i in range(3):
            PointOfInterest.objects.create(
                name=f"POI {i}",
                latitude=45.0 + i,
                longitude=-122.0 + i,
                created_by=user,
            )

        api_client.force_authenticate(user=user)
        url = reverse("api:v1:pois")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["data"]["pois"]) == 3  # noqa: PLR2004

    # Retrieve endpoint tests
    def test_retrieve_poi_unauthenticated(
        self, api_client: APIClient, poi: PointOfInterest
    ) -> None:
        """Test retrieving a single POI without authentication (should work)."""
        url = reverse("api:v1:poi-detail", kwargs={"id": poi.id})
        response = api_client.get(url)

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_retrieve_poi_authenticated(
        self, api_client: APIClient, user: User, poi: PointOfInterest
    ) -> None:
        """Test retrieving a single POI with authentication."""
        api_client.force_authenticate(user=user)
        url = reverse("api:v1:poi-detail", kwargs={"id": poi.id})
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["data"]["poi"]["created_by"] == "testuser@example.com"

    def test_retrieve_poi_not_found(self, api_client: APIClient, user: User) -> None:
        """Test retrieving a non-existent POI."""
        fake_uuid = uuid.uuid4()
        api_client.force_authenticate(user=user)
        url = reverse("api:v1:poi-detail", kwargs={"id": fake_uuid})
        response = api_client.get(url)

        assert response.status_code == status.HTTP_404_NOT_FOUND
        data = response.json()
        assert data["success"] is False

    # Create endpoint tests
    def test_create_poi_unauthenticated(self, api_client: APIClient) -> None:
        """Test creating a POI without authentication (should fail)."""
        url = reverse("api:v1:pois")
        data = {
            "name": "New POI",
            "latitude": "45.0",
            "longitude": "-122.0",
        }

        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_create_poi_authenticated(self, api_client: APIClient, user: User) -> None:
        """Test creating a POI with authentication."""
        api_client.force_authenticate(user=user)
        url = reverse("api:v1:pois")
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
        assert response_data["data"]["poi"]["created_by"] == "testuser@example.com"

        # Verify POI was created in database
        poi = PointOfInterest.objects.get(name="New POI")
        assert poi.created_by == user

    def test_create_poi_minimal_data(self, api_client: APIClient, user: User) -> None:
        """Test creating a POI with minimal data."""
        api_client.force_authenticate(user=user)
        url = reverse("api:v1:pois")
        data = {
            "name": "Minimal POI",
            "latitude": "0.0",
            "longitude": "0.0",
        }

        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        poi = PointOfInterest.objects.get(name="Minimal POI")
        assert poi.description == ""

    def test_create_poi_invalid_latitude(
        self, api_client: APIClient, user: User
    ) -> None:
        """Test creating a POI with invalid latitude."""
        api_client.force_authenticate(user=user)
        url = reverse("api:v1:pois")
        data = {
            "name": "Invalid POI",
            "latitude": "91.0",  # Invalid - > 90
            "longitude": "0.0",
        }

        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        response_data = response.json()
        assert "latitude" in response_data["errors"]

    def test_create_poi_invalid_longitude(
        self, api_client: APIClient, user: User
    ) -> None:
        """Test creating a POI with invalid longitude."""
        api_client.force_authenticate(user=user)
        url = reverse("api:v1:pois")
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
    def test_update_poi_unauthenticated(
        self, api_client: APIClient, poi: PointOfInterest
    ) -> None:
        """Test updating a POI without authentication (should fail)."""
        url = reverse("api:v1:poi-detail", kwargs={"id": poi.id})
        data = {"name": "Updated POI"}

        response = api_client.patch(url, data, format="json")

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_update_poi_as_creator(
        self, api_client: APIClient, user: User, poi: PointOfInterest
    ) -> None:
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

    def test_update_poi_as_other_user(
        self, api_client: APIClient, other_user: User, poi: PointOfInterest
    ) -> None:
        """Test updating a POI as a different user (should succeed - any authenticated
        user can update)."""

        test_new_description = "Updated by another user"

        api_client.force_authenticate(user=other_user)
        url = reverse("api:v1:poi-detail", kwargs={"id": poi.id})
        data = {"description": test_new_description}

        response = api_client.patch(url, data, format="json")

        assert response.status_code == status.HTTP_403_FORBIDDEN
        poi.refresh_from_db()
        assert poi.description != test_new_description

    def test_update_poi_coordinates(
        self, api_client: APIClient, user: User, poi: PointOfInterest
    ) -> None:
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
        assert poi.latitude == 48.0  # noqa: PLR2004
        assert poi.longitude == -123.0  # noqa: PLR2004

    def test_update_poi_invalid_data(
        self, api_client: APIClient, user: User, poi: PointOfInterest
    ) -> None:
        """Test updating POI with invalid data."""
        api_client.force_authenticate(user=user)
        url = reverse("api:v1:poi-detail", kwargs={"id": poi.id})
        data = {"latitude": "invalid"}

        response = api_client.patch(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    # Delete endpoint tests
    def test_delete_poi_unauthenticated(
        self, api_client: APIClient, poi: PointOfInterest
    ) -> None:
        """Test deleting a POI without authentication (should fail)."""
        url = reverse("api:v1:poi-detail", kwargs={"id": poi.id})
        response = api_client.delete(url)

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_delete_poi_as_creator(
        self, api_client: APIClient, user: User, poi: PointOfInterest
    ) -> None:
        """Test deleting a POI as the creator."""
        api_client.force_authenticate(user=user)
        url = reverse("api:v1:poi-detail", kwargs={"id": poi.id})
        response = api_client.delete(url)

        assert response.status_code == status.HTTP_200_OK

        # Verify POI was deleted
        assert not PointOfInterest.objects.filter(id=poi.id).exists()

    def test_delete_poi_as_other_user(
        self, api_client: APIClient, other_user: User, poi: PointOfInterest
    ) -> None:
        """Test deleting a POI as a different user (should succeed - any authenticated
        user can delete)."""
        api_client.force_authenticate(user=other_user)
        url = reverse("api:v1:poi-detail", kwargs={"id": poi.id})
        response = api_client.delete(url)

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_delete_poi_not_found(self, api_client: APIClient, user: User) -> None:
        """Test deleting a non-existent POI."""
        api_client.force_authenticate(user=user)
        url = reverse("api:v1:poi-detail", kwargs={"id": uuid.uuid4()})
        response = api_client.delete(url)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    # Map endpoint tests
    def test_geojson_endpoint_unauthenticated(
        self, api_client: APIClient, user: User
    ) -> None:
        """Test geojson endpoint without authentication (should work)."""
        # Create POIs with different properties
        PointOfInterest.objects.create(
            name="POI 1",
            description="Description 1",
            latitude=45.0,
            longitude=-122.0,
            created_by=user,
        )
        PointOfInterest.objects.create(
            name="POI 2",
            latitude=46.0,
            longitude=-123.0,
            created_by=user,  # Using the same user
        )

        url = reverse("api:v1:pois-geojson")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_geojson_endpoint_empty(self, api_client: APIClient, user: User) -> None:
        """Test geojson endpoint with no POIs."""
        api_client.force_authenticate(user=user)
        url = reverse("api:v1:pois-geojson")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["data"]["type"] == "FeatureCollection"
        assert len(data["data"]["features"]) == 0

    def test_geojson_endpoint_coordinate_format(
        self, api_client: APIClient, poi: PointOfInterest, user: User
    ) -> None:
        """Test that geojson endpoint returns coordinates in correct GeoJSON format."""
        api_client.force_authenticate(user=user)
        url = reverse("api:v1:pois-geojson")
        response = api_client.get(url)

        data = response.json()
        feature = data["data"]["features"][0]
        coordinates = feature["geometry"]["coordinates"]

        # GeoJSON format is [longitude, latitude]
        assert coordinates[0] == -122.654321  # longitude  # noqa: PLR2004
        assert coordinates[1] == 45.123456  # latitude  # noqa: PLR2004

    # Edge cases and error handling
    def test_invalid_http_methods(
        self, api_client: APIClient, poi: PointOfInterest
    ) -> None:
        """Test invalid HTTP methods return appropriate errors."""
        # Test PUT on list endpoint (should not be allowed)
        url = reverse("api:v1:pois")
        response = api_client.put(url, {}, format="json")
        assert response.status_code == status.HTTP_403_FORBIDDEN  # No auth provided

    def test_coordinate_precision_in_responses(
        self, api_client: APIClient, user: User
    ) -> None:
        """Test that coordinates maintain proper precision in API responses."""
        api_client.force_authenticate(user=user)

        # Create POI with precise coordinates
        url = reverse("api:v1:pois")
        data = {
            "name": "Precise POI",
            "latitude": "45.1234567",
            "longitude": "-122.7654321",
        }

        response = api_client.post(url, data, format="json")
        assert response.status_code == status.HTTP_201_CREATED

        # Check response maintains 7 decimal places
        poi_data = response.json()["data"]["poi"]
        assert poi_data["latitude"] == 45.1234567  # noqa: PLR2004
        assert poi_data["longitude"] == -122.7654321  # noqa: PLR2004
