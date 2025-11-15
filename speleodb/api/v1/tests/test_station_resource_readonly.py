"""Test that resource_type cannot be changed after creation."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from speleodb.api.v1.tests.factories import ProjectFactory
from speleodb.api.v1.tests.factories import StationFactory
from speleodb.api.v1.tests.factories import StationResourceFactory
from speleodb.api.v1.tests.factories import UserProjectPermissionFactory
from speleodb.common.enums import PermissionLevel
from speleodb.gis.models.station import StationResourceType
from speleodb.users.tests.factories import UserFactory

if TYPE_CHECKING:
    from speleodb.gis.models import StationResource


@pytest.mark.django_db
class TestStationResourceReadOnlyFields:
    """Test that certain fields cannot be modified after creation."""

    def setup_method(self) -> None:
        """Set up test data."""
        self.client = APIClient()
        self.user = UserFactory.create()
        self.project = ProjectFactory(created_by=self.user.email)
        # Give user write permission
        self.permission = UserProjectPermissionFactory(
            target=self.user,
            project=self.project,
            level=PermissionLevel.READ_AND_WRITE,
        )
        self.station = StationFactory(project=self.project, created_by=self.user.email)
        self.client.force_authenticate(user=self.user)

    def test_resource_type_cannot_be_changed_from_note_to_sketch(self) -> None:
        """Test that changing resource_type from note to sketch is rejected."""
        # Create a note resource
        resource: StationResource = StationResourceFactory(
            station=self.station,
            resource_type=StationResourceType.NOTE,
            title="Test Note",
            text_content="This is a test note",
        )  # type: ignore[assignment]

        # Try to change it to a sketch
        response = self.client.patch(
            reverse("api:v1:resource-detail", kwargs={"id": resource.id}),
            {
                "resource_type": StationResourceType.SKETCH,
                "text_content": '{"type": "sketch_with_history", "operations": {}, "preview": "data:image/png;base64,..."}',  # noqa: E501
            },
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Resource type cannot be changed" in str(response.data)

        # Verify the resource type hasn't changed
        resource.refresh_from_db()
        assert resource.resource_type == StationResourceType.NOTE

    def test_resource_type_cannot_be_changed_from_photo_to_video(self) -> None:
        """Test that changing resource_type from photo to video is rejected."""
        # Create a photo resource

        # Note: In real usage, this would have a file, but for testing the
        # validation is enough
        resource: StationResource = StationResourceFactory(
            station=self.station,
            resource_type=StationResourceType.PHOTO,
            title="Test Photo",
        )  # type: ignore[assignment]

        # Try to change it to a video
        response = self.client.patch(
            reverse("api:v1:resource-detail", kwargs={"id": resource.id}),
            {
                "resource_type": StationResourceType.VIDEO,
            },
            format="json",
        )

        assert response.status_code == 400  # noqa: PLR2004
        assert "Resource type cannot be changed" in str(response.data)

        # Verify the resource type hasn't changed
        resource.refresh_from_db()
        assert resource.resource_type == StationResourceType.PHOTO

    def test_resource_type_cannot_be_changed_from_sketch_to_document(self) -> None:
        """Test that changing resource_type from sketch to document is rejected."""
        # Create a sketch resource
        resource: StationResource = StationResourceFactory(
            station=self.station,
            resource_type=StationResourceType.SKETCH,
            title="Test Sketch",
            text_content='{"type": "sketch_with_history", "operations": {}, "preview": "data:image/png;base64,..."}',  # noqa: E501
        )  # type: ignore[assignment]

        # Try to change it to a document
        response = self.client.patch(
            reverse("api:v1:resource-detail", kwargs={"id": resource.id}),
            {
                "resource_type": StationResourceType.DOCUMENT,
            },
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Resource type cannot be changed" in str(response.data)

        # Verify the resource type hasn't changed
        resource.refresh_from_db()
        assert resource.resource_type == StationResourceType.SKETCH

    def test_other_fields_can_be_updated(self) -> None:
        """Test that other fields can still be updated normally."""
        # Create a note resource
        resource: StationResource = StationResourceFactory(
            station=self.station,
            resource_type=StationResourceType.NOTE,
            title="Original Title",
            description="Original Description",
            text_content="Original content",
        )  # type: ignore[assignment]

        # Update title, description, and content (but not resource_type)
        response = self.client.patch(
            reverse("api:v1:resource-detail", kwargs={"id": resource.id}),
            {
                "title": "Updated Title",
                "description": "Updated Description",
                "text_content": "Updated content",
            },
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK

        # Verify the fields were updated
        resource.refresh_from_db()
        assert resource.title == "Updated Title"
        assert resource.description == "Updated Description"
        assert resource.text_content == "Updated content"
        assert resource.resource_type == StationResourceType.NOTE

    def test_resource_type_same_value_is_allowed(self) -> None:
        """Test that sending the same resource_type value is allowed."""
        # Create a sketch resource
        resource: StationResource = StationResourceFactory(
            station=self.station,
            resource_type=StationResourceType.SKETCH,
            title="Test Sketch",
            text_content='{"type": "sketch_with_history", "operations": {}, "preview": "data:image/png;base64,..."}',  # noqa: E501
        )  # type: ignore[assignment]

        # Send an update with the same resource_type
        response = self.client.patch(
            reverse("api:v1:resource-detail", kwargs={"id": resource.id}),
            {
                "resource_type": StationResourceType.SKETCH,
                "title": "Updated Sketch Title",
            },
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK

        # Verify the title was updated
        resource.refresh_from_db()
        assert resource.title == "Updated Sketch Title"
        assert resource.resource_type == StationResourceType.SKETCH

    def test_resource_type_field_optional_on_update(self) -> None:
        """Test that resource_type field is optional during updates."""
        # Create a note resource
        resource: StationResource = StationResourceFactory(
            station=self.station,
            resource_type=StationResourceType.NOTE,
            title="Test Note",
            text_content="Original content",
        )  # type: ignore[assignment]

        # Update without sending resource_type
        response = self.client.patch(
            reverse("api:v1:resource-detail", kwargs={"id": resource.id}),
            {
                "title": "Updated Title Only",
            },
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK

        # Verify the update worked
        resource.refresh_from_db()
        assert resource.title == "Updated Title Only"
        assert resource.resource_type == StationResourceType.NOTE
