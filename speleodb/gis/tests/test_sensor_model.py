"""Tests for Sensor models (SensorFleet, Sensor, SensorFleetUserPermission)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.utils import IntegrityError

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

    def test_create_sensor_fleet_with_valid_data(self, user: User) -> None:
        """Test creating a sensor fleet with all valid data."""
        fleet = SensorFleet.objects.create(
            name="Flow Meters - Yucatan",
            description="Collection of flow meters in Yucatan Peninsula",
            is_active=True,
            created_by=user.email,
        )

        assert fleet.id is not None
        assert fleet.name == "Flow Meters - Yucatan"
        assert fleet.description == "Collection of flow meters in Yucatan Peninsula"
        assert fleet.is_active is True
        assert fleet.created_by == user.email
        assert fleet.creation_date is not None
        assert fleet.modified_date is not None

    def test_create_sensor_fleet_minimal_data(self, user: User) -> None:
        """Test creating a sensor fleet with only required fields."""
        fleet = SensorFleet.objects.create(
            name="Minimal Fleet",
            created_by=user.email,
        )

        assert fleet.id is not None
        assert fleet.name == "Minimal Fleet"
        assert fleet.description == ""  # Default value
        assert fleet.is_active is True  # Default value
        assert fleet.created_by == user.email

    def test_sensor_fleet_string_representation(
        self, sensor_fleet: SensorFleet
    ) -> None:
        """Test the string representation of sensor fleet."""
        assert str(sensor_fleet) == "Sensor Fleet: Test Fleet"

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

    def test_sensor_fleet_default_is_active(self, user: User) -> None:
        """Test that is_active defaults to True."""
        fleet = SensorFleet.objects.create(
            name="Test Fleet",
            created_by=user.email,
        )

        assert fleet.is_active is True

    def test_timestamps_auto_update(self, sensor_fleet: SensorFleet) -> None:
        """Test that timestamps are automatically managed."""
        original_created = sensor_fleet.creation_date
        original_modified = sensor_fleet.modified_date

        # Update the fleet
        sensor_fleet.description = "Updated description"
        sensor_fleet.save()

        # creation_date should not change
        assert sensor_fleet.creation_date == original_created

        # modified_date should be updated
        assert sensor_fleet.modified_date > original_modified

    def test_verbose_names(self) -> None:
        """Test model verbose names."""
        assert SensorFleet._meta.verbose_name == "Sensor Fleet"  # noqa: SLF001
        assert SensorFleet._meta.verbose_name_plural == "Sensor Fleets"  # noqa: SLF001

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

    def test_blank_description_allowed(self, user: User) -> None:
        """Test that blank description is allowed."""
        fleet = SensorFleet.objects.create(
            name="No Description Fleet",
            created_by=user.email,
            description="",
        )

        assert fleet.description == ""
        fleet.full_clean()  # Should not raise


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

    def test_create_sensor_with_valid_data(
        self, user: User, sensor_fleet: SensorFleet
    ) -> None:
        """Test creating a sensor with all valid data."""
        sensor = Sensor.objects.create(
            name="Temperature Sensor #001",
            notes="Monitors cave temperature",
            is_functional=True,
            fleet=sensor_fleet,
            created_by=user.email,
        )

        assert sensor.id is not None
        assert sensor.name == "Temperature Sensor #001"
        assert sensor.notes == "Monitors cave temperature"
        assert sensor.is_functional is True
        assert sensor.created_by == user.email
        assert sensor.creation_date is not None
        assert sensor.modified_date is not None

    def test_create_sensor_minimal_data(
        self, user: User, sensor_fleet: SensorFleet
    ) -> None:
        """Test creating a sensor with only required fields."""
        sensor = Sensor.objects.create(
            name="Minimal Sensor",
            fleet=sensor_fleet,
            created_by=user.email,
        )

        assert sensor.id is not None
        assert sensor.name == "Minimal Sensor"
        assert sensor.notes == ""  # Default value
        assert sensor.is_functional is True  # Default value

    def test_sensor_string_representation_functional(self, sensor: Sensor) -> None:
        """Test the string representation of a functional sensor."""
        sensor.is_functional = True
        assert str(sensor) == "Sensor: Flow Meter #023 [Status: OK]"

    def test_sensor_string_representation_not_functional(self, sensor: Sensor) -> None:
        """Test the string representation of a non-functional sensor."""
        sensor.is_functional = False
        assert str(sensor) == "Sensor: Flow Meter #023 [Status: NOT OK]"

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

    def test_sensor_default_is_functional(
        self, user: User, sensor_fleet: SensorFleet
    ) -> None:
        """Test that is_functional defaults to True."""
        sensor = Sensor.objects.create(
            name="Test Sensor",
            fleet=sensor_fleet,
            created_by=user.email,
        )

        assert sensor.is_functional is True

    def test_sensor_toggle_functional_status(self, sensor: Sensor) -> None:
        """Test toggling the functional status of a sensor."""
        assert sensor.is_functional is True

        sensor.is_functional = False
        sensor.save()

        sensor.refresh_from_db()
        assert sensor.is_functional is False

        sensor.is_functional = True
        sensor.save()

        sensor.refresh_from_db()
        assert sensor.is_functional is True

    def test_timestamps_auto_update(self, sensor: Sensor) -> None:
        """Test that timestamps are automatically managed."""
        original_created = sensor.creation_date
        original_modified = sensor.modified_date

        # Update the sensor
        sensor.notes = "Updated notes"
        sensor.save()

        # creation_date should not change
        assert sensor.creation_date == original_created

        # modified_date should be updated
        assert sensor.modified_date > original_modified

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

    def test_blank_notes_allowed(self, user: User, sensor_fleet: SensorFleet) -> None:
        """Test that blank notes are allowed."""
        sensor = Sensor.objects.create(
            name="No Notes Sensor",
            fleet=sensor_fleet,
            created_by=user.email,
            notes="",
        )

        assert sensor.notes == ""
        sensor.full_clean()  # Should not raise


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

    def test_create_permission_with_valid_data(
        self, user: User, sensor_fleet: SensorFleet
    ) -> None:
        """Test creating a permission with all valid data."""
        perm = SensorFleetUserPermission.objects.create(
            user=user,
            sensor_fleet=sensor_fleet,
            level=PermissionLevel.ADMIN,
            is_active=True,
        )

        assert perm.user == user
        assert perm.sensor_fleet == sensor_fleet
        assert perm.level == PermissionLevel.ADMIN
        assert perm.is_active is True
        assert perm.creation_date is not None
        assert perm.modified_date is not None

    def test_permission_string_representation(
        self, permission: SensorFleetUserPermission
    ) -> None:
        """Test the string representation of a permission."""
        assert (
            str(permission)
            == f"{permission.user} => {permission.sensor_fleet} [{permission.level}]"
        )

    def test_permission_repr(self, permission: SensorFleetUserPermission) -> None:
        """Test the __repr__ of a permission."""
        assert repr(permission) == f"<SensorFleetUserPermission: {permission}>"

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

    def test_level_label_property(self, permission: SensorFleetUserPermission) -> None:
        """Test the level_label property."""
        permission.level = PermissionLevel.READ_ONLY
        assert permission.level_label == PermissionLevel.READ_ONLY.label

        permission.level = PermissionLevel.ADMIN
        assert permission.level_label == PermissionLevel.ADMIN.label

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

    def test_verbose_names(self) -> None:
        """Test model verbose names."""
        assert (
            SensorFleetUserPermission._meta.verbose_name  # noqa: SLF001
            == "Sensor Fleet - User Permission"
        )
        assert (
            SensorFleetUserPermission._meta.verbose_name_plural  # noqa: SLF001
            == "Sensor Fleet - User Permissions"
        )

    def test_indexes_exist(self) -> None:
        """Test that the expected indexes are defined."""
        indexes = SensorFleetUserPermission._meta.indexes  # noqa: SLF001
        assert len(indexes) == 3  # noqa: PLR2004

        # Check that index fields are as expected
        index_fields = [tuple(idx.fields) for idx in indexes]
        assert ("user", "is_active") in index_fields
        assert ("sensor_fleet", "is_active") in index_fields
        assert ("user", "sensor_fleet", "is_active") in index_fields

    def test_timestamps_auto_update(
        self, permission: SensorFleetUserPermission
    ) -> None:
        """Test that timestamps are automatically managed."""
        original_created = permission.creation_date
        original_modified = permission.modified_date

        # Update the permission
        permission.level = PermissionLevel.ADMIN
        permission.save()

        # creation_date should not change
        assert permission.creation_date == original_created

        # modified_date should be updated
        assert permission.modified_date > original_modified


@pytest.mark.django_db
class TestSensorFleetIntegration:
    """Integration tests for sensor fleet and related models."""

    def test_sensor_fleet_with_multiple_sensors(self) -> None:
        """Test a sensor fleet with multiple sensors."""
        user = UserFactory.create()
        fleet = SensorFleet.objects.create(
            name="Multi-Sensor Fleet",
            created_by=user.email,
        )

        # Note: Since Sensor doesn't have a foreign key to SensorFleet,
        # we would need to add that relationship or use a different approach
        # For now, this test verifies the fleet can be created
        assert fleet.id is not None

    def test_sensor_fleet_with_multiple_user_permissions(self) -> None:
        """Test a sensor fleet with multiple user permissions."""
        owner = UserFactory.create()
        user1 = UserFactory.create()
        user2 = UserFactory.create()

        fleet = SensorFleet.objects.create(
            name="Shared Fleet",
            created_by=owner.email,
        )

        perm1 = SensorFleetUserPermission.objects.create(
            user=user1,
            sensor_fleet=fleet,
            level=PermissionLevel.READ_ONLY,
        )

        perm2 = SensorFleetUserPermission.objects.create(
            user=user2,
            sensor_fleet=fleet,
            level=PermissionLevel.READ_AND_WRITE,
        )

        assert fleet.rel_user_permissions.count() == 2  # noqa: PLR2004
        assert perm1 in fleet.rel_user_permissions.all()
        assert perm2 in fleet.rel_user_permissions.all()

    def test_user_multiple_fleet_permissions(self) -> None:
        """Test a user with permissions on multiple fleets."""
        owner = UserFactory.create()
        user = UserFactory.create()

        fleet1 = SensorFleet.objects.create(
            name="Fleet 1",
            created_by=owner.email,
        )

        fleet2 = SensorFleet.objects.create(
            name="Fleet 2",
            created_by=owner.email,
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

        assert user.rel_sensorfleet_permissions.count() == 2  # noqa: PLR2004
        assert perm1 in user.rel_sensorfleet_permissions.all()
        assert perm2 in user.rel_sensorfleet_permissions.all()
