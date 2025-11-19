"""Tests for Station Tag Editor view."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from django.test import Client
from django.urls import reverse

from speleodb.gis.models import StationTag
from speleodb.users.models.user import User
from speleodb.users.tests.factories import UserFactory

if TYPE_CHECKING:
    from speleodb.users.models.user import User


@pytest.mark.django_db
class TestStationTagsView:
    """Test cases for Station Tag Editor view."""

    @pytest.fixture
    def client(self) -> Client:
        """Create a test client."""
        return Client()

    @pytest.fixture
    def user(self) -> User:
        """Create a test user."""
        return UserFactory.create()

    @pytest.fixture
    def authenticated_client(self, client: Client, user: User) -> Client:
        """Create an authenticated client."""
        client.force_login(user)
        return client

    @pytest.fixture
    def tag(self, user: User) -> StationTag:
        """Create a test station tag."""
        return StationTag.objects.create(
            name="Active",
            color="#EF4444",
            user=user,
        )

    def test_station_tags_page_requires_authentication(self, client: Client) -> None:
        """Test that the station tags page requires authentication."""
        url = reverse("private:station_tags")
        response = client.get(url)

        # Should redirect to login
        assert response.status_code == 302  # noqa: PLR2004

    def test_station_tags_page_accessible_when_authenticated(
        self, authenticated_client: Client, user: User
    ) -> None:
        """Test that authenticated users can access the station tags page."""
        url = reverse("private:station_tags")
        response = authenticated_client.get(url)

        assert response.status_code == 200  # noqa: PLR2004
        assert b"Station Tag Editor" in response.content
        assert b"Create New Tag" in response.content

    def test_station_tags_page_template_structure(
        self, authenticated_client: Client, user: User
    ) -> None:
        """Test that the page has the expected structure."""
        url = reverse("private:station_tags")
        response = authenticated_client.get(url)

        assert response.status_code == 200  # noqa: PLR2004

        # Check for key elements
        assert b"tags-table-body" in response.content
        assert b"tags-cards-container" in response.content
        assert b"edit-tag-modal" in response.content
        assert b"delete-tag-modal" in response.content
        assert b"btn-create-tag" in response.content

    def test_station_tags_page_context(
        self, authenticated_client: Client, user: User
    ) -> None:
        """Test that the page context is correctly set."""
        url = reverse("private:station_tags")
        response = authenticated_client.get(url)

        assert response.status_code == 200  # noqa: PLR2004
        assert "user" in response.context
        assert response.context["user"] == user

    def test_station_tags_page_with_existing_tags(
        self, authenticated_client: Client, user: User, tag: StationTag
    ) -> None:
        """Test that the page loads with existing tags."""
        # Create additional tags
        StationTag.objects.create(name="Complete", color="#22C55E", user=user)
        StationTag.objects.create(name="Priority", color="#F97316", user=user)

        url = reverse("private:station_tags")
        response = authenticated_client.get(url)

        assert response.status_code == 200  # noqa: PLR2004
        # The tags will be loaded via JavaScript, so we just check the page loads

    def test_station_tags_page_javascript_functions(
        self, authenticated_client: Client, user: User
    ) -> None:
        """Test that necessary JavaScript functions are present."""
        url = reverse("private:station_tags")
        response = authenticated_client.get(url)

        assert response.status_code == 200  # noqa: PLR2004

        content = response.content.decode("utf-8")

        # Check for JavaScript functions
        assert "loadTags()" in content or "loadTags" in content
        assert "renderTags()" in content or "renderTags" in content
        assert "btn-create-tag" in content  # Button exists
        assert "openEditModal" in content or "btn-edit-tag" in content
        assert "openDeleteModal" in content or "btn-delete-tag" in content
        assert "selectColor" in content

    def test_station_tags_page_color_picker(
        self, authenticated_client: Client, user: User
    ) -> None:
        """Test that color picker is properly configured."""
        url = reverse("private:station_tags")
        response = authenticated_client.get(url)

        assert response.status_code == 200  # noqa: PLR2004

        content = response.content.decode("utf-8")

        # Check for predefined colors array
        assert "predefinedColors" in content
        assert "#ef4444" in content.lower()
        assert "#22c55e" in content.lower()
        assert "#3b82f6" in content.lower()

    def test_station_tags_page_csrf_token(
        self, authenticated_client: Client, user: User
    ) -> None:
        """Test that CSRF token is present on the page."""
        url = reverse("private:station_tags")
        response = authenticated_client.get(url)

        assert response.status_code == 200  # noqa: PLR2004
        assert b"csrfmiddlewaretoken" in response.content

    def test_station_tags_page_modal_structure(
        self, authenticated_client: Client, user: User
    ) -> None:
        """Test that both modals have correct structure."""
        url = reverse("private:station_tags")
        response = authenticated_client.get(url)

        assert response.status_code == 200  # noqa: PLR2004

        content = response.content.decode("utf-8")

        # Edit modal
        assert "edit-tag-modal" in content
        assert "edit-tag-name" in content
        assert "edit-tag-color" in content
        assert "edit-tag-form" in content

        # Delete modal
        assert "delete-tag-modal" in content
        assert "delete-tag-id" in content
        assert "btn-confirm-delete" in content

    def test_station_tags_page_empty_state(
        self, authenticated_client: Client, user: User
    ) -> None:
        """Test that empty state is shown when no tags exist."""
        url = reverse("private:station_tags")
        response = authenticated_client.get(url)

        assert response.status_code == 200  # noqa: PLR2004
        # Empty state will be rendered by JavaScript
        assert b"tags-table-body" in response.content

    def test_station_tags_page_notification_system(
        self, authenticated_client: Client, user: User
    ) -> None:
        """Test that modal system is present."""
        url = reverse("private:station_tags")
        response = authenticated_client.get(url)

        assert response.status_code == 200  # noqa: PLR2004

        content = response.content.decode("utf-8")

        # Check for modal system (includes modal_success and modal_error)
        assert "modal_success" in content or "modal_error" in content
