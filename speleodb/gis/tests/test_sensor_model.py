"""Tests for Sensor models (SensorFleet, Sensor, SensorFleetUserPermission)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.utils import IntegrityError

from speleodb.common.enums import OperationalStatus
from speleodb.common.enums import PermissionLevel
from speleodb.gis.models import Sensor
from speleodb.gis.models import SensorFleet
from speleodb.gis.models import SensorFleetUserPermission
from speleodb.users.tests.factories import UserFactory

if TYPE_CHECKING:
    from speleodb.users.models import User


@pytest.mark.django_db
class TestSensorFleetModel:
    """Test cases for SensorFleet model."""

    @pytest.fixture
    def user(self) -> User:
        """Create a test user."""
        return UserFactory.create()

    @pytest.fixture
    def sensor_fleet(self, user: User) -> SensorFleet:
        """Create a test sensor fleet."""
        return SensorFleet.objects.create(
            name="Test Fleet",
            description="Test sensor fleet description",
            created_by=user.email,
        )

    def test_create_sensor_fleet_minimal_data(self, user: User) -> None:
        """Test creating a sensor fleet with only required fields."""
        fleet = SensorFleet.objects.create(
            name="Minimal Fleet",
            created_by=user.email,
        )

        fleet.full_clean()
        fleet.refresh_from_db()
        assert fleet.id is not None
        assert fleet.name == "Minimal Fleet"
        assert fleet.description == ""  # Default value
        assert fleet.is_active is True  # Default value
        assert fleet.created_by == user.email

    def test_sensor_fleet_name_max_length(self, user: User) -> None:
        """Test that fleet names respect max length constraint (50 chars)."""
        # Valid: exactly 50 characters
        fleet = SensorFleet(
            name="a" * 50,
            created_by=user.email,
        )
        fleet.full_clean()  # Should not raise
        fleet.save()

        # Invalid: more than 50 characters
        fleet_too_long = SensorFleet(
            name="a" * 51,
            created_by=user.email,
        )
        with pytest.raises(ValidationError) as exc_info:
            fleet_too_long.full_clean()

        assert "name" in exc_info.value.message_dict

    def test_ordering(self, user: User) -> None:
        """Test that sensor fleets are ordered by modified_date descending."""
        fleet1 = SensorFleet.objects.create(
            name="Fleet 1",
            created_by=user.email,
        )
        fleet2 = SensorFleet.objects.create(
            name="Fleet 2",
            created_by=user.email,
        )
        fleet3 = SensorFleet.objects.create(
            name="Fleet 3",
            created_by=user.email,
        )

        # Update fleet1 to make it the most recently modified
        fleet1.description = "Updated"
        fleet1.save()

        # Query all fleets
        fleets = list(SensorFleet.objects.all())

        # Should be ordered by modified_date descending
        assert fleets[0] == fleet1  # Most recently modified
        assert fleets[1] == fleet3
        assert fleets[2] == fleet2


@pytest.mark.django_db
class TestSensorModel:
    """Test cases for Sensor model."""

    @pytest.fixture
    def user(self) -> User:
        """Create a test user."""
        return UserFactory.create()

    @pytest.fixture
    def sensor_fleet(self, user: User) -> SensorFleet:
        """Create a test sensor fleet."""
        return SensorFleet.objects.create(
            name="Test Fleet",
            description="Test sensor fleet",
            created_by=user.email,
        )

    @pytest.fixture
    def sensor(self, user: User, sensor_fleet: SensorFleet) -> Sensor:
        """Create a test sensor."""
        return Sensor.objects.create(
            name="Flow Meter #023",
            notes="Located at entrance",
            fleet=sensor_fleet,
            created_by=user.email,
        )

    def test_create_sensor_minimal_data(
        self, user: User, sensor_fleet: SensorFleet
    ) -> None:
        """Test creating a sensor with only required fields."""
        sensor = Sensor.objects.create(
            name="Minimal Sensor",
            fleet=sensor_fleet,
            created_by=user.email,
        )

        sensor.full_clean()
        sensor.refresh_from_db()
        assert sensor.id is not None
        assert sensor.name == "Minimal Sensor"
        assert sensor.notes == ""  # Default value
        assert sensor.status == OperationalStatus.FUNCTIONAL  # Default value

    def test_sensor_name_max_length(
        self, user: User, sensor_fleet: SensorFleet
    ) -> None:
        """Test that sensor names respect max length constraint (50 chars)."""
        # Valid: exactly 50 characters
        sensor = Sensor(
            name="a" * 50,
            fleet=sensor_fleet,
            created_by=user.email,
        )
        sensor.full_clean()  # Should not raise
        sensor.save()

        # Invalid: more than 50 characters
        sensor_too_long = Sensor(
            name="a" * 51,
            fleet=sensor_fleet,
            created_by=user.email,
        )
        with pytest.raises(ValidationError) as exc_info:
            sensor_too_long.full_clean()

        assert "name" in exc_info.value.message_dict

    def test_ordering(self, user: User, sensor_fleet: SensorFleet) -> None:
        """Test that sensors are ordered by modified_date descending."""
        sensor1 = Sensor.objects.create(
            name="Sensor 1",
            fleet=sensor_fleet,
            created_by=user.email,
        )
        sensor2 = Sensor.objects.create(
            name="Sensor 2",
            fleet=sensor_fleet,
            created_by=user.email,
        )
        sensor3 = Sensor.objects.create(
            name="Sensor 3",
            fleet=sensor_fleet,
            created_by=user.email,
        )

        # Update sensor2 to make it the most recently modified
        sensor2.notes = "Updated"
        sensor2.save()

        # Query all sensors
        sensors = list(Sensor.objects.all())

        # Should be ordered by modified_date descending
        assert sensors[0] == sensor2  # Most recently modified
        assert sensors[1] == sensor3
        assert sensors[2] == sensor1


@pytest.mark.django_db
class TestSensorFleetUserPermissionModel:
    """Test cases for SensorFleetUserPermission model."""

    @pytest.fixture
    def user(self) -> User:
        """Create a test user."""
        return UserFactory.create()

    @pytest.fixture
    def user2(self) -> User:
        """Create a second test user."""
        return UserFactory.create()

    @pytest.fixture
    def sensor_fleet(self, user: User) -> SensorFleet:
        """Create a test sensor fleet."""
        return SensorFleet.objects.create(
            name="Test Fleet",
            created_by=user.email,
        )

    @pytest.fixture
    def permission(
        self, user: User, sensor_fleet: SensorFleet
    ) -> SensorFleetUserPermission:
        """Create a test permission."""
        return SensorFleetUserPermission.objects.create(
            user=user,
            sensor_fleet=sensor_fleet,
            level=PermissionLevel.READ_ONLY,
        )

    def test_unique_user_sensor_fleet_constraint(
        self, user: User, sensor_fleet: SensorFleet
    ) -> None:
        """Test that user and sensor_fleet combination must be unique."""
        # Create first permission
        perm1 = SensorFleetUserPermission.objects.create(
            user=user,
            sensor_fleet=sensor_fleet,
            level=PermissionLevel.READ_ONLY,
        )
        assert perm1.pk is not None

        # Try to create duplicate - must use transaction.atomic for proper cleanup
        with transaction.atomic(), pytest.raises(IntegrityError):
            SensorFleetUserPermission.objects.create(
                user=user,
                sensor_fleet=sensor_fleet,
                level=PermissionLevel.ADMIN,
            )

    def test_different_users_can_have_permissions_on_same_fleet(
        self, user: User, user2: User, sensor_fleet: SensorFleet
    ) -> None:
        """Test that different users can have permissions on the same fleet."""
        perm1 = SensorFleetUserPermission.objects.create(
            user=user,
            sensor_fleet=sensor_fleet,
            level=PermissionLevel.READ_ONLY,
        )

        perm2 = SensorFleetUserPermission.objects.create(
            user=user2,
            sensor_fleet=sensor_fleet,
            level=PermissionLevel.ADMIN,
        )

        assert perm1.id is not None
        assert perm2.id is not None
        assert perm1.user != perm2.user
        assert perm1.sensor_fleet == perm2.sensor_fleet

    def test_same_user_can_have_permissions_on_different_fleets(
        self, user: User
    ) -> None:
        """Test that the same user can have permissions on different fleets."""
        fleet1 = SensorFleet.objects.create(
            name="Fleet 1",
            created_by=user.email,
        )
        fleet2 = SensorFleet.objects.create(
            name="Fleet 2",
            created_by=user.email,
        )

        perm1 = SensorFleetUserPermission.objects.create(
            user=user,
            sensor_fleet=fleet1,
            level=PermissionLevel.READ_ONLY,
        )

        perm2 = SensorFleetUserPermission.objects.create(
            user=user,
            sensor_fleet=fleet2,
            level=PermissionLevel.ADMIN,
        )

        assert perm1.id is not None
        assert perm2.id is not None
        assert perm1.sensor_fleet != perm2.sensor_fleet

    def test_permission_default_values(
        self, user: User, sensor_fleet: SensorFleet
    ) -> None:
        """Test default values for permission fields."""
        perm = SensorFleetUserPermission.objects.create(
            user=user,
            sensor_fleet=sensor_fleet,
        )

        assert perm.level == PermissionLevel.READ_ONLY  # Default
        assert perm.is_active is True  # Default
        assert perm.deactivated_by is None  # Default

    def test_deactivate_permission(
        self, permission: SensorFleetUserPermission, user2: User
    ) -> None:
        """Test deactivating a permission."""
        assert permission.is_active is True
        assert permission.deactivated_by is None

        permission.deactivate(deactivated_by=user2)

        assert permission.is_active is False
        assert permission.deactivated_by == user2

    def test_reactivate_permission(
        self, permission: SensorFleetUserPermission, user2: User
    ) -> None:
        """Test reactivating a permission."""
        # First deactivate
        permission.deactivate(deactivated_by=user2)
        assert permission.is_active is False

        # Now reactivate with new level
        permission.reactivate(level=PermissionLevel.ADMIN)

        assert permission.is_active is True
        assert permission.level == PermissionLevel.ADMIN
        assert permission.deactivated_by is None

    def test_permission_cascade_on_user_delete(
        self, user: User, sensor_fleet: SensorFleet
    ) -> None:
        """Test that permission is deleted when user is deleted."""
        perm = SensorFleetUserPermission.objects.create(
            user=user,
            sensor_fleet=sensor_fleet,
        )
        perm_id = perm.id

        # Delete the user
        user.delete()

        # Permission should be deleted (CASCADE)
        assert not SensorFleetUserPermission.objects.filter(id=perm_id).exists()

    def test_permission_cascade_on_sensor_fleet_delete(
        self, user: User, sensor_fleet: SensorFleet
    ) -> None:
        """Test that permission is deleted when sensor fleet is deleted."""
        perm = SensorFleetUserPermission.objects.create(
            user=user,
            sensor_fleet=sensor_fleet,
        )
        perm_id = perm.id

        # Delete the sensor fleet
        sensor_fleet.delete()

        # Permission should be deleted (CASCADE)
        assert not SensorFleetUserPermission.objects.filter(id=perm_id).exists()
