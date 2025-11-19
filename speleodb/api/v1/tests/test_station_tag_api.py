"""Tests for StationTag API endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from speleodb.api.v1.tests.factories import ProjectFactory
from speleodb.api.v1.tests.factories import StationFactory
from speleodb.common.enums import PermissionLevel
from speleodb.gis.models import StationTag
from speleodb.gis.models.station import Station
from speleodb.surveys.models import UserProjectPermission
from speleodb.users.models.user import User
from speleodb.users.tests.factories import UserFactory

if TYPE_CHECKING:
    from speleodb.gis.models.station import Station
    from speleodb.surveys.models.project import Project
    from speleodb.users.models.user import User


@pytest.mark.django_db
class TestStationTagAPI:
    """Test cases for StationTag API endpoints."""

    @pytest.fixture
    def api_client(self) -> APIClient:
        """Create an API client."""
        return APIClient()

    @pytest.fixture
    def user(self) -> User:
        """Create a test user."""
        return UserFactory.create()

    @pytest.fixture
    def authenticated_client(self, api_client: APIClient, user: User) -> APIClient:
        """Create an authenticated API client."""
        api_client.force_authenticate(user=user)
        return api_client

    @pytest.fixture
    def tag(self, user: User) -> StationTag:
        """Create a test station tag."""
        return StationTag.objects.create(
            name="Testtag",  # After .title() normalization
            color="#ef4444",
            user=user,
        )

    def test_list_user_tags(
        self,
        authenticated_client: APIClient,
        user: User,
        tag: StationTag,
    ) -> None:
        """Test listing all tags for a user."""
        # Create additional tags
        StationTag.objects.create(name="Complete", color="#22c55e", user=user)
        StationTag.objects.create(name="Priority", color="#f97316", user=user)

        url = reverse("api:v1:station-tags")
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["data"]) == 3  # noqa: PLR2004

    def test_list_tags_only_shows_user_tags(
        self,
        authenticated_client: APIClient,
        user: User,
        tag: StationTag,
    ) -> None:
        """Test that users only see their own tags."""
        other_user = UserFactory.create()
        StationTag.objects.create(name="Other Tag", color="#22c55e", user=other_user)

        url = reverse("api:v1:station-tags")
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["data"]) == 1
        assert response.data["data"][0]["name"] == "Testtag"

    def test_create_station_tag(self, authenticated_client: APIClient) -> None:
        """Test creating a new station tag."""
        url = reverse("api:v1:station-tags")
        data = {
            "name": "New Tag",
            "color": "#3b82f6",
        }

        response = authenticated_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["data"]["name"] == "New Tag"
        assert response.data["data"]["color"] == "#3B82F6"  # Uppercase

        # Verify it was created in database
        assert StationTag.objects.filter(name="New Tag").exists()

    def test_create_tag_with_lowercase_name(
        self, authenticated_client: APIClient
    ) -> None:
        """Test that tag names are automatically capitalized."""
        url = reverse("api:v1:station-tags")
        data = {
            "name": "high priority",  # lowercase
            "color": "#3b82f6",
        }

        response = authenticated_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["data"]["name"] == "High Priority"  # Capitalized

    def test_create_tag_with_extra_whitespace(
        self, authenticated_client: APIClient
    ) -> None:
        """Test that tag names are trimmed of whitespace."""
        url = reverse("api:v1:station-tags")
        data = {
            "name": "  active  ",  # Extra whitespace
            "color": "#3b82f6",
        }

        response = authenticated_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["data"]["name"] == "Active"  # Trimmed and capitalized

    def test_create_tag_with_duplicate_name(
        self,
        authenticated_client: APIClient,
        user: User,
    ) -> None:
        """Test that duplicate tag names for same user are rejected."""
        url = reverse("api:v1:station-tags")

        # First create a tag through the API
        data1 = {
            "name": "Duplicate Test",
            "color": "#ef4444",
        }
        response1 = authenticated_client.post(url, data1, format="json")
        assert response1.status_code == status.HTTP_201_CREATED

        # Now try to create another tag with the same name (case-insensitive)
        data2 = {
            "name": "duplicate test",  # Will be normalized to "Duplicate Test"
            "color": "#22c55e",
        }
        response2 = authenticated_client.post(url, data2, format="json")

        assert response2.status_code == status.HTTP_400_BAD_REQUEST
        # The error is now in serializer.errors['name'], not response.error
        assert (
            response2.data["error"]
            == "A tag with the name 'Duplicate Test' already exists for this user."
        )

    def test_create_tag_with_invalid_color(
        self, authenticated_client: APIClient
    ) -> None:
        """Test that invalid colors are rejected."""
        url = reverse("api:v1:station-tags")
        data = {
            "name": "Invalid Color",
            "color": "invalid",
        }

        response = authenticated_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_get_specific_tag(
        self,
        authenticated_client: APIClient,
        tag: StationTag,
    ) -> None:
        """Test getting a specific station tag."""
        url = reverse("api:v1:station-tag-detail", kwargs={"id": tag.id})
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"]["id"] == str(tag.id)
        assert response.data["data"]["name"] == "Testtag"

    def test_update_station_tag(
        self,
        authenticated_client: APIClient,
        tag: StationTag,
    ) -> None:
        """Test updating a station tag."""
        url = reverse("api:v1:station-tag-detail", kwargs={"id": tag.id})
        data = {
            "name": "Updated Tag",
            "color": "#22c55e",
        }

        response = authenticated_client.put(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"]["name"] == "Updated Tag"
        assert response.data["data"]["color"] == "#22C55E"

        # Verify in database
        tag.refresh_from_db()
        assert tag.name == "Updated Tag"

    def test_patch_station_tag(
        self,
        authenticated_client: APIClient,
        tag: StationTag,
    ) -> None:
        """Test partially updating a station tag."""
        url = reverse("api:v1:station-tag-detail", kwargs={"id": tag.id})
        data = {"color": "#22c55e"}

        response = authenticated_client.patch(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"]["name"] == "Testtag"  # Unchanged
        assert response.data["data"]["color"] == "#22C55E"  # Changed

    def test_delete_station_tag(
        self,
        authenticated_client: APIClient,
        tag: StationTag,
    ) -> None:
        """Test deleting a station tag."""
        tag_id = tag.id
        url = reverse("api:v1:station-tag-detail", kwargs={"id": tag_id})

        response = authenticated_client.delete(url)

        assert response.status_code == status.HTTP_200_OK
        assert not StationTag.objects.filter(id=tag_id).exists()

    def test_cannot_access_other_user_tag(
        self,
        authenticated_client: APIClient,
        user: User,
    ) -> None:
        """Test that users cannot access tags from other users."""
        other_user = UserFactory.create()
        other_tag = StationTag.objects.create(
            name="Other Tag",
            color="#22c55e",
            user=other_user,
        )

        url = reverse("api:v1:station-tag-detail", kwargs={"id": other_tag.id})
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_get_predefined_colors(self, authenticated_client: APIClient) -> None:
        """Test getting the list of predefined colors."""
        url = reverse("api:v1:station-tag-colors")
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert "colors" in response.data["data"]
        assert len(response.data["data"]["colors"]) == 20  # noqa: PLR2004
        assert all(color.startswith("#") for color in response.data["data"]["colors"])

    def test_unauthenticated_access_denied(self, api_client: APIClient) -> None:
        """Test that unauthenticated users cannot access tag endpoints."""
        url = reverse("api:v1:station-tags")
        response = api_client.get(url)

        # DRF returns 403 Forbidden for unauthenticated requests
        assert response.status_code in [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        ]


@pytest.mark.django_db
class TestStationTagManagementAPI:
    """Test cases for managing tags on stations."""

    @pytest.fixture
    def api_client(self) -> APIClient:
        """Create an API client."""
        return APIClient()

    @pytest.fixture
    def user(self) -> User:
        """Create a test user."""
        return UserFactory.create()

    @pytest.fixture
    def authenticated_client(self, api_client: APIClient, user: User) -> APIClient:
        """Create an authenticated API client."""
        api_client.force_authenticate(user=user)
        return api_client

    @pytest.fixture
    def project(self, user: User) -> Project:
        """Create a test project with user permissions."""

        project = ProjectFactory.create()
        # Grant user write access to the project (target is the user field)
        UserProjectPermission.objects.create(
            target=user,
            project=project,
            level=PermissionLevel.READ_AND_WRITE,
        )
        return project

    @pytest.fixture
    def station(self, project: Project) -> Station:
        """Create a test station."""
        return StationFactory.create(project=project)

    @pytest.fixture
    def tag(self, user: User) -> StationTag:
        """Create a test station tag."""
        return StationTag.objects.create(
            name="Testtag",  # After .title() normalization
            color="#ef4444",
            user=user,
        )

    def test_get_station_tag(
        self,
        authenticated_client: APIClient,
        station: Station,
        tag: StationTag,
    ) -> None:
        """Test getting the tag assigned to a station."""
        station.tag = tag
        station.save()

        url = reverse("api:v1:station-tags-manage", kwargs={"id": station.id})
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"]["name"] == "Testtag"

    def test_get_station_no_tag(
        self,
        authenticated_client: APIClient,
        station: Station,
    ) -> None:
        """Test getting tag when station has no tag."""
        url = reverse("api:v1:station-tags-manage", kwargs={"id": station.id})
        response = authenticated_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"] is None

    def test_set_tag_on_station(
        self,
        authenticated_client: APIClient,
        station: Station,
        tag: StationTag,
    ) -> None:
        """Test setting a tag on a station."""
        url = reverse("api:v1:station-tags-manage", kwargs={"id": station.id})
        data = {"tag_id": str(tag.id)}

        response = authenticated_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"]["name"] == "Testtag"

        # Verify in database
        station.refresh_from_db()
        assert station.tag == tag

    def test_change_station_tag(
        self,
        authenticated_client: APIClient,
        station: Station,
        user: User,
    ) -> None:
        """Test changing a station's tag."""
        tag1 = StationTag.objects.create(name="Tag1", color="#ef4444", user=user)
        tag2 = StationTag.objects.create(name="Tag2", color="#22c55e", user=user)

        station.tag = tag1
        station.save()

        url = reverse("api:v1:station-tags-manage", kwargs={"id": station.id})
        data = {"tag_id": str(tag2.id)}

        response = authenticated_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"]["name"] == "Tag2"

        # Verify in database
        station.refresh_from_db()
        assert station.tag == tag2

    def test_cannot_set_other_user_tag_on_station(
        self, authenticated_client: APIClient, station: Station
    ) -> None:
        """Test that users cannot set tags from other users on stations."""
        other_user = UserFactory.create()
        other_tag = StationTag.objects.create(
            name="Other Tag",
            color="#22c55e",
            user=other_user,
        )

        url = reverse("api:v1:station-tags-manage", kwargs={"id": station.id})
        data = {"tag_id": str(other_tag.id)}

        response = authenticated_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_remove_tag_from_station(
        self,
        authenticated_client: APIClient,
        station: Station,
        tag: StationTag,
    ) -> None:
        """Test removing the tag from a station."""
        station.tag = tag
        station.save()

        url = reverse("api:v1:station-tags-manage", kwargs={"id": station.id})

        response = authenticated_client.delete(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"] is None

        # Verify in database
        station.refresh_from_db()
        assert station.tag is None
