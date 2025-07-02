"""Test that resource_type cannot be changed after creation."""

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from speleodb.api.v1.tests.factories import ProjectFactory
from speleodb.api.v1.tests.factories import StationFactory
from speleodb.api.v1.tests.factories import StationResourceFactory
from speleodb.api.v1.tests.factories import UserFactory
from speleodb.api.v1.tests.factories import UserPermissionFactory
from speleodb.surveys.models import PermissionLevel

User = get_user_model()


@pytest.mark.django_db
class TestStationResourceReadOnlyFields:
    """Test that certain fields cannot be modified after creation."""

    def setup_method(self):
        """Set up test data."""
        self.client = APIClient()
        self.user = UserFactory()
        self.project = ProjectFactory(created_by=self.user)
        # Give user write permission
        self.permission = UserPermissionFactory(
            target=self.user,
            project=self.project,
            level=PermissionLevel.READ_AND_WRITE,
        )
        self.station = StationFactory(project=self.project, created_by=self.user)
        self.client.force_authenticate(user=self.user)

    def test_resource_type_cannot_be_changed_from_note_to_sketch(self):
        """Test that changing resource_type from note to sketch is rejected."""
        # Create a note resource
        resource = StationResourceFactory(
            station=self.station,
            resource_type="note",
            title="Test Note",
            text_content="This is a test note",
        )

        # Try to change it to a sketch
        response = self.client.patch(
            f"/api/v1/resources/{resource.id}/",
            {
                "resource_type": "sketch",
                "text_content": '{"type": "sketch_with_history", "operations": {}, "preview": "data:image/png;base64,..."}',
            },
            format="json",
        )

        assert response.status_code == 400
        assert "Resource type cannot be changed" in str(response.data)

        # Verify the resource type hasn't changed
        resource.refresh_from_db()
        assert resource.resource_type == "note"

    def test_resource_type_cannot_be_changed_from_photo_to_video(self):
        """Test that changing resource_type from photo to video is rejected."""
        # Create a photo resource
        resource = StationResourceFactory(
            station=self.station,
            resource_type="photo",
            title="Test Photo",
            # Note: In real usage, this would have a file, but for testing the validation is enough
        )

        # Try to change it to a video
        response = self.client.patch(
            f"/api/v1/resources/{resource.id}/",
            {
                "resource_type": "video",
            },
            format="json",
        )

        assert response.status_code == 400
        assert "Resource type cannot be changed" in str(response.data)

        # Verify the resource type hasn't changed
        resource.refresh_from_db()
        assert resource.resource_type == "photo"

    def test_resource_type_cannot_be_changed_from_sketch_to_document(self):
        """Test that changing resource_type from sketch to document is rejected."""
        # Create a sketch resource
        resource = StationResourceFactory(
            station=self.station,
            resource_type="sketch",
            title="Test Sketch",
            text_content='{"type": "sketch_with_history", "operations": {}, "preview": "data:image/png;base64,..."}',
        )

        # Try to change it to a document
        response = self.client.patch(
            f"/api/v1/resources/{resource.id}/",
            {
                "resource_type": "document",
            },
            format="json",
        )

        assert response.status_code == 400
        assert "Resource type cannot be changed" in str(response.data)

        # Verify the resource type hasn't changed
        resource.refresh_from_db()
        assert resource.resource_type == "sketch"

    def test_other_fields_can_be_updated(self):
        """Test that other fields can still be updated normally."""
        # Create a note resource
        resource = StationResourceFactory(
            station=self.station,
            resource_type="note",
            title="Original Title",
            description="Original Description",
            text_content="Original content",
        )

        # Update title, description, and content (but not resource_type)
        response = self.client.patch(
            f"/api/v1/resources/{resource.id}/",
            {
                "title": "Updated Title",
                "description": "Updated Description",
                "text_content": "Updated content",
            },
            format="json",
        )

        assert response.status_code == 200

        # Verify the fields were updated
        resource.refresh_from_db()
        assert resource.title == "Updated Title"
        assert resource.description == "Updated Description"
        assert resource.text_content == "Updated content"
        assert resource.resource_type == "note"  # Unchanged

    def test_resource_type_same_value_is_allowed(self):
        """Test that sending the same resource_type value is allowed."""
        # Create a sketch resource
        resource = StationResourceFactory(
            station=self.station,
            resource_type="sketch",
            title="Test Sketch",
            text_content='{"type": "sketch_with_history", "operations": {}, "preview": "data:image/png;base64,..."}',
        )

        # Send an update with the same resource_type
        response = self.client.patch(
            f"/api/v1/resources/{resource.id}/",
            {
                "resource_type": "sketch",
                "title": "Updated Sketch Title",
            },
            format="json",
        )

        assert response.status_code == 200

        # Verify the title was updated
        resource.refresh_from_db()
        assert resource.title == "Updated Sketch Title"
        assert resource.resource_type == "sketch"

    def test_resource_type_field_optional_on_update(self):
        """Test that resource_type field is optional during updates."""
        # Create a note resource
        resource = StationResourceFactory(
            station=self.station,
            resource_type="note",
            title="Test Note",
            text_content="Original content",
        )

        # Update without sending resource_type
        response = self.client.patch(
            f"/api/v1/resources/{resource.id}/",
            {
                "title": "Updated Title Only",
            },
            format="json",
        )

        assert response.status_code == 200

        # Verify the update worked
        resource.refresh_from_db()
        assert resource.title == "Updated Title Only"
        assert resource.resource_type == "note"  # Unchanged
