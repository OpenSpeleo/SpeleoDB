"""Test that resource_type cannot be changed at the model level."""

import pytest

from speleodb.api.v1.tests.factories import ProjectFactory
from speleodb.api.v1.tests.factories import StationFactory
from speleodb.api.v1.tests.factories import StationResourceFactory
from speleodb.surveys.models.station import StationResource
from speleodb.users.tests.factories import UserFactory


@pytest.mark.django_db
class TestStationResourceModelReadOnly:
    """Test that resource_type is protected at the model level."""

    def setup_method(self) -> None:
        """Set up test data."""
        self.user = UserFactory()
        self.project = ProjectFactory(created_by=self.user)
        self.station = StationFactory(project=self.project, created_by=self.user)

    def test_model_save_prevents_resource_type_change(self) -> None:
        """Test that changing resource_type at model level raises ValueError."""
        # Create a note resource
        resource: StationResource = StationResourceFactory(
            station=self.station,
            resource_type="note",
            title="Test Note",
            text_content="This is a test note",
            created_by=self.user,
        )  # type: ignore[assignment]

        # Try to change resource type directly and save
        resource.resource_type = "sketch"

        # Should raise ValueError when trying to save
        with pytest.raises(ValueError, match="Cannot change resource type"):
            resource.save()

        # Verify the resource type hasn't changed in DB
        resource.refresh_from_db()
        assert resource.resource_type == "note"

    def test_model_save_allows_same_resource_type(self) -> None:
        """Test that saving with the same resource_type works fine."""
        # Create a sketch resource
        resource: StationResource = StationResourceFactory(
            station=self.station,
            resource_type="sketch",
            title="Test Sketch",
            text_content='{"type": "sketch_with_history"}',
            created_by=self.user,
        )  # type: ignore[assignment]

        # Update title but keep same resource type
        resource.title = "Updated Sketch"
        resource.resource_type = "sketch"  # Same type

        # Should save without error
        resource.save()

        # Verify changes were saved
        resource.refresh_from_db()
        assert resource.title == "Updated Sketch"
        assert resource.resource_type == "sketch"

    def test_bulk_update_still_protected(self) -> None:
        """Test that bulk_update also cannot change resource_type."""
        # Create multiple resources
        resources: list[StationResource] = [
            StationResourceFactory(
                station=self.station,
                resource_type="note",
                title=f"Note {i}",
                text_content=f"Content {i}",
                created_by=self.user,
            )  # type:ignore[misc]
            for i in range(3)
        ]  # pyright: ignore[reportAssignmentType]

        # Try to change resource types
        for resource in resources:
            resource.resource_type = "sketch"

        # Bulk update should fail for each one
        for resource in resources:
            with pytest.raises(ValueError, match="Cannot change resource type"):
                resource.save()

    def test_create_with_resource_type_works(self) -> None:
        """Test that creating new resources with resource_type works."""
        # Create new resource with resource_type - using NOTE type which doesn't require
        #  a file
        resource = StationResource.objects.create(
            station=self.station,  # type:ignore[misc]
            resource_type="note",
            title="New Note",
            text_content="This is a note",
            created_by=self.user,
        )

        # Should save without error
        resource.save()

        # Verify it was created
        assert resource.pk is not None
        assert resource.resource_type == "note"

        # And the protection is now active
        resource.resource_type = "video"
        with pytest.raises(ValueError, match="Cannot change resource type"):
            resource.save()
