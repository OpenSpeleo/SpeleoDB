# -*- coding: utf-8 -*-
"""Tests for SubSurfaceStation type field on the model level."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from django.core.exceptions import ValidationError

from speleodb.api.v2.tests.factories import ProjectFactory
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
