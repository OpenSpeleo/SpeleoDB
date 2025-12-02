"""Tests for Landmark model."""

from __future__ import annotations

import pytest
from django.core.exceptions import ValidationError

from speleodb.gis.models import Landmark
from speleodb.users.models import User


@pytest.mark.django_db
class TestLandmarkModel:
    """Test cases for Landmark model."""

    @pytest.fixture
    def user(self) -> User:
        """Create a test user."""
        return User.objects.create_user(
            email="testuser@example.com",
            password="testpass123",  # noqa: S106
        )

    @pytest.fixture
    def landmark(self, user: User) -> Landmark:
        """Create a test Landmark."""
        return Landmark.objects.create(
            name="Test Cave Entrance",
            description="A beautiful cave entrance with stalactites",
            latitude=45.123456,
            longitude=-122.654321,
            user=user,
        )

    def test_create_landmark_with_valid_data(self, user: User) -> None:
        """Test creating a Landmark with all valid data."""
        landmark = Landmark.objects.create(
            name="Mountain Peak Viewpoint",
            description="Stunning panoramic views",
            latitude=47.608013,
            longitude=-122.335167,
            user=user,
        )

        assert landmark.id is not None
        assert landmark.name == "Mountain Peak Viewpoint"
        assert landmark.description == "Stunning panoramic views"
        assert landmark.latitude == 47.608013  # noqa: PLR2004
        assert landmark.longitude == -122.335167  # noqa: PLR2004
        assert landmark.user == user
        assert landmark.creation_date is not None
        assert landmark.modified_date is not None

    def test_create_landmark_minimal_data(self, user: User) -> None:
        """Test creating a Landmark with only required fields."""
        landmark = Landmark.objects.create(
            name="Minimal Landmark",
            latitude=0.0,
            longitude=0.0,
            user=user,
        )

        assert landmark.id is not None
        assert landmark.name == "Minimal Landmark"
        assert landmark.description == ""  # Default value
        assert landmark.user == user

    def test_landmark_string_representation(self, landmark: Landmark) -> None:
        """Test the string representation of Landmark."""
        assert str(landmark) == "Landmark: Test Cave Entrance"

    def test_latitude_validation(self, user: User) -> None:
        """Test latitude must be between -90 and 90."""

        # Test invalid latitude > 90
        landmark = Landmark(
            name="Invalid Latitude High",
            latitude=91.0,
            longitude=0.0,
            user=user,
        )
        with pytest.raises(ValidationError, match="latitude"):
            landmark.full_clean()

        # Test invalid latitude < -90
        landmark = Landmark(
            name="Invalid Latitude Low",
            latitude=-91.0,
            longitude=0.0,
            user=user,
        )
        with pytest.raises(ValidationError, match="latitude"):
            landmark.full_clean()

        # Test boundary values are valid
        landmark_north = Landmark(
            name="North Pole",
            latitude=90.0,
            longitude=0.0,
            user=user,
        )
        landmark_north.full_clean()  # Should not raise

        landmark_south = Landmark(
            name="South Pole",
            latitude=-90.0,
            longitude=0.0,
            user=user,
        )
        landmark_south.full_clean()  # Should not raise

    def test_longitude_validation(self, user: User) -> None:
        """Test longitude must be between -180 and 180."""
        # Test invalid longitude > 180
        with pytest.raises(ValidationError) as exc_info:  # noqa: PT012
            landmark = Landmark(
                name="Invalid Longitude High",
                latitude=0.0,
                longitude=181.0,
                user=user,
            )
            landmark.full_clean()

        assert "longitude" in exc_info.value.message_dict

        # Test invalid longitude < -180
        with pytest.raises(ValidationError) as exc_info:  # noqa: PT012
            landmark = Landmark(
                name="Invalid Longitude Low",
                latitude=0.0,
                longitude=-181.0,
                user=user,
            )
            landmark.full_clean()

        assert "longitude" in exc_info.value.message_dict

        # Test boundary values are valid
        landmark_east = Landmark(
            name="International Date Line East",
            latitude=0.0,
            longitude=180.0,
            user=user,
        )
        landmark_east.full_clean()  # Should not raise

        landmark_west = Landmark(
            name="International Date Line West",
            latitude=0.0,
            longitude=-180.0,
            user=user,
        )
        landmark_west.full_clean()  # Should not raise

    def test_coordinate_precision(self, user: User) -> None:
        """Test that coordinates maintain 7 decimal places."""
        landmark = Landmark.objects.create(
            name="Precise Location",
            latitude=45.1234567,
            longitude=-122.7654321,
            user=user,
        )

        # Refresh from database
        landmark.refresh_from_db()

        # Check precision is maintained
        assert str(landmark.latitude) == "45.1234567"
        assert str(landmark.longitude) == "-122.7654321"

    def test_user_cascade_on_user_delete(self, landmark: Landmark, user: User) -> None:
        """Test that Landmark is deleted when user is deleted (CASCADE)."""
        assert landmark.user == user
        landmark_id = landmark.id

        # Delete the user
        user.delete()

        # Landmark should be deleted due to CASCADE
        assert not Landmark.objects.filter(id=landmark_id).exists()

    def test_ordering(self, user: User) -> None:
        """Test that Landmarks are ordered by name."""
        # Create Landmarks in non-alphabetical order
        _ = Landmark.objects.create(
            name="Cave C",
            latitude=0.0,
            longitude=0.0,
            user=user,
        )
        _ = Landmark.objects.create(
            name="Arch A",
            latitude=0.0,
            longitude=0.0,
            user=user,
        )
        _ = Landmark.objects.create(
            name="Bridge B",
            latitude=0.0,
            longitude=0.0,
            user=user,
        )

        # Query all Landmarks
        landmarks = list(Landmark.objects.all())

        # Should be ordered alphabetically by name
        assert landmarks[0].name == "Arch A"
        assert landmarks[1].name == "Bridge B"
        assert landmarks[2].name == "Cave C"

    def test_timestamps_auto_update(self, landmark: Landmark) -> None:
        """Test that timestamps are automatically managed."""
        original_created = landmark.creation_date
        original_modified = landmark.modified_date

        # Update the Landmark
        landmark.description = "Updated description"
        landmark.save()
        # creation_date should not change
        assert landmark.creation_date == original_created

        # modified_date should be updated
        assert landmark.modified_date > original_modified

    def test_verbose_names(self) -> None:
        """Test model verbose names."""
        assert Landmark._meta.verbose_name == "Landmark"  # noqa: SLF001
        assert Landmark._meta.verbose_name_plural == "Landmarks"  # noqa: SLF001

    def test_blank_description_allowed(self, user: User) -> None:
        """Test that blank description is allowed."""
        landmark = Landmark.objects.create(
            name="No Description Landmark",
            latitude=10.0,
            longitude=20.0,
            user=user,
            description="",
        )

        assert landmark.description == ""
        landmark.full_clean()  # Should not raise
