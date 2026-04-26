"""Tests for Landmark API endpoints."""

from __future__ import annotations

import uuid

import pytest
from django.db import transaction
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from speleodb.common.enums import PermissionLevel
from speleodb.gis.landmark_collections import get_or_create_personal_landmark_collection
from speleodb.gis.models import Landmark
from speleodb.gis.models import LandmarkCollection
from speleodb.gis.models import LandmarkCollectionUserPermission
from speleodb.users.models import User


@pytest.mark.django_db
class TestLandmarkEndpoints:
    """Test cases for Landmark API endpoints."""

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
    def landmark(self, user: User) -> Landmark:
        """Create a test Landmark."""
        personal_collection = get_or_create_personal_landmark_collection(user=user)
        return Landmark.objects.create(
            name="Test Landmark",
            description="Test description",
            latitude=45.123456,
            longitude=-122.654321,
            created_by=user.email,
            collection=personal_collection,
        )

    # List endpoint tests
    def test_list_landmarks_unauthenticated(
        self, api_client: APIClient, landmark: Landmark
    ) -> None:
        """Test listing Landmarks without authentication (should work - read-only)."""
        url = reverse("api:v2:landmarks")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_list_landmarks_authenticated(
        self, api_client: APIClient, user: User, landmark: Landmark
    ) -> None:
        """Test listing Landmarks with authentication."""
        api_client.force_authenticate(user=user)
        url = reverse("api:v2:landmarks")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["landmarks"]) == 1

    def test_list_landmarks_empty(self, api_client: APIClient, user: User) -> None:
        """Test listing Landmarks when none exist."""
        api_client.force_authenticate(user=user)
        url = reverse("api:v2:landmarks")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["landmarks"]) == 0

    def test_list_landmarks_multiple(self, api_client: APIClient, user: User) -> None:
        """Test listing multiple Landmarks."""
        personal_collection = get_or_create_personal_landmark_collection(user=user)
        # Create multiple Landmarks
        for i in range(3):
            Landmark.objects.create(
                name=f"Landmark {i}",
                latitude=45.0 + i,
                longitude=-122.0 + i,
                created_by=user.email,
                collection=personal_collection,
            )

        api_client.force_authenticate(user=user)
        url = reverse("api:v2:landmarks")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["landmarks"]) == 3  # noqa: PLR2004

    # Retrieve endpoint tests
    def test_retrieve_landmark_unauthenticated(
        self, api_client: APIClient, landmark: Landmark
    ) -> None:
        """Test retrieving a single Landmark without authentication (should work)."""
        url = reverse("api:v2:landmark-detail", kwargs={"id": landmark.id})
        response = api_client.get(url)

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_retrieve_landmark_authenticated(
        self, api_client: APIClient, user: User, landmark: Landmark
    ) -> None:
        """Test retrieving a single Landmark with authentication."""
        api_client.force_authenticate(user=user)
        url = reverse("api:v2:landmark-detail", kwargs={"id": landmark.id})
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["landmark"]["created_by"] == "testuser@example.com"
        assert "user" not in data["landmark"]

    def test_retrieve_landmark_not_found(
        self, api_client: APIClient, user: User
    ) -> None:
        """Test retrieving a non-existent Landmark."""
        fake_uuid = uuid.uuid4()
        api_client.force_authenticate(user=user)
        url = reverse("api:v2:landmark-detail", kwargs={"id": fake_uuid})
        response = api_client.get(url)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    # Create endpoint tests
    def test_create_landmark_unauthenticated(self, api_client: APIClient) -> None:
        """Test creating a Landmark without authentication (should fail)."""
        url = reverse("api:v2:landmarks")
        data = {
            "name": "New Landmark",
            "latitude": "45.0",
            "longitude": "-122.0",
        }

        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_create_landmark_authenticated(
        self, api_client: APIClient, user: User
    ) -> None:
        """Test creating a Landmark with authentication."""
        api_client.force_authenticate(user=user)
        url = reverse("api:v2:landmarks")
        data = {
            "name": "New Landmark",
            "description": "New description",
            "latitude": "47.608013",
            "longitude": "-122.335167",
        }

        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        response_data = response.json()
        assert response_data["landmark"]["name"] == "New Landmark"
        assert response_data["landmark"]["created_by"] == "testuser@example.com"
        assert "user" not in response_data["landmark"]

        # Verify Landmark was created in database
        landmark = Landmark.objects.get(name="New Landmark")
        assert landmark.created_by == user.email
        assert landmark.collection == get_or_create_personal_landmark_collection(
            user=user
        )

    def test_create_landmark_minimal_data(
        self, api_client: APIClient, user: User
    ) -> None:
        """Test creating a Landmark with minimal data."""
        api_client.force_authenticate(user=user)
        url = reverse("api:v2:landmarks")
        data = {
            "name": "Minimal Landmark",
            "latitude": "0.0",
            "longitude": "0.0",
        }

        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        landmark = Landmark.objects.get(name="Minimal Landmark")
        assert landmark.description == ""
        assert landmark.collection.is_personal

    def test_create_landmark_missing_latitude(
        self, api_client: APIClient, user: User
    ) -> None:
        """Test creating a Landmark without latitude returns 400."""
        api_client.force_authenticate(user=user)
        url = reverse("api:v2:landmarks")
        data = {
            "name": "No Lat Landmark",
            "longitude": "-122.0",
        }

        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        response_data = response.json()
        assert "latitude" in response_data["errors"]

    def test_create_landmark_missing_longitude(
        self, api_client: APIClient, user: User
    ) -> None:
        """Test creating a Landmark without longitude returns 400."""
        api_client.force_authenticate(user=user)
        url = reverse("api:v2:landmarks")
        data = {
            "name": "No Long Landmark",
            "latitude": "45.0",
        }

        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        response_data = response.json()
        assert "longitude" in response_data["errors"]

    def test_create_landmark_duplicate_location_same_user(
        self, api_client: APIClient, user: User, landmark: Landmark
    ) -> None:
        """Test creating a second Landmark at the same coordinates for the same user
        returns 400."""
        api_client.force_authenticate(user=user)
        url = reverse("api:v2:landmarks")
        data = {
            "name": "Duplicate Location",
            "latitude": str(landmark.latitude),
            "longitude": str(landmark.longitude),
        }

        with transaction.atomic():
            response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        response_data = response.json()
        assert "error" in response_data
        assert "already exists" in response_data["error"]

    def test_create_landmark_invalid_latitude(
        self, api_client: APIClient, user: User
    ) -> None:
        """Test creating a Landmark with invalid latitude."""
        api_client.force_authenticate(user=user)
        url = reverse("api:v2:landmarks")
        data = {
            "name": "Invalid Landmark",
            "latitude": "91.0",  # Invalid - > 90
            "longitude": "0.0",
        }

        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        response_data = response.json()
        assert "latitude" in response_data["errors"]

    def test_create_landmark_invalid_longitude(
        self, api_client: APIClient, user: User
    ) -> None:
        """Test creating a Landmark with invalid longitude."""
        api_client.force_authenticate(user=user)
        url = reverse("api:v2:landmarks")
        data = {
            "name": "Invalid Landmark",
            "latitude": "0.0",
            "longitude": "181.0",  # Invalid - > 180
        }

        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        response_data = response.json()
        assert "longitude" in response_data["errors"]

    # Update endpoint tests
    def test_update_landmark_unauthenticated(
        self, api_client: APIClient, landmark: Landmark
    ) -> None:
        """Test updating a Landmark without authentication (should fail)."""
        url = reverse("api:v2:landmark-detail", kwargs={"id": landmark.id})
        data = {"name": "Updated Landmark"}

        response = api_client.patch(url, data, format="json")

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_update_landmark_as_creator(
        self, api_client: APIClient, user: User, landmark: Landmark
    ) -> None:
        """Test updating a Landmark as the creator."""
        api_client.force_authenticate(user=user)
        url = reverse("api:v2:landmark-detail", kwargs={"id": landmark.id})
        data = {
            "name": "Updated Landmark",
            "description": "Updated description",
        }

        response = api_client.patch(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        response_data = response.json()
        assert response_data["landmark"]["name"] == "Updated Landmark"
        assert response_data["landmark"]["description"] == "Updated description"

        # Verify in database
        landmark.refresh_from_db()
        assert landmark.name == "Updated Landmark"

    def test_update_landmark_as_other_user(
        self, api_client: APIClient, other_user: User, landmark: Landmark
    ) -> None:
        """Test updating a Landmark as a different user."""

        test_new_description = "Updated by another user"

        api_client.force_authenticate(user=other_user)
        url = reverse("api:v2:landmark-detail", kwargs={"id": landmark.id})
        data = {"description": test_new_description}

        response = api_client.patch(url, data, format="json")

        assert response.status_code == status.HTTP_403_FORBIDDEN
        landmark.refresh_from_db()
        assert landmark.description != test_new_description

    def test_update_landmark_coordinates(
        self, api_client: APIClient, user: User, landmark: Landmark
    ) -> None:
        """Test updating Landmark coordinates."""
        api_client.force_authenticate(user=user)
        url = reverse("api:v2:landmark-detail", kwargs={"id": landmark.id})
        data = {
            "latitude": "48.0",
            "longitude": "-123.0",
        }

        response = api_client.patch(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        landmark.refresh_from_db()
        assert landmark.latitude == 48.0  # noqa: PLR2004
        assert landmark.longitude == -123.0  # noqa: PLR2004

    def test_update_landmark_duplicate_collection_coordinates_returns_400(
        self,
        api_client: APIClient,
        user: User,
        landmark: Landmark,
    ) -> None:
        """Moving onto an occupied collection coordinate should not 500."""
        Landmark.objects.create(
            name="Already There",
            latitude=46.0,
            longitude=-123.0,
            created_by=user.email,
            collection=landmark.collection,
        )

        api_client.force_authenticate(user=user)
        response = api_client.patch(
            reverse("api:v2:landmark-detail", kwargs={"id": landmark.id}),
            {
                "latitude": "46.0",
                "longitude": "-123.0",
            },
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "already exists" in response.json()["error"]
        landmark.refresh_from_db()
        assert landmark.latitude != 46.0  # noqa: PLR2004
        assert landmark.longitude != -123.0  # noqa: PLR2004

    def test_update_landmark_invalid_data(
        self, api_client: APIClient, user: User, landmark: Landmark
    ) -> None:
        """Test updating Landmark with invalid data."""
        api_client.force_authenticate(user=user)
        url = reverse("api:v2:landmark-detail", kwargs={"id": landmark.id})
        data = {"latitude": "invalid"}

        response = api_client.patch(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    # Delete endpoint tests
    def test_delete_landmark_unauthenticated(
        self, api_client: APIClient, landmark: Landmark
    ) -> None:
        """Test deleting a Landmark without authentication (should fail)."""
        url = reverse("api:v2:landmark-detail", kwargs={"id": landmark.id})
        response = api_client.delete(url)

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_delete_landmark_as_creator(
        self, api_client: APIClient, user: User, landmark: Landmark
    ) -> None:
        """Test deleting a Landmark as the creator."""
        api_client.force_authenticate(user=user)
        url = reverse("api:v2:landmark-detail", kwargs={"id": landmark.id})
        response = api_client.delete(url)

        assert response.status_code == status.HTTP_200_OK

        # Verify Landmark was deleted
        assert not Landmark.objects.filter(id=landmark.id).exists()

    def test_delete_landmark_as_other_user(
        self, api_client: APIClient, other_user: User, landmark: Landmark
    ) -> None:
        """Test deleting a Landmark as a different user."""
        api_client.force_authenticate(user=other_user)
        url = reverse("api:v2:landmark-detail", kwargs={"id": landmark.id})
        response = api_client.delete(url)

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_delete_landmark_not_found(self, api_client: APIClient, user: User) -> None:
        """Test deleting a non-existent Landmark."""
        api_client.force_authenticate(user=user)
        url = reverse("api:v2:landmark-detail", kwargs={"id": uuid.uuid4()})
        response = api_client.delete(url)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    # Map endpoint tests
    def test_geojson_endpoint_unauthenticated(
        self, api_client: APIClient, user: User
    ) -> None:
        """Test geojson endpoint without authentication (should work)."""
        personal_collection = get_or_create_personal_landmark_collection(user=user)
        # Create Landmarks with different properties
        Landmark.objects.create(
            name="Landmark 1",
            description="Description 1",
            latitude=45.0,
            longitude=-122.0,
            created_by=user.email,
            collection=personal_collection,
        )
        Landmark.objects.create(
            name="Landmark 2",
            latitude=46.0,
            longitude=-123.0,
            created_by=user.email,
            collection=personal_collection,
        )

        url = reverse("api:v2:landmarks-geojson")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_geojson_endpoint_empty(self, api_client: APIClient, user: User) -> None:
        """Test geojson endpoint with no Landmarks."""
        api_client.force_authenticate(user=user)
        url = reverse("api:v2:landmarks-geojson")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["type"] == "FeatureCollection"
        assert len(data["features"]) == 0

    def test_geojson_endpoint_coordinate_format(
        self, api_client: APIClient, landmark: Landmark, user: User
    ) -> None:
        """Test that geojson endpoint returns coordinates in correct GeoJSON format."""
        api_client.force_authenticate(user=user)
        url = reverse("api:v2:landmarks-geojson")
        response = api_client.get(url)

        data = response.json()
        feature = data["features"][0]
        coordinates = feature["geometry"]["coordinates"]

        # GeoJSON format is [longitude, latitude]
        assert coordinates[0] == -122.654321  # longitude  # noqa: PLR2004
        assert coordinates[1] == 45.123456  # latitude  # noqa: PLR2004

    # Edge cases and error handling
    def test_invalid_http_methods(
        self, api_client: APIClient, landmark: Landmark
    ) -> None:
        """Test invalid HTTP methods return appropriate errors."""
        # Test PUT on list endpoint (should not be allowed)
        url = reverse("api:v2:landmarks")
        response = api_client.put(url, {}, format="json")
        assert response.status_code == status.HTTP_403_FORBIDDEN  # No auth provided

    def test_coordinate_precision_in_responses(
        self, api_client: APIClient, user: User
    ) -> None:
        """Test that coordinates maintain proper precision in API responses."""
        api_client.force_authenticate(user=user)

        # Create Landmark with precise coordinates
        url = reverse("api:v2:landmarks")
        data = {
            "name": "Precise Landmark",
            "latitude": "45.1234567",
            "longitude": "-122.7654321",
        }

        response = api_client.post(url, data, format="json")
        assert response.status_code == status.HTTP_201_CREATED

        # Check response maintains 7 decimal places
        landmark_data = response.json()["landmark"]
        assert landmark_data["latitude"] == 45.1234567  # noqa: PLR2004
        assert landmark_data["longitude"] == -122.7654321  # noqa: PLR2004


@pytest.mark.django_db
class TestBulkTransfer:
    """Tests for POST /landmark-collections/<id>/landmarks/transfer/."""

    @pytest.fixture
    def api_client(self) -> APIClient:
        return APIClient()

    @pytest.fixture
    def owner(self) -> User:
        return User.objects.create_user(
            email="owner@example.com",
            password="pass",  # noqa: S106
        )

    @pytest.fixture
    def other_user(self) -> User:
        return User.objects.create_user(
            email="other@example.com",
            password="pass",  # noqa: S106
        )

    @pytest.fixture
    def source(self, owner: User) -> LandmarkCollection:
        c = LandmarkCollection.objects.create(name="Source", created_by=owner.email)
        LandmarkCollectionUserPermission.objects.create(
            collection=c, user=owner, level=PermissionLevel.ADMIN
        )
        return c

    @pytest.fixture
    def target(self, owner: User) -> LandmarkCollection:
        c = LandmarkCollection.objects.create(name="Target", created_by=owner.email)
        LandmarkCollectionUserPermission.objects.create(
            collection=c, user=owner, level=PermissionLevel.READ_AND_WRITE
        )
        return c

    @pytest.fixture
    def landmarks(self, owner: User, source: LandmarkCollection) -> list[Landmark]:
        return [
            Landmark.objects.create(
                name=f"LM-{i}",
                latitude=45 + i,
                longitude=-122 + i,
                created_by=owner.email,
                collection=source,
            )
            for i in range(3)
        ]

    def _url(self, collection_id: uuid.UUID | str) -> str:
        return reverse(
            "api:v2:landmark-collection-landmarks-transfer",
            kwargs={"collection_id": collection_id},
        )

    def test_happy_path(
        self,
        api_client: APIClient,
        owner: User,
        source: LandmarkCollection,
        target: LandmarkCollection,
        landmarks: list[Landmark],
    ) -> None:
        api_client.force_authenticate(user=owner)
        ids = [str(lm.id) for lm in landmarks]
        response = api_client.post(
            self._url(source.id),
            {"landmark_ids": ids, "target_collection": str(target.id)},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["transferred"] == 3  # noqa: PLR2004
        assert data["target_collection"]["id"] == str(target.id)
        assert data["target_collection"]["name"] == "Target"
        for lm in landmarks:
            lm.refresh_from_db()
            assert lm.collection_id == target.id

    def test_read_only_user_on_source_gets_403(
        self,
        api_client: APIClient,
        other_user: User,
        source: LandmarkCollection,
        target: LandmarkCollection,
        landmarks: list[Landmark],
    ) -> None:
        LandmarkCollectionUserPermission.objects.create(
            collection=source,
            user=other_user,
            level=PermissionLevel.READ_ONLY,
        )
        api_client.force_authenticate(user=other_user)
        response = api_client.post(
            self._url(source.id),
            {
                "landmark_ids": [str(landmarks[0].id)],
                "target_collection": str(target.id),
            },
            format="json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_read_only_user_on_target_gets_403(
        self,
        api_client: APIClient,
        owner: User,
        other_user: User,
        source: LandmarkCollection,
        landmarks: list[Landmark],
    ) -> None:
        read_target = LandmarkCollection.objects.create(
            name="ReadOnly Target", created_by=owner.email
        )
        LandmarkCollectionUserPermission.objects.create(
            collection=source,
            user=other_user,
            level=PermissionLevel.READ_AND_WRITE,
        )
        LandmarkCollectionUserPermission.objects.create(
            collection=read_target,
            user=other_user,
            level=PermissionLevel.READ_ONLY,
        )
        api_client.force_authenticate(user=other_user)
        response = api_client.post(
            self._url(source.id),
            {
                "landmark_ids": [str(landmarks[0].id)],
                "target_collection": str(read_target.id),
            },
            format="json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_empty_landmark_ids_returns_400(
        self,
        api_client: APIClient,
        owner: User,
        source: LandmarkCollection,
        target: LandmarkCollection,
    ) -> None:
        api_client.force_authenticate(user=owner)
        response = api_client.post(
            self._url(source.id),
            {"landmark_ids": [], "target_collection": str(target.id)},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_missing_target_collection_returns_400(
        self,
        api_client: APIClient,
        owner: User,
        source: LandmarkCollection,
        landmarks: list[Landmark],
    ) -> None:
        api_client.force_authenticate(user=owner)
        response = api_client.post(
            self._url(source.id),
            {"landmark_ids": [str(landmarks[0].id)]},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_transfer_to_same_collection_returns_400(
        self,
        api_client: APIClient,
        owner: User,
        source: LandmarkCollection,
        landmarks: list[Landmark],
    ) -> None:
        api_client.force_authenticate(user=owner)
        response = api_client.post(
            self._url(source.id),
            {
                "landmark_ids": [str(landmarks[0].id)],
                "target_collection": str(source.id),
            },
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_nonexistent_target_returns_404(
        self,
        api_client: APIClient,
        owner: User,
        source: LandmarkCollection,
        landmarks: list[Landmark],
    ) -> None:
        api_client.force_authenticate(user=owner)
        response = api_client.post(
            self._url(source.id),
            {
                "landmark_ids": [str(landmarks[0].id)],
                "target_collection": str(uuid.uuid4()),
            },
            format="json",
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_landmark_ids_not_in_source_returns_400(
        self,
        api_client: APIClient,
        owner: User,
        source: LandmarkCollection,
        target: LandmarkCollection,
    ) -> None:
        api_client.force_authenticate(user=owner)
        response = api_client.post(
            self._url(source.id),
            {
                "landmark_ids": [str(uuid.uuid4())],
                "target_collection": str(target.id),
            },
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_partial_invalid_ids_rejects_entire_request(
        self,
        api_client: APIClient,
        owner: User,
        source: LandmarkCollection,
        target: LandmarkCollection,
        landmarks: list[Landmark],
    ) -> None:
        api_client.force_authenticate(user=owner)
        mixed_ids = [str(landmarks[0].id), str(uuid.uuid4())]
        response = api_client.post(
            self._url(source.id),
            {"landmark_ids": mixed_ids, "target_collection": str(target.id)},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        landmarks[0].refresh_from_db()
        assert landmarks[0].collection_id == source.id

    def test_personal_collection_as_target(
        self,
        api_client: APIClient,
        owner: User,
        source: LandmarkCollection,
        landmarks: list[Landmark],
    ) -> None:
        personal = get_or_create_personal_landmark_collection(user=owner)
        api_client.force_authenticate(user=owner)
        response = api_client.post(
            self._url(source.id),
            {
                "landmark_ids": [str(landmarks[0].id)],
                "target_collection": str(personal.id),
            },
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        landmarks[0].refresh_from_db()
        assert landmarks[0].collection_id == personal.id

    def test_duplicate_landmark_ids_are_deduplicated(
        self,
        api_client: APIClient,
        owner: User,
        source: LandmarkCollection,
        target: LandmarkCollection,
        landmarks: list[Landmark],
    ) -> None:
        api_client.force_authenticate(user=owner)
        dup_id = str(landmarks[0].id)
        response = api_client.post(
            self._url(source.id),
            {
                "landmark_ids": [dup_id, dup_id, dup_id],
                "target_collection": str(target.id),
            },
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["transferred"] == 1
        landmarks[0].refresh_from_db()
        assert landmarks[0].collection_id == target.id

    def test_unauthenticated_returns_403(
        self,
        api_client: APIClient,
        source: LandmarkCollection,
        landmarks: list[Landmark],
    ) -> None:
        response = api_client.post(
            self._url(source.id),
            {
                "landmark_ids": [str(landmarks[0].id)],
                "target_collection": str(uuid.uuid4()),
            },
            format="json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestBulkDelete:
    """Tests for POST /landmark-collections/<id>/landmarks/bulk_delete/."""

    @pytest.fixture
    def api_client(self) -> APIClient:
        return APIClient()

    @pytest.fixture
    def owner(self) -> User:
        return User.objects.create_user(
            email="delowner@example.com",
            password="pass",  # noqa: S106
        )

    @pytest.fixture
    def reader_user(self) -> User:
        return User.objects.create_user(
            email="delreader@example.com",
            password="pass",  # noqa: S106
        )

    @pytest.fixture
    def collection(self, owner: User) -> LandmarkCollection:
        c = LandmarkCollection.objects.create(
            name="Delete Collection", created_by=owner.email
        )
        LandmarkCollectionUserPermission.objects.create(
            collection=c, user=owner, level=PermissionLevel.ADMIN
        )
        return c

    @pytest.fixture
    def landmarks(self, owner: User, collection: LandmarkCollection) -> list[Landmark]:
        return [
            Landmark.objects.create(
                name=f"Del-{i}",
                latitude=45 + i,
                longitude=-122 + i,
                created_by=owner.email,
                collection=collection,
            )
            for i in range(3)
        ]

    def _url(self, collection_id: uuid.UUID | str) -> str:
        return reverse(
            "api:v2:landmark-collection-landmarks-bulk-delete",
            kwargs={"collection_id": collection_id},
        )

    def test_happy_path(
        self,
        api_client: APIClient,
        owner: User,
        collection: LandmarkCollection,
        landmarks: list[Landmark],
    ) -> None:
        api_client.force_authenticate(user=owner)
        ids = [str(lm.id) for lm in landmarks]
        response = api_client.post(
            self._url(collection.id),
            {"landmark_ids": ids},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["deleted"] == 3  # noqa: PLR2004
        assert Landmark.objects.filter(id__in=ids).count() == 0

    def test_read_only_user_gets_403(
        self,
        api_client: APIClient,
        reader_user: User,
        collection: LandmarkCollection,
        landmarks: list[Landmark],
    ) -> None:
        LandmarkCollectionUserPermission.objects.create(
            collection=collection,
            user=reader_user,
            level=PermissionLevel.READ_ONLY,
        )
        api_client.force_authenticate(user=reader_user)
        response = api_client.post(
            self._url(collection.id),
            {"landmark_ids": [str(landmarks[0].id)]},
            format="json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_empty_landmark_ids_returns_400(
        self,
        api_client: APIClient,
        owner: User,
        collection: LandmarkCollection,
    ) -> None:
        api_client.force_authenticate(user=owner)
        response = api_client.post(
            self._url(collection.id),
            {"landmark_ids": []},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_ids_not_in_collection_returns_400(
        self,
        api_client: APIClient,
        owner: User,
        collection: LandmarkCollection,
    ) -> None:
        api_client.force_authenticate(user=owner)
        response = api_client.post(
            self._url(collection.id),
            {"landmark_ids": [str(uuid.uuid4())]},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_partial_invalid_ids_rejects_entire_request(
        self,
        api_client: APIClient,
        owner: User,
        collection: LandmarkCollection,
        landmarks: list[Landmark],
    ) -> None:
        api_client.force_authenticate(user=owner)
        mixed_ids = [str(landmarks[0].id), str(uuid.uuid4())]
        response = api_client.post(
            self._url(collection.id),
            {"landmark_ids": mixed_ids},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert Landmark.objects.filter(id=landmarks[0].id).exists()

    def test_personal_collection_delete(
        self,
        api_client: APIClient,
        owner: User,
    ) -> None:
        personal = get_or_create_personal_landmark_collection(user=owner)
        lm = Landmark.objects.create(
            name="Personal LM",
            latitude=45,
            longitude=-122,
            created_by=owner.email,
            collection=personal,
        )
        api_client.force_authenticate(user=owner)
        response = api_client.post(
            self._url(personal.id),
            {"landmark_ids": [str(lm.id)]},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["deleted"] == 1
        assert not Landmark.objects.filter(id=lm.id).exists()

    def test_duplicate_landmark_ids_are_deduplicated(
        self,
        api_client: APIClient,
        owner: User,
        collection: LandmarkCollection,
        landmarks: list[Landmark],
    ) -> None:
        api_client.force_authenticate(user=owner)
        dup_id = str(landmarks[0].id)
        response = api_client.post(
            self._url(collection.id),
            {"landmark_ids": [dup_id, dup_id, dup_id]},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["deleted"] == 1
        assert not Landmark.objects.filter(id=landmarks[0].id).exists()

    def test_unauthenticated_returns_403(
        self,
        api_client: APIClient,
        collection: LandmarkCollection,
        landmarks: list[Landmark],
    ) -> None:
        response = api_client.post(
            self._url(collection.id),
            {"landmark_ids": [str(landmarks[0].id)]},
            format="json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN
