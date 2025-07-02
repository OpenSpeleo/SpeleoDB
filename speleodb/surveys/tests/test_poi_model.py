"""Tests for PointOfInterest model."""
# mypy: disable-error-code="attr-defined"

from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from speleodb.surveys.models import PointOfInterest

User = get_user_model()


@pytest.mark.django_db
class TestPointOfInterestModel:
    """Test cases for PointOfInterest model."""

    @pytest.fixture
    def user(self):
        """Create a test user."""
        return User.objects.create_user(
            email="testuser@example.com", password="testpass123"
        )

    @pytest.fixture
    def poi(self, user):
        """Create a test POI."""
        return PointOfInterest.objects.create(
            name="Test Cave Entrance",
            description="A beautiful cave entrance with stalactites",
            latitude=Decimal("45.123456"),
            longitude=Decimal("-122.654321"),
            created_by=user,
        )

    def test_create_poi_with_valid_data(self, user):
        """Test creating a POI with all valid data."""
        poi = PointOfInterest.objects.create(
            name="Mountain Peak Viewpoint",
            description="Stunning panoramic views",
            latitude=Decimal("47.608013"),
            longitude=Decimal("-122.335167"),
            created_by=user,
        )

        assert poi.id is not None
        assert poi.name == "Mountain Peak Viewpoint"
        assert poi.description == "Stunning panoramic views"
        assert poi.latitude == Decimal("47.608013")
        assert poi.longitude == Decimal("-122.335167")
        assert poi.created_by == user
        assert poi.creation_date is not None
        assert poi.modified_date is not None

    def test_create_poi_minimal_data(self, user):
        """Test creating a POI with only required fields."""
        poi = PointOfInterest.objects.create(
            name="Minimal POI",
            latitude=Decimal("0.0"),
            longitude=Decimal("0.0"),
            created_by=user,
        )

        assert poi.id is not None
        assert poi.name == "Minimal POI"
        assert poi.description == ""  # Default value
        assert poi.created_by == user

    def test_poi_string_representation(self, poi):
        """Test the string representation of POI."""
        assert str(poi) == "POI: Test Cave Entrance"

    def test_latitude_validation(self, user):
        """Test latitude must be between -90 and 90."""
        # Test invalid latitude > 90
        with pytest.raises(ValidationError) as exc_info:
            poi = PointOfInterest(
                name="Invalid Latitude High",
                latitude=Decimal("91.0"),
                longitude=Decimal("0.0"),
                created_by=user,
            )
            poi.full_clean()

        assert "latitude" in exc_info.value.message_dict

        # Test invalid latitude < -90
        with pytest.raises(ValidationError) as exc_info:
            poi = PointOfInterest(
                name="Invalid Latitude Low",
                latitude=Decimal("-91.0"),
                longitude=Decimal("0.0"),
                created_by=user,
            )
            poi.full_clean()

        assert "latitude" in exc_info.value.message_dict

        # Test boundary values are valid
        poi_north = PointOfInterest(
            name="North Pole",
            latitude=Decimal("90.0"),
            longitude=Decimal("0.0"),
            created_by=user,
        )
        poi_north.full_clean()  # Should not raise

        poi_south = PointOfInterest(
            name="South Pole",
            latitude=Decimal("-90.0"),
            longitude=Decimal("0.0"),
            created_by=user,
        )
        poi_south.full_clean()  # Should not raise

    def test_longitude_validation(self, user):
        """Test longitude must be between -180 and 180."""
        # Test invalid longitude > 180
        with pytest.raises(ValidationError) as exc_info:
            poi = PointOfInterest(
                name="Invalid Longitude High",
                latitude=Decimal("0.0"),
                longitude=Decimal("181.0"),
                created_by=user,
            )
            poi.full_clean()

        assert "longitude" in exc_info.value.message_dict

        # Test invalid longitude < -180
        with pytest.raises(ValidationError) as exc_info:
            poi = PointOfInterest(
                name="Invalid Longitude Low",
                latitude=Decimal("0.0"),
                longitude=Decimal("-181.0"),
                created_by=user,
            )
            poi.full_clean()

        assert "longitude" in exc_info.value.message_dict

        # Test boundary values are valid
        poi_east = PointOfInterest(
            name="International Date Line East",
            latitude=Decimal("0.0"),
            longitude=Decimal("180.0"),
            created_by=user,
        )
        poi_east.full_clean()  # Should not raise

        poi_west = PointOfInterest(
            name="International Date Line West",
            latitude=Decimal("0.0"),
            longitude=Decimal("-180.0"),
            created_by=user,
        )
        poi_west.full_clean()  # Should not raise

    def test_coordinate_precision(self, user):
        """Test that coordinates maintain 7 decimal places."""
        poi = PointOfInterest.objects.create(
            name="Precise Location",
            latitude=Decimal("45.1234567"),
            longitude=Decimal("-122.7654321"),
            created_by=user,
        )

        # Refresh from database
        poi.refresh_from_db()

        # Check precision is maintained
        assert str(poi.latitude) == "45.1234567"
        assert str(poi.longitude) == "-122.7654321"

    def test_created_by_cascade_on_user_delete(self, poi, user):
        """Test that POI is deleted when user is deleted (CASCADE)."""
        assert poi.created_by == user
        poi_id = poi.id

        # Delete the user
        user.delete()

        # POI should be deleted due to CASCADE
        assert not PointOfInterest.objects.filter(id=poi_id).exists()

    def test_ordering(self, user):
        """Test that POIs are ordered by name."""
        # Create POIs in non-alphabetical order
        poi_c = PointOfInterest.objects.create(
            name="Cave C",
            latitude=Decimal("0.0"),
            longitude=Decimal("0.0"),
            created_by=user,
        )
        poi_a = PointOfInterest.objects.create(
            name="Arch A",
            latitude=Decimal("0.0"),
            longitude=Decimal("0.0"),
            created_by=user,
        )
        poi_b = PointOfInterest.objects.create(
            name="Bridge B",
            latitude=Decimal("0.0"),
            longitude=Decimal("0.0"),
            created_by=user,
        )

        # Query all POIs
        pois = list(PointOfInterest.objects.all())

        # Should be ordered alphabetically by name
        assert pois[0].name == "Arch A"
        assert pois[1].name == "Bridge B"
        assert pois[2].name == "Cave C"

    def test_timestamps_auto_update(self, poi):
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

    def test_verbose_names(self):
        """Test model verbose names."""
        assert PointOfInterest._meta.verbose_name == "Point of Interest"
        assert PointOfInterest._meta.verbose_name_plural == "Points of Interest"

    def test_blank_description_allowed(self, user):
        """Test that blank description is allowed."""
        poi = PointOfInterest.objects.create(
            name="No Description POI",
            latitude=Decimal("10.0"),
            longitude=Decimal("20.0"),
            created_by=user,
            description="",
        )

        assert poi.description == ""
        poi.full_clean()  # Should not raise
