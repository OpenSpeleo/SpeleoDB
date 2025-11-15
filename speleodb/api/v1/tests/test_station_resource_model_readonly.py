"""Test that resource_type cannot be changed at the model level."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from speleodb.api.v1.tests.factories import ProjectFactory
from speleodb.api.v1.tests.factories import StationFactory
from speleodb.api.v1.tests.factories import StationResourceFactory
from speleodb.gis.models.station import StationResourceType
from speleodb.users.tests.factories import UserFactory

if TYPE_CHECKING:
    from speleodb.gis.models import StationResource


@pytest.mark.django_db
class TestStationResourceModelReadOnly:
    """Test that resource_type is protected at the model level."""

    def setup_method(self) -> None:
        """Set up test data."""
        self.user = UserFactory.create()
        self.project = ProjectFactory(created_by=self.user.email)
        self.station = StationFactory(project=self.project, created_by=self.user.email)

    def test_model_save_prevents_resource_type_change(self) -> None:
        """Test that changing resource_type at model level raises ValueError."""
        # Create a note resource
        resource: StationResource = StationResourceFactory(
            station=self.station,
            resource_type=StationResourceType.NOTE,
            title="Test Note",
            text_content="This is a test note",
            created_by=self.user.email,
        )  # type: ignore[assignment]

        # Try to change resource type directly and save
        resource.resource_type = StationResourceType.SKETCH

        # Should raise ValueError when trying to save
        with pytest.raises(ValueError, match="Cannot change resource type"):
            resource.save()

        # Verify the resource type hasn't changed in DB
        resource.refresh_from_db()
        assert resource.resource_type == StationResourceType.NOTE

    def test_model_save_allows_same_resource_type(self) -> None:
        """Test that saving with the same resource_type works fine."""
        # Create a sketch resource
        resource: StationResource = StationResourceFactory(
            station=self.station,
            resource_type=StationResourceType.SKETCH,
            title="Test Sketch",
            text_content='{"type": "sketch_with_history"}',
            created_by=self.user.email,
        )  # type: ignore[assignment]

        # Update title but keep same resource type
        resource.title = "Updated Sketch"
        resource.resource_type = StationResourceType.SKETCH  # Same type

        # Should save without error
        resource.save()

        # Verify changes were saved
        resource.refresh_from_db()
        assert resource.title == "Updated Sketch"
        assert resource.resource_type == StationResourceType.SKETCH

    def test_bulk_update_still_protected(self) -> None:
        """Test that bulk_update also cannot change resource_type."""
        # Create multiple resources
        resources: list[StationResource] = [
            StationResourceFactory(
                station=self.station,
                resource_type=StationResourceType.NOTE,
                title=f"Note {i}",
                text_content=f"Content {i}",
                created_by=self.user.email,
            )  # type:ignore[misc]
            for i in range(3)
        ]  # pyright: ignore[reportAssignmentType]

        # Try to change resource types
        for resource in resources:
            resource.resource_type = StationResourceType.SKETCH

        # Bulk update should fail for each one
        for resource in resources:
            with pytest.raises(ValueError, match="Cannot change resource type"):
                resource.save()
