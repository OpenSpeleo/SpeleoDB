"""Tests for StationTag model."""

from __future__ import annotations

import pytest
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.utils import IntegrityError

from speleodb.api.v1.tests.factories import ProjectFactory
from speleodb.api.v1.tests.factories import StationFactory
from speleodb.gis.models import StationTag
from speleodb.users.models import User
from speleodb.users.tests.factories import UserFactory


@pytest.mark.django_db
class TestStationTagModel:
    """Test cases for StationTag model."""

    @pytest.fixture
    def user(self) -> User:
        """Create a test user."""
        return UserFactory.create()

    @pytest.fixture
    def tag(self, user: User) -> StationTag:
        """Create a test station tag."""
        return StationTag.objects.create(
            name="Testtag",  # After .title() normalization
            color="#ef4444",
            user=user,
        )

    def test_create_station_tag_with_valid_data(self, user: User) -> None:
        """Test creating a station tag with all valid data."""
        tag = StationTag.objects.create(
            name="High Priority",
            color="#f97316",
            user=user,
        )

        assert tag.id is not None
        assert tag.name == "High Priority"
        assert tag.color == "#f97316"
        assert tag.user == user
        assert tag.creation_date is not None
        assert tag.modified_date is not None

    def test_station_tag_string_representation(self, tag: StationTag) -> None:
        """Test the string representation of a station tag."""
        assert str(tag) == "Testtag (#ef4444)"

    def test_unique_name_per_user(self, user: User) -> None:
        """Test that tag names must be unique per user."""
        # Create first tag
        tag1 = StationTag.objects.create(
            name="UniqueTest",
            color="#ef4444",
            user=user,
        )
        assert tag1.pk is not None

        # Try to create duplicate - must use transaction.atomic for proper cleanup
        with transaction.atomic(), pytest.raises(IntegrityError):
            StationTag.objects.create(
                name="UniqueTest",  # Same name as existing tag
                color="#22c55e",
                user=user,
            )

    def test_different_users_can_have_same_tag_name(
        self, user: User, tag: StationTag
    ) -> None:
        """Test that different users can have tags with the same name."""
        user2 = UserFactory.create()

        tag2 = StationTag.objects.create(
            name=tag.name,
            color="#22c55e",
            user=user2,
        )

        assert tag2.id is not None
        assert tag2.name == tag.name
        assert tag2.user != tag.user

    def test_color_validation_valid_hex(self, user: User) -> None:
        """Test that valid hex colors are accepted."""
        valid_colors = [
            "#ef4444",
            "#FF5733",
            "#123456",
            "#ABCDEF",
            "#000000",
            "#ffffff",
        ]

        for color in valid_colors:
            tag = StationTag(
                name=f"Test {color}",
                color=color,
                user=user,
            )
            tag.full_clean()  # Should not raise
            tag.save()
            assert tag.id is not None

    def test_color_validation_invalid_hex(self, user: User) -> None:
        """Test that invalid hex colors are rejected."""
        invalid_colors = [
            "ef4444",  # Missing #
            "#ef444",  # Too short
            "#ef44444",  # Too long
            "#GGGGGG",  # Invalid characters
            "red",  # Color name
            "#ef-444",  # Invalid characters
        ]

        for color in invalid_colors:
            tag = StationTag(
                name=f"Test {color}",
                color=color,
                user=user,
            )
            with pytest.raises(ValidationError) as exc_info:
                tag.full_clean()

            assert "color" in exc_info.value.message_dict

    def test_predefined_colors_list(self) -> None:
        """Test that predefined colors list contains valid colors."""
        colors = StationTag.get_predefined_colors()

        assert len(colors) == 20  # noqa: PLR2004
        assert all(isinstance(color, str) for color in colors)
        assert all(color.startswith("#") for color in colors)
        assert all(len(color) == 7 for color in colors)  # noqa: PLR2004

    def test_tag_name_max_length(self, user: User) -> None:
        """Test that tag names respect max length constraint."""
        # Valid: exactly 50 characters
        tag = StationTag(
            name="a" * 50,
            color="#ef4444",
            user=user,
        )
        tag.full_clean()  # Should not raise
        tag.save()

        # Invalid: more than 50 characters
        tag_too_long = StationTag(
            name="a" * 51,
            color="#ef4444",
            user=user,
        )
        with pytest.raises(ValidationError) as exc_info:
            tag_too_long.full_clean()

        assert "name" in exc_info.value.message_dict

    def test_tag_cascade_deletion_with_user(self, user: User, tag: StationTag) -> None:
        """Test that tags are deleted when user is deleted."""
        tag_id = tag.id
        user_id = user.id

        # Delete the user
        user.delete()

        # Tag should also be deleted (CASCADE)
        assert not StationTag.objects.filter(id=tag_id).exists()
        assert not User.objects.filter(id=user_id).exists()

    def test_foreign_key_relationship_with_stations(
        self, user: User, tag: StationTag
    ) -> None:
        """Test the foreign key relationship between tag and stations."""
        project = ProjectFactory.create()
        station = StationFactory.create(project=project)

        # Set tag on station
        station.tag = tag
        station.save()

        assert station.tag == tag
        assert tag.stations.count() == 1
        assert tag.stations.first() == station

    def test_single_tag_per_station(self, user: User) -> None:
        """Test that a station can only have one tag."""

        project = ProjectFactory.create()
        station = StationFactory.create(project=project)

        tag1 = StationTag.objects.create(name="Active", color="#ef4444", user=user)
        tag2 = StationTag.objects.create(name="Complete", color="#22c55e", user=user)

        # Set first tag
        station.tag = tag1
        station.save()
        assert station.tag == tag1

        # Change to second tag
        station.tag = tag2
        station.save()
        assert station.tag == tag2

    def test_tag_on_multiple_stations(self, user: User, tag: StationTag) -> None:
        """Test that a tag can be assigned to multiple stations."""

        project = ProjectFactory.create()
        station1 = StationFactory.create(project=project, name="Station 1")
        station2 = StationFactory.create(project=project, name="Station 2")
        station3 = StationFactory.create(project=project, name="Station 3")

        station1.tag = tag
        station1.save()
        station2.tag = tag
        station2.save()
        station3.tag = tag
        station3.save()

        assert tag.stations.count() == 3  # noqa: PLR2004
        assert set(tag.stations.all()) == {station1, station2, station3}

    def test_station_tag_set_null(self, user: User, tag: StationTag) -> None:
        """Test that station tag can be set to null."""

        project = ProjectFactory.create()
        station = StationFactory.create(project=project)

        # Set tag
        station.tag = tag
        station.save()
        assert station.tag == tag

        # Clear tag
        station.tag = None
        station.save()
        assert station.tag is None
