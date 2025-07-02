"""Test that resource_type cannot be changed at the model level."""

import pytest
from django.contrib.auth import get_user_model

from speleodb.api.v1.tests.factories import ProjectFactory
from speleodb.api.v1.tests.factories import StationFactory
from speleodb.api.v1.tests.factories import StationResourceFactory
from speleodb.api.v1.tests.factories import UserFactory
from speleodb.surveys.models.station import StationResource

User = get_user_model()


@pytest.mark.django_db
class TestStationResourceModelReadOnly:
    """Test that resource_type is protected at the model level."""

    def setup_method(self):
        """Set up test data."""
        self.user = UserFactory()
        self.project = ProjectFactory(created_by=self.user)
        self.station = StationFactory(project=self.project, created_by=self.user)

    def test_model_save_prevents_resource_type_change(self):
        """Test that changing resource_type at model level raises ValueError."""
        # Create a note resource
        resource = StationResourceFactory(
            station=self.station,
            resource_type="note",
            title="Test Note",
            text_content="This is a test note",
            created_by=self.user,
        )

        # Try to change resource type directly and save
        resource.resource_type = "sketch"

        # Should raise ValueError when trying to save
        with pytest.raises(ValueError) as exc_info:
            resource.save()

        assert "Cannot change resource type" in str(exc_info.value)
        assert "from 'note' to 'sketch'" in str(exc_info.value)

        # Verify the resource type hasn't changed in DB
        resource.refresh_from_db()
        assert resource.resource_type == "note"

    def test_model_save_allows_same_resource_type(self):
        """Test that saving with the same resource_type works fine."""
        # Create a sketch resource
        resource = StationResourceFactory(
            station=self.station,
            resource_type="sketch",
            title="Test Sketch",
            text_content='{"type": "sketch_with_history"}',
            created_by=self.user,
        )

        # Update title but keep same resource type
        resource.title = "Updated Sketch"
        resource.resource_type = "sketch"  # Same type

        # Should save without error
        resource.save()

        # Verify changes were saved
        resource.refresh_from_db()
        assert resource.title == "Updated Sketch"
        assert resource.resource_type == "sketch"

    def test_bulk_update_still_protected(self):
        """Test that bulk_update also cannot change resource_type."""
        # Create multiple resources
        resources = [
            StationResourceFactory(
                station=self.station,
                resource_type="note",
                title=f"Note {i}",
                text_content=f"Content {i}",
                created_by=self.user,
            )
            for i in range(3)
        ]

        # Try to change resource types
        for resource in resources:
            resource.resource_type = "sketch"

        # Bulk update should fail for each one
        for resource in resources:
            with pytest.raises(ValueError) as exc_info:
                resource.save()
            assert "Cannot change resource type" in str(exc_info.value)

    def test_create_with_resource_type_works(self):
        """Test that creating new resources with resource_type works."""
        # Create new resource with resource_type
        resource = StationResource(
            station=self.station,
            resource_type="photo",
            title="New Photo",
            created_by=self.user,
        )

        # Should save without error
        resource.save()

        # Verify it was created
        assert resource.pk is not None
        assert resource.resource_type == "photo"

        # And the protection is now active
        resource.resource_type = "video"
        with pytest.raises(ValueError) as exc_info:
            resource.save()
        assert "Cannot change resource type" in str(exc_info.value)
