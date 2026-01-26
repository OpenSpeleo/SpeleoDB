# -*- coding: utf-8 -*-
"""Tests for SubSurfaceStation type field on the model level."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from django.core.exceptions import ValidationError

from speleodb.api.v1.tests.factories import ProjectFactory
from speleodb.api.v1.tests.factories import SubSurfaceStationFactory
from speleodb.common.enums import SubSurfaceStationType
from speleodb.gis.models import SubSurfaceStation
from speleodb.users.tests.factories import UserFactory

if TYPE_CHECKING:
    from speleodb.surveys.models import Project
    from speleodb.users.models import User


@pytest.fixture
def project() -> Project:
    """Create a test project."""
    return ProjectFactory.create()


@pytest.fixture
def user() -> User:
    """Create a test user."""
    return UserFactory.create()


@pytest.mark.django_db
class TestSubSurfaceStationTypeModel:
    """Test cases for SubSurfaceStation type field at model level."""

    def test_create_science_station(self, project: Project, user: User) -> None:
        """Test creating a station with type 'science'."""
        station = SubSurfaceStation.objects.create(
            project=project,
            name="Science Station 1",
            description="Test science station",
            latitude="45.123456",
            longitude="-123.456789",
            created_by=user.email,
            type=SubSurfaceStationType.SCIENCE,
        )

        assert station.id is not None
        assert station.type == SubSurfaceStationType.SCIENCE
        assert station.type == "science"

    def test_create_bone_station(self, project: Project, user: User) -> None:
        """Test creating a station with type 'bone'."""
        station = SubSurfaceStation.objects.create(
            project=project,
            name="Bone Station 1",
            description="Test bone station",
            latitude="45.123456",
            longitude="-123.456789",
            created_by=user.email,
            type=SubSurfaceStationType.BONE,
        )

        assert station.id is not None
        assert station.type == SubSurfaceStationType.BONE
        assert station.type == "bone"

    def test_create_artifact_station(self, project: Project, user: User) -> None:
        """Test creating a station with type 'artifact'."""
        station = SubSurfaceStation.objects.create(
            project=project,
            name="Artifact Station 1",
            description="Test artifact station",
            latitude="45.123456",
            longitude="-123.456789",
            created_by=user.email,
            type=SubSurfaceStationType.ARTIFACT,
        )

        assert station.id is not None
        assert station.type == SubSurfaceStationType.ARTIFACT
        assert station.type == "artifact"

    def test_create_biology_station(self, project: Project, user: User) -> None:
        """Test creating a station with type 'biology'."""
        station = SubSurfaceStation.objects.create(
            project=project,
            name="Biology Station 1",
            description="Test biology station",
            latitude="45.123456",
            longitude="-123.456789",
            created_by=user.email,
            type=SubSurfaceStationType.BIOLOGY,
        )

        assert station.id is not None
        assert station.type == SubSurfaceStationType.BIOLOGY
        assert station.type == "biology"

    def test_create_geology_station(self, project: Project, user: User) -> None:
        """Test creating a station with type 'geology'."""
        station = SubSurfaceStation.objects.create(
            project=project,
            name="Geology Station 1",
            description="Test geology station",
            latitude="45.123456",
            longitude="-123.456789",
            created_by=user.email,
            type=SubSurfaceStationType.GEOLOGY,
        )

        assert station.id is not None
        assert station.type == SubSurfaceStationType.GEOLOGY
        assert station.type == "geology"

    def test_type_field_is_required(self, project: Project, user: User) -> None:
        """Test that type field is required (no default in model)."""
        station = SubSurfaceStation(
            project=project,
            name="No Type Station",
            description="Station without type",
            latitude="45.123456",
            longitude="-123.456789",
            created_by=user.email,
            # type is not provided - should fail validation
        )
        with pytest.raises(ValidationError) as exc_info:
            station.full_clean()

        # The error should be about the type field being required
        assert "type" in exc_info.value.message_dict

    def test_type_field_invalid_choice(self, project: Project, user: User) -> None:
        """Test that invalid type values are rejected."""
        station = SubSurfaceStation(
            project=project,
            name="Invalid Type Station",
            description="Station with invalid type",
            latitude="45.123456",
            longitude="-123.456789",
            created_by=user.email,
            type="invalid_type",
        )

        with pytest.raises(ValidationError) as exc_info:
            station.full_clean()

        assert "type" in exc_info.value.message_dict

    def test_type_field_empty_string_rejected(
        self, project: Project, user: User
    ) -> None:
        """Test that empty string type is rejected."""
        station = SubSurfaceStation(
            project=project,
            name="Empty Type Station",
            description="Station with empty type",
            latitude="45.123456",
            longitude="-123.456789",
            created_by=user.email,
            type="",
        )

        with pytest.raises(ValidationError) as exc_info:
            station.full_clean()

        assert "type" in exc_info.value.message_dict

    def test_type_field_max_length(self) -> None:
        """Test that type field respects max_length constraint."""
        # The max_length is 10 - all valid choices are within this
        assert len(SubSurfaceStationType.SCIENCE) <= 10  # noqa: PLR2004
        assert len(SubSurfaceStationType.BIOLOGY) <= 10  # noqa: PLR2004
        assert len(SubSurfaceStationType.BONE) <= 10  # noqa: PLR2004
        assert len(SubSurfaceStationType.ARTIFACT) <= 10  # noqa: PLR2004
        assert len(SubSurfaceStationType.GEOLOGY) <= 10  # noqa: PLR2004

    def test_all_station_type_choices_valid(self, project: Project, user: User) -> None:
        """Test that all enum choices create valid stations."""
        for i, station_type in enumerate(SubSurfaceStationType.choices):
            type_value = station_type[0]
            station = SubSurfaceStation(
                project=project,
                name=f"Station {type_value}_{i}",
                description=f"Station of type {type_value}",
                latitude="45.123456",  # Use string to avoid float precision issues
                longitude="-123.456789",
                created_by=user.email,
                type=type_value,
            )
            station.full_clean()  # Should not raise
            station.save()
            assert station.pk is not None

    def test_station_factory_default_type(self, project: Project) -> None:
        """Test that factory creates stations with default type."""
        station = SubSurfaceStationFactory.create(project=project)
        assert station.type == "science"

    def test_station_factory_with_bone_type(self, project: Project) -> None:
        """Test that factory can create bone stations."""
        station = SubSurfaceStationFactory.create(
            project=project, type=SubSurfaceStationType.BONE
        )
        assert station.type == "bone"

    def test_station_factory_with_artifact_type(self, project: Project) -> None:
        """Test that factory can create artifact stations."""
        station = SubSurfaceStationFactory.create(
            project=project, type=SubSurfaceStationType.ARTIFACT
        )
        assert station.type == "artifact"

    def test_station_factory_with_biology_type(self, project: Project) -> None:
        """Test that factory can create biology stations."""
        station = SubSurfaceStationFactory.create(
            project=project, type=SubSurfaceStationType.BIOLOGY
        )
        assert station.type == "biology"

    def test_station_factory_with_geology_type(self, project: Project) -> None:
        """Test that factory can create geology stations."""
        station = SubSurfaceStationFactory.create(
            project=project, type=SubSurfaceStationType.GEOLOGY
        )
        assert station.type == "geology"

    def test_type_field_can_be_queried(self, project: Project) -> None:
        """Test that stations can be filtered by type."""
        science_station = SubSurfaceStationFactory.create(
            project=project, type=SubSurfaceStationType.SCIENCE, name="Science"
        )
        biology_station = SubSurfaceStationFactory.create(
            project=project, type=SubSurfaceStationType.BIOLOGY, name="Biology"
        )
        bone_station = SubSurfaceStationFactory.create(
            project=project, type=SubSurfaceStationType.BONE, name="Bone"
        )
        artifact_station = SubSurfaceStationFactory.create(
            project=project, type=SubSurfaceStationType.ARTIFACT, name="Artifact"
        )
        geology_station = SubSurfaceStationFactory.create(
            project=project, type=SubSurfaceStationType.GEOLOGY, name="Geology"
        )

        # Query by type
        science_qs = SubSurfaceStation.objects.filter(
            type=SubSurfaceStationType.SCIENCE
        )
        biology_qs = SubSurfaceStation.objects.filter(
            type=SubSurfaceStationType.BIOLOGY
        )
        bone_qs = SubSurfaceStation.objects.filter(type=SubSurfaceStationType.BONE)
        artifact_qs = SubSurfaceStation.objects.filter(
            type=SubSurfaceStationType.ARTIFACT
        )
        geology_qs = SubSurfaceStation.objects.filter(
            type=SubSurfaceStationType.GEOLOGY
        )

        assert science_station in science_qs
        assert biology_station in biology_qs
        assert bone_station in bone_qs
        assert artifact_station in artifact_qs
        assert geology_station in geology_qs

    def test_type_field_updates_modified_date(
        self, project: Project, user: User
    ) -> None:
        """Test that changing type updates the modified_date."""
        station = SubSurfaceStation.objects.create(
            project=project,
            name="Modifiable Station",
            description="Test station",
            latitude="45.123456",
            longitude="-123.456789",
            created_by=user.email,
            type=SubSurfaceStationType.SCIENCE,
        )
        original_modified = station.modified_date

        # Update type (at model level, this is allowed)
        station.type = SubSurfaceStationType.BONE
        station.save()
        station.refresh_from_db()

        # Modified date should be updated
        assert station.modified_date > original_modified
        assert station.type == SubSurfaceStationType.BONE

    def test_type_field_choices_enum_values(self) -> None:
        """Test SubSurfaceStationType enum values."""
        assert SubSurfaceStationType.SCIENCE == "science"  # type: ignore[comparison-overlap]
        assert SubSurfaceStationType.BIOLOGY == "biology"  # type: ignore[comparison-overlap]
        assert SubSurfaceStationType.BONE == "bone"  # type: ignore[comparison-overlap]
        assert SubSurfaceStationType.ARTIFACT == "artifact"  # type: ignore[comparison-overlap]
        assert SubSurfaceStationType.GEOLOGY == "geology"  # type: ignore[comparison-overlap]

    def test_type_field_choices_enum_labels(self) -> None:
        """Test SubSurfaceStationType enum labels."""
        choices = dict(SubSurfaceStationType.choices)
        assert choices["science"] == "Science"
        assert choices["biology"] == "Biology"
        assert choices["bone"] == "Bone"
        assert choices["artifact"] == "Artifact"
        assert choices["geology"] == "Geology"
