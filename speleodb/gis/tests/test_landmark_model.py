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
    def poi(self, user: User) -> Landmark:
        """Create a test POI."""
        return Landmark.objects.create(
            name="Test Cave Entrance",
            description="A beautiful cave entrance with stalactites",
            latitude=45.123456,
            longitude=-122.654321,
            user=user,
        )

    def test_create_poi_with_valid_data(self, user: User) -> None:
        """Test creating a POI with all valid data."""
        poi = Landmark.objects.create(
            name="Mountain Peak Viewpoint",
            description="Stunning panoramic views",
            latitude=47.608013,
            longitude=-122.335167,
            user=user,
        )

        assert poi.id is not None
        assert poi.name == "Mountain Peak Viewpoint"
        assert poi.description == "Stunning panoramic views"
        assert poi.latitude == 47.608013  # noqa: PLR2004
        assert poi.longitude == -122.335167  # noqa: PLR2004
        assert poi.user == user
        assert poi.creation_date is not None
        assert poi.modified_date is not None

    def test_create_poi_minimal_data(self, user: User) -> None:
        """Test creating a POI with only required fields."""
        poi = Landmark.objects.create(
            name="Minimal POI",
            latitude=0.0,
            longitude=0.0,
            user=user,
        )

        assert poi.id is not None
        assert poi.name == "Minimal POI"
        assert poi.description == ""  # Default value
        assert poi.user == user

    def test_poi_string_representation(self, poi: Landmark) -> None:
        """Test the string representation of POI."""
        assert str(poi) == "POI: Test Cave Entrance"

    def test_latitude_validation(self, user: User) -> None:
        """Test latitude must be between -90 and 90."""
        # Test invalid latitude > 90
        with pytest.raises(ValidationError) as exc_info:  # noqa: PT012
            poi = Landmark(
                name="Invalid Latitude High",
                latitude=91.0,
                longitude=0.0,
                user=user,
            )
            poi.full_clean()

        assert "latitude" in exc_info.value.message_dict

        # Test invalid latitude < -90
        with pytest.raises(ValidationError) as exc_info:  # noqa: PT012
            poi = Landmark(
                name="Invalid Latitude Low",
                latitude=-91.0,
                longitude=0.0,
                user=user,
            )
            poi.full_clean()

        assert "latitude" in exc_info.value.message_dict

        # Test boundary values are valid
        poi_north = Landmark(
            name="North Pole",
            latitude=90.0,
            longitude=0.0,
            user=user,
        )
        poi_north.full_clean()  # Should not raise

        poi_south = Landmark(
            name="South Pole",
            latitude=-90.0,
            longitude=0.0,
            user=user,
        )
        poi_south.full_clean()  # Should not raise

    def test_longitude_validation(self, user: User) -> None:
        """Test longitude must be between -180 and 180."""
        # Test invalid longitude > 180
        with pytest.raises(ValidationError) as exc_info:  # noqa: PT012
            poi = Landmark(
                name="Invalid Longitude High",
                latitude=0.0,
                longitude=181.0,
                user=user,
            )
            poi.full_clean()

        assert "longitude" in exc_info.value.message_dict

        # Test invalid longitude < -180
        with pytest.raises(ValidationError) as exc_info:  # noqa: PT012
            poi = Landmark(
                name="Invalid Longitude Low",
                latitude=0.0,
                longitude=-181.0,
                user=user,
            )
            poi.full_clean()

        assert "longitude" in exc_info.value.message_dict

        # Test boundary values are valid
        poi_east = Landmark(
            name="International Date Line East",
            latitude=0.0,
            longitude=180.0,
            user=user,
        )
        poi_east.full_clean()  # Should not raise

        poi_west = Landmark(
            name="International Date Line West",
            latitude=0.0,
            longitude=-180.0,
            user=user,
        )
        poi_west.full_clean()  # Should not raise

    def test_coordinate_precision(self, user: User) -> None:
        """Test that coordinates maintain 7 decimal places."""
        poi = Landmark.objects.create(
            name="Precise Location",
            latitude=45.1234567,
            longitude=-122.7654321,
            user=user,
        )

        # Refresh from database
        poi.refresh_from_db()

        # Check precision is maintained
        assert str(poi.latitude) == "45.1234567"
        assert str(poi.longitude) == "-122.7654321"

    def test_user_cascade_on_user_delete(self, poi: Landmark, user: User) -> None:
        """Test that POI is deleted when user is deleted (CASCADE)."""
        assert poi.user == user
        poi_id = poi.id

        # Delete the user
        user.delete()

        # POI should be deleted due to CASCADE
        assert not Landmark.objects.filter(id=poi_id).exists()

    def test_ordering(self, user: User) -> None:
        """Test that POIs are ordered by name."""
        # Create POIs in non-alphabetical order
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

        # Query all POIs
        pois = list(Landmark.objects.all())

        # Should be ordered alphabetically by name
        assert pois[0].name == "Arch A"
        assert pois[1].name == "Bridge B"
        assert pois[2].name == "Cave C"

    def test_timestamps_auto_update(self, poi: Landmark) -> None:
        """Test that timestamps are automatically managed."""
        original_created = poi.creation_date
        original_modified = poi.modified_date

        # Update the POI
        poi.description = "Updated description"
        poi.save()

        # creation_date should not change
        assert poi.creation_date == original_created

        # modified_date should be updated
        assert poi.modified_date > original_modified

    def test_verbose_names(self) -> None:
        """Test model verbose names."""
        assert Landmark._meta.verbose_name == "Point of Interest"  # noqa: SLF001
        assert Landmark._meta.verbose_name_plural == "Points of Interest"  # noqa: SLF001

    def test_blank_description_allowed(self, user: User) -> None:
        """Test that blank description is allowed."""
        poi = Landmark.objects.create(
            name="No Description POI",
            latitude=10.0,
            longitude=20.0,
            user=user,
            description="",
        )

        assert poi.description == ""
        poi.full_clean()  # Should not raise
