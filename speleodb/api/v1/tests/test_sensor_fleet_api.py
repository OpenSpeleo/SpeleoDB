# -*- coding: utf-8 -*-

"""
Comprehensive test suite for Sensor Fleet API endpoints.

Tests cover:
- Sensor Fleet CRUD operations
- Sensor CRUD operations
- Permission management
- Access control at different permission levels
- Edge cases and validation
"""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from speleodb.api.v1.tests.factories import SensorFactory
from speleodb.api.v1.tests.factories import SensorFleetFactory
from speleodb.api.v1.tests.factories import SensorFleetUserPermissionFactory
from speleodb.api.v1.tests.factories import SensorInstallFactory
from speleodb.api.v1.tests.factories import SubSurfaceStationFactory
from speleodb.common.enums import InstallStatus
from speleodb.common.enums import OperationalStatus
from speleodb.common.enums import PermissionLevel
from speleodb.gis.models import Sensor
from speleodb.gis.models import SensorFleet
from speleodb.gis.models import SensorFleetUserPermission
from speleodb.users.models.user import User
from speleodb.users.tests.factories import UserFactory

if TYPE_CHECKING:
    from speleodb.users.models import User

# ================== FIXTURES ================== #


@pytest.fixture
def api_client() -> APIClient:
    """Return an API client instance."""
    return APIClient()


@pytest.fixture
def user() -> User:
    """Create a test user."""
    return UserFactory.create()


@pytest.fixture
def other_user() -> User:
    """Create another test user."""
    return UserFactory.create()


@pytest.fixture
def sensor_fleet(user: User) -> SensorFleet:
    """Create a sensor fleet."""
    return SensorFleetFactory.create(created_by=user.email)


@pytest.fixture
def sensor_fleet_with_admin(user: User) -> SensorFleet:
    """Create a sensor fleet with admin permission for user."""
    fleet = SensorFleetFactory.create(created_by=user.email)
    SensorFleetUserPermissionFactory(
        user=user,
        sensor_fleet=fleet,
        level=PermissionLevel.ADMIN,
    )
    return fleet


@pytest.fixture
def sensor_fleet_with_write(user: User) -> SensorFleet:
    """Create a sensor fleet with write permission for user."""
    fleet = SensorFleetFactory.create(created_by=user.email)
    SensorFleetUserPermissionFactory.create(
        user=user,
        sensor_fleet=fleet,
        level=PermissionLevel.READ_AND_WRITE,
    )

    return fleet


@pytest.fixture
def sensor_fleet_with_read(user: User) -> SensorFleet:
    """Create a sensor fleet with read-only permission for user."""
    fleet = SensorFleetFactory.create(created_by=user.email)
    SensorFleetUserPermissionFactory.create(
        user=user,
        sensor_fleet=fleet,
        level=PermissionLevel.READ_ONLY,
    )
    return fleet


@pytest.fixture
def sensor(sensor_fleet_with_admin: SensorFleet) -> Sensor:
    """Create a sensor in a fleet."""
    return SensorFactory.create(fleet=sensor_fleet_with_admin)


# ================== HELPER FUNCTIONS ================== #


def get_auth_header(user: User) -> str:
    """Get authorization header for user."""

    token, _ = Token.objects.get_or_create(user=user)
    return f"Token {token.key}"


# ================== TEST CLASSES ================== #


@pytest.mark.django_db
class TestSensorFleetListCreate:
    """Tests for listing and creating sensor fleets."""

    def test_list_sensor_fleets_authenticated(
        self,
        api_client: APIClient,
        user: User,
    ) -> None:
        """Authenticated user can list their accessible fleets."""
        # Create fleets with permissions
        n_fleet = 2
        fleets = SensorFleetFactory.create_batch(n_fleet, created_by=user.email)

        SensorFleetUserPermissionFactory.create(user=user, sensor_fleet=fleets[0])
        SensorFleetUserPermissionFactory.create(user=user, sensor_fleet=fleets[1])

        # Create fleet without permission (should not appear)
        SensorFleetFactory()

        response = api_client.get(
            reverse("api:v1:sensor-fleets"),
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["data"]) == n_fleet

    def test_list_sensor_fleets_with_multiple_permissions(
        self,
        api_client: APIClient,
        user: User,
    ) -> None:
        """Fleets show correct permission levels."""
        fleet_read = SensorFleetFactory(created_by=user.email)
        fleet_write = SensorFleetFactory(created_by=user.email)
        fleet_admin = SensorFleetFactory(created_by=user.email)

        SensorFleetUserPermissionFactory(
            user=user, sensor_fleet=fleet_read, level=PermissionLevel.READ_ONLY
        )
        SensorFleetUserPermissionFactory(
            user=user, sensor_fleet=fleet_write, level=PermissionLevel.READ_AND_WRITE
        )
        SensorFleetUserPermissionFactory(
            user=user, sensor_fleet=fleet_admin, level=PermissionLevel.ADMIN
        )

        response = api_client.get(
            reverse("api:v1:sensor-fleets"),
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK
        fleets = response.data["data"]

        # Check permission levels are included
        permission_levels = [f["user_permission_level"] for f in fleets]
        assert PermissionLevel.READ_ONLY in permission_levels
        assert PermissionLevel.READ_AND_WRITE in permission_levels
        assert PermissionLevel.ADMIN in permission_levels

    def test_list_sensor_fleets_includes_sensor_count(
        self,
        api_client: APIClient,
        sensor_fleet_with_admin: SensorFleet,
        user: User,
    ) -> None:
        """Fleet listing includes accurate sensor count."""
        # Create sensors
        n_sensors = 3
        SensorFactory.create_batch(n_sensors, fleet=sensor_fleet_with_admin)

        response = api_client.get(
            reverse("api:v1:sensor-fleets"),
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK
        fleet_data = response.data["data"][0]
        assert fleet_data["sensor_count"] == n_sensors

    def test_list_sensor_fleets_empty(
        self,
        api_client: APIClient,
        user: User,
    ) -> None:
        """User with no fleet access gets empty list."""
        # Create fleet without permission
        SensorFleetFactory()

        response = api_client.get(
            reverse("api:v1:sensor-fleets"),
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"] == []

    def test_create_sensor_fleet_valid(
        self,
        api_client: APIClient,
        user: User,
    ) -> None:
        """User can create a sensor fleet and gets ADMIN permission."""
        data = {
            "name": "Test Fleet",
            "description": "Test Description",
            "is_active": True,
        }

        response = api_client.post(
            reverse("api:v1:sensor-fleets"),
            data=data,
            format="json",
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["data"]["name"] == "Test Fleet"
        assert response.data["data"]["created_by"] == user.email

        # Check ADMIN permission was created
        fleet_id = response.data["data"]["id"]
        perm = SensorFleetUserPermission.objects.get(
            user=user, sensor_fleet_id=fleet_id
        )
        assert perm.level == PermissionLevel.ADMIN

    def test_create_sensor_fleet_with_initial_sensors(
        self,
        api_client: APIClient,
        user: User,
    ) -> None:
        """User can create fleet with initial sensors in one request."""
        data = {
            "name": "Fleet with Sensors",
            "description": "Test",
            "sensors": [
                {
                    "name": "Sensor 1",
                    "notes": "First sensor",
                    "status": OperationalStatus.FUNCTIONAL,
                },
                {
                    "name": "Sensor 2",
                    "notes": "Second sensor",
                    "status": OperationalStatus.BROKEN,
                },
            ],
        }

        response = api_client.post(
            reverse("api:v1:sensor-fleets"),
            data=data,
            format="json",
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_201_CREATED

        sensors = Sensor.objects.filter(
            fleet=SensorFleet.objects.get(id=response.data["data"]["id"])
        )

        assert sensors.count() == len(data["sensors"])

    def test_create_sensor_fleet_invalid_name(
        self,
        api_client: APIClient,
        user: User,
    ) -> None:
        """Creating fleet with invalid name returns validation error."""
        data = {"name": "", "description": "Test"}

        response = api_client.post(
            reverse("api:v1:sensor-fleets"),
            data=data,
            format="json",
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "name" in response.data["errors"]

    def test_create_sensor_fleet_unauthenticated(
        self,
        api_client: APIClient,
    ) -> None:
        """Unauthenticated request returns 401."""
        data = {"name": "Test Fleet"}

        response = api_client.post(
            reverse("api:v1:sensor-fleets"),
            data=data,
            format="json",
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestSensorFleetRetrieveUpdateDelete:
    """Tests for retrieving, updating, and deleting sensor fleets."""

    def test_retrieve_sensor_fleet_as_admin(
        self,
        api_client: APIClient,
        sensor_fleet_with_admin: SensorFleet,
        user: User,
    ) -> None:
        """Admin can retrieve fleet details."""
        response = api_client.get(
            reverse(
                "api:v1:sensor-fleet-detail",
                kwargs={"fleet_id": sensor_fleet_with_admin.id},
            ),
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"]["id"] == str(sensor_fleet_with_admin.id)
        assert response.data["data"]["name"] == sensor_fleet_with_admin.name

    def test_retrieve_sensor_fleet_as_read_only(
        self,
        api_client: APIClient,
        sensor_fleet_with_read: SensorFleet,
        user: User,
    ) -> None:
        """Read-only user can view fleet."""
        response = api_client.get(
            reverse(
                "api:v1:sensor-fleet-detail",
                kwargs={"fleet_id": sensor_fleet_with_read.id},
            ),
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK

    def test_retrieve_sensor_fleet_no_permission(
        self,
        api_client: APIClient,
        user: User,
    ) -> None:
        """User without permission gets 403."""
        fleet = SensorFleetFactory.create()

        response = api_client.get(
            reverse("api:v1:sensor-fleet-detail", kwargs={"fleet_id": fleet.id}),
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_update_sensor_fleet_as_write(
        self,
        api_client: APIClient,
        sensor_fleet_with_write: SensorFleet,
        user: User,
    ) -> None:
        """Write user can update fleet."""
        data = {
            "name": "Updated Name",
            "description": "Updated Description",
        }

        response = api_client.patch(
            reverse(
                "api:v1:sensor-fleet-detail",
                kwargs={"fleet_id": sensor_fleet_with_write.id},
            ),
            data=data,
            format="json",
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"]["name"] == "Updated Name"

        # Verify in database
        sensor_fleet_with_write.refresh_from_db()
        assert sensor_fleet_with_write.name == "Updated Name"

    def test_update_sensor_fleet_as_read_only(
        self,
        api_client: APIClient,
        sensor_fleet_with_read: SensorFleet,
        user: User,
    ) -> None:
        """Read-only user cannot update fleet."""
        data = {"name": "Updated Name"}

        response = api_client.patch(
            reverse(
                "api:v1:sensor-fleet-detail",
                kwargs={"fleet_id": sensor_fleet_with_read.id},
            ),
            data=data,
            format="json",
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_partial_update_sensor_fleet(
        self,
        api_client: APIClient,
        sensor_fleet_with_write: SensorFleet,
        user: User,
    ) -> None:
        """PATCH allows partial updates."""
        original_description = sensor_fleet_with_write.description
        data = {"name": "New Name Only"}

        response = api_client.patch(
            reverse(
                "api:v1:sensor-fleet-detail",
                kwargs={"fleet_id": sensor_fleet_with_write.id},
            ),
            data=data,
            format="json",
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK
        sensor_fleet_with_write.refresh_from_db()
        assert sensor_fleet_with_write.name == "New Name Only"
        assert sensor_fleet_with_write.description == original_description

    def test_delete_sensor_fleet_as_admin(
        self,
        api_client: APIClient,
        sensor_fleet_with_admin: SensorFleet,
        user: User,
    ) -> None:
        """Admin can deactivate fleet."""
        response = api_client.delete(
            reverse(
                "api:v1:sensor-fleet-detail",
                kwargs={"fleet_id": sensor_fleet_with_admin.id},
            ),
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK

        # Fleet should be inactive
        sensor_fleet_with_admin.refresh_from_db()
        assert sensor_fleet_with_admin.is_active is False

    def test_delete_sensor_fleet_as_write(
        self,
        api_client: APIClient,
        sensor_fleet_with_write: SensorFleet,
        user: User,
    ) -> None:
        """Write user cannot delete fleet."""
        response = api_client.delete(
            reverse(
                "api:v1:sensor-fleet-detail",
                kwargs={"fleet_id": sensor_fleet_with_write.id},
            ),
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_delete_cascades_to_permissions(
        self,
        api_client: APIClient,
        sensor_fleet_with_admin: SensorFleet,
        user: User,
        other_user: User,
    ) -> None:
        """Deleting fleet deactivates all permissions."""
        # Add another user's permission
        SensorFleetUserPermissionFactory(
            user=other_user,
            sensor_fleet=sensor_fleet_with_admin,
            level=PermissionLevel.READ_ONLY,
        )

        response = api_client.delete(
            reverse(
                "api:v1:sensor-fleet-detail",
                kwargs={"fleet_id": sensor_fleet_with_admin.id},
            ),
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK

        # All permissions should be deactivated
        perms = SensorFleetUserPermission.objects.filter(
            sensor_fleet=sensor_fleet_with_admin
        )
        assert all(not p.is_active for p in perms)

    def test_update_invalid_data(
        self,
        api_client: APIClient,
        sensor_fleet_with_write: SensorFleet,
        user: User,
    ) -> None:
        """Invalid data returns validation errors."""
        data = {"name": "x" * 100}  # Exceeds max length

        response = api_client.patch(
            reverse(
                "api:v1:sensor-fleet-detail",
                kwargs={"fleet_id": sensor_fleet_with_write.id},
            ),
            data=data,
            format="json",
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_retrieve_nonexistent_fleet(
        self,
        api_client: APIClient,
        user: User,
    ) -> None:
        """Retrieving non-existent fleet returns 404."""
        fake_uuid = "00000000-0000-0000-0000-000000000000"
        response = api_client.get(
            reverse("api:v1:sensor-fleet-detail", kwargs={"fleet_id": fake_uuid}),
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestSensorListCreate:
    """Tests for listing and creating sensors in a fleet."""

    def test_list_sensors_in_fleet(
        self,
        api_client: APIClient,
        sensor_fleet_with_admin: SensorFleet,
        user: User,
    ) -> None:
        """User can list all sensors in a fleet."""
        n_sensors = 3
        SensorFactory.create_batch(n_sensors, fleet=sensor_fleet_with_admin)

        response = api_client.get(
            reverse(
                "api:v1:sensor-fleet-sensors",
                kwargs={"fleet_id": sensor_fleet_with_admin.id},
            ),
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["data"]) == n_sensors

    def test_create_sensor_valid(
        self,
        api_client: APIClient,
        sensor_fleet_with_write: SensorFleet,
        user: User,
    ) -> None:
        """User with write access can create sensor."""
        data = {
            "name": "New Sensor",
            "notes": "Test notes",
            "status": OperationalStatus.FUNCTIONAL,
        }

        response = api_client.post(
            reverse(
                "api:v1:sensor-fleet-sensors",
                kwargs={"fleet_id": sensor_fleet_with_write.id},
            ),
            data=data,
            format="json",
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["data"]["name"] == "New Sensor"

    def test_create_sensor_without_write_permission(
        self,
        api_client: APIClient,
        sensor_fleet_with_read: SensorFleet,
        user: User,
    ) -> None:
        """Read-only user cannot create sensor."""
        data = {"name": "New Sensor"}

        response = api_client.post(
            reverse(
                "api:v1:sensor-fleet-sensors",
                kwargs={"fleet_id": sensor_fleet_with_read.id},
            ),
            data=data,
            format="json",
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestSensorRetrieveUpdateDelete:
    """Tests for retrieving, updating, and deleting sensors."""

    def test_retrieve_sensor(
        self,
        api_client: APIClient,
        sensor: Sensor,
        user: User,
    ) -> None:
        """User can retrieve sensor details."""
        response = api_client.get(
            reverse("api:v1:sensor-detail", kwargs={"id": sensor.id}),
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"]["id"] == str(sensor.id)

    def test_update_sensor(
        self,
        api_client: APIClient,
        sensor_fleet_with_write: SensorFleet,
        user: User,
    ) -> None:
        """User can update sensor."""
        sensor = SensorFactory.create(fleet=sensor_fleet_with_write)
        data = {"name": "Updated Sensor", "notes": "New notes"}

        response = api_client.patch(
            reverse("api:v1:sensor-detail", kwargs={"id": sensor.id}),
            data=data,
            format="json",
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"]["name"] == "Updated Sensor"

    def test_delete_sensor(
        self,
        api_client: APIClient,
        sensor_fleet_with_write: SensorFleet,
        user: User,
    ) -> None:
        """User can delete sensor."""
        sensor = SensorFactory.create(fleet=sensor_fleet_with_write)

        response = api_client.delete(
            reverse("api:v1:sensor-detail", kwargs={"id": sensor.id}),
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK
        assert not Sensor.objects.filter(id=sensor.id).exists()


@pytest.mark.django_db
class TestSensorToggleFunctional:
    """Tests for toggling sensor functional status."""

    def test_toggle_functional_true_to_false(
        self,
        api_client: APIClient,
        sensor_fleet_with_write: SensorFleet,
        user: User,
    ) -> None:
        """Toggle functional status from True to False."""
        sensor = SensorFactory.create(
            fleet=sensor_fleet_with_write,
            status=OperationalStatus.FUNCTIONAL,
        )

        response = api_client.patch(
            reverse("api:v1:sensor-toggle-functional", kwargs={"id": sensor.id}),
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK
        sensor.refresh_from_db()
        assert sensor.status == OperationalStatus.BROKEN

    def test_toggle_functional_false_to_true(
        self,
        api_client: APIClient,
        sensor_fleet_with_write: SensorFleet,
        user: User,
    ) -> None:
        """Toggle functional status from BROKEN to FUNCTIONAL."""
        sensor = SensorFactory.create(
            fleet=sensor_fleet_with_write, status=OperationalStatus.BROKEN
        )

        response = api_client.patch(
            reverse("api:v1:sensor-toggle-functional", kwargs={"id": sensor.id}),
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK
        sensor.refresh_from_db()
        assert sensor.status == OperationalStatus.FUNCTIONAL

    def test_toggle_without_write_permission(
        self,
        api_client: APIClient,
        sensor_fleet_with_read: SensorFleet,
        user: User,
    ) -> None:
        """Read-only user cannot toggle sensor status."""
        sensor = SensorFactory.create(fleet=sensor_fleet_with_read)

        response = api_client.patch(
            reverse("api:v1:sensor-toggle-functional", kwargs={"id": sensor.id}),
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestSensorFleetPermissions:
    """Tests for fleet permission management."""

    def test_list_fleet_permissions(
        self,
        api_client: APIClient,
        sensor_fleet_with_admin: SensorFleet,
        user: User,
        other_user: User,
    ) -> None:
        """Admin can list all permissions for fleet."""
        # Add another permission
        SensorFleetUserPermissionFactory(
            user=other_user,
            sensor_fleet=sensor_fleet_with_admin,
            level=PermissionLevel.READ_ONLY,
        )

        response = api_client.get(
            reverse(
                "api:v1:sensor-fleet-permissions",
                kwargs={"fleet_id": sensor_fleet_with_admin.id},
            ),
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK
        # Should have admin permission + other user's permission
        assert len(response.data["data"]) >= 2  # noqa: PLR2004

    def test_grant_permission_as_admin(
        self,
        api_client: APIClient,
        sensor_fleet_with_admin: SensorFleet,
        user: User,
        other_user: User,
    ) -> None:
        """Admin can grant permissions to other users."""
        data = {
            "user": other_user.email,
            "level": PermissionLevel.READ_AND_WRITE.label,
        }

        response = api_client.post(
            reverse(
                "api:v1:sensor-fleet-permissions",
                kwargs={"fleet_id": sensor_fleet_with_admin.id},
            ),
            data=data,
            format="json",
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert SensorFleetUserPermission.objects.filter(
            user=other_user, sensor_fleet=sensor_fleet_with_admin
        ).exists()

    def test_grant_permission_as_non_admin(
        self,
        api_client: APIClient,
        sensor_fleet_with_write: SensorFleet,
        user: User,
        other_user: User,
    ) -> None:
        """Non-admin cannot grant permissions."""
        data = {
            "user": other_user.email,
            "level": PermissionLevel.READ_ONLY,
        }

        response = api_client.post(
            reverse(
                "api:v1:sensor-fleet-permissions",
                kwargs={"fleet_id": sensor_fleet_with_write.id},
            ),
            data=data,
            format="json",
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_revoke_permission_as_admin(
        self,
        api_client: APIClient,
        sensor_fleet_with_admin: SensorFleet,
        user: User,
        other_user: User,
    ) -> None:
        """Admin can revoke other users' permissions."""
        perm = SensorFleetUserPermissionFactory.create(
            user=other_user,
            sensor_fleet=sensor_fleet_with_admin,
            level=PermissionLevel.READ_ONLY,
        )

        response = api_client.delete(
            reverse(
                "api:v1:sensor-fleet-permissions",
                kwargs={"fleet_id": sensor_fleet_with_admin.id},
            ),
            data={"user": other_user.email},
            format="json",
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK
        perm.refresh_from_db()
        assert perm.is_active is False

    def test_cannot_revoke_own_permission(
        self,
        api_client: APIClient,
        sensor_fleet_with_admin: SensorFleet,
        user: User,
    ) -> None:
        """User cannot revoke their own permission."""
        _ = SensorFleetUserPermission.objects.get(
            user=user, sensor_fleet=sensor_fleet_with_admin
        )

        response = api_client.delete(
            reverse(
                "api:v1:sensor-fleet-permissions",
                kwargs={"fleet_id": sensor_fleet_with_admin.id},
            ),
            data={"user": user.email},
            format="json",
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestSensorFleetPermissionLevels:
    """Tests for permission-based access control."""

    def test_read_only_cannot_update_fleet(
        self,
        api_client: APIClient,
        sensor_fleet_with_read: SensorFleet,
        user: User,
    ) -> None:
        """Read-only user cannot update fleet."""
        data = {"name": "Updated"}

        response = api_client.patch(
            reverse(
                "api:v1:sensor-fleet-detail",
                kwargs={"fleet_id": sensor_fleet_with_read.id},
            ),
            data=data,
            format="json",
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_read_and_write_cannot_delete(
        self,
        api_client: APIClient,
        sensor_fleet_with_write: SensorFleet,
        user: User,
    ) -> None:
        """Write user cannot delete fleet."""
        response = api_client.delete(
            reverse(
                "api:v1:sensor-fleet-detail",
                kwargs={"fleet_id": sensor_fleet_with_write.id},
            ),
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_admin_can_delete(
        self,
        api_client: APIClient,
        sensor_fleet_with_admin: SensorFleet,
        user: User,
    ) -> None:
        """Admin can delete fleet."""
        response = api_client.delete(
            reverse(
                "api:v1:sensor-fleet-detail",
                kwargs={"fleet_id": sensor_fleet_with_admin.id},
            ),
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK

    def test_unauthenticated_blocked(self, api_client: APIClient) -> None:
        """Unauthenticated requests are blocked."""
        fleet = SensorFleetFactory.create()

        response = api_client.get(
            reverse("api:v1:sensor-fleet-detail", kwargs={"fleet_id": fleet.id})
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_inactive_fleet_not_listed(self, api_client: APIClient, user: User) -> None:
        """Inactive fleets are not listed."""
        fleet = SensorFleetFactory(created_by=user.email, is_active=False)
        SensorFleetUserPermissionFactory(user=user, sensor_fleet=fleet)

        response = api_client.get(
            reverse("api:v1:sensor-fleets"),
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["data"]) == 0


@pytest.mark.django_db
class TestSensorFleetEdgeCases:
    """Edge cases and integration tests."""

    def test_fleet_name_max_length(self, api_client: APIClient, user: User) -> None:
        """Fleet name cannot exceed 50 characters."""
        data = {"name": "x" * 51}

        response = api_client.post(
            reverse("api:v1:sensor-fleets"),
            data=data,
            format="json",
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_sensor_name_max_length(
        self,
        api_client: APIClient,
        sensor_fleet_with_write: SensorFleet,
        user: User,
    ) -> None:
        """Sensor name cannot exceed 50 characters."""
        data = {"name": "x" * 51}

        response = api_client.post(
            reverse(
                "api:v1:sensor-fleet-sensors",
                kwargs={"fleet_id": sensor_fleet_with_write.id},
            ),
            data=data,
            format="json",
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_empty_description_allowed(self, api_client: APIClient, user: User) -> None:
        """Empty description is allowed."""
        data = {"name": "Test Fleet", "description": ""}

        response = api_client.post(
            reverse("api:v1:sensor-fleets"),
            data=data,
            format="json",
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_201_CREATED

    def test_special_characters_in_names(
        self,
        api_client: APIClient,
        user: User,
    ) -> None:
        """Unicode and special characters in names are supported."""
        data = {"name": "Fleet™ 测试 🚀"}

        response = api_client.post(
            reverse("api:v1:sensor-fleets"),
            data=data,
            format="json",
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["data"]["name"] == "Fleet™ 测试 🚀"


@pytest.mark.django_db
class TestSensorFleetExport:
    """Tests for exporting sensor fleet data to Excel."""

    def test_export_sensors_excel(
        self,
        api_client: APIClient,
        sensor_fleet_with_read: SensorFleet,
        user: User,
    ) -> None:
        """Read-only user can export sensors to Excel."""
        # Create some sensors with install history
        sensor1 = SensorFactory.create(fleet=sensor_fleet_with_read, name="Sensor 1")
        _ = SensorFactory.create(fleet=sensor_fleet_with_read, name="Sensor 2")

        # Create install for sensor 1
        station = SubSurfaceStationFactory.create()
        SensorInstallFactory.create(
            sensor=sensor1,
            station=station,
            status=InstallStatus.INSTALLED,
        )

        response = api_client.get(
            reverse(
                "api:v1:sensor-fleet-sensors-export",
                kwargs={"fleet_id": sensor_fleet_with_read.id},
            ),
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK
        assert (
            response["Content-Type"]
            == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        assert "sensor_fleet_" in response["Content-Disposition"]

    def test_export_sensors_no_permission(
        self,
        api_client: APIClient,
        user: User,
    ) -> None:
        """User without permission cannot export."""
        fleet = SensorFleetFactory.create()

        response = api_client.get(
            reverse(
                "api:v1:sensor-fleet-sensors-export",
                kwargs={"fleet_id": fleet.id},
            ),
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestSensorFleetWatchlist:
    """Tests for sensor fleet watchlist endpoint."""

    def test_watchlist_default_days(
        self,
        api_client: APIClient,
        sensor_fleet_with_read: SensorFleet,
        user: User,
    ) -> None:
        """Default days parameter (60) returns sensors expiring within 60 days."""
        today = timezone.localdate()

        # Create sensors with installs expiring at different times
        sensor1 = SensorFactory.create(fleet=sensor_fleet_with_read)
        sensor2 = SensorFactory.create(fleet=sensor_fleet_with_read)
        sensor3 = SensorFactory.create(fleet=sensor_fleet_with_read)

        station = SubSurfaceStationFactory.create()

        # Sensor 1: expires in 30 days (should be included)
        SensorInstallFactory.create(
            sensor=sensor1,
            station=station,
            status=InstallStatus.INSTALLED,
            expiracy_memory_date=today + timedelta(days=30),
            created_by=user.email,
        )

        # Sensor 2: expires in 90 days (should NOT be included with default 60)
        SensorInstallFactory.create(
            sensor=sensor2,
            station=station,
            status=InstallStatus.INSTALLED,
            expiracy_battery_date=today + timedelta(days=90),
            created_by=user.email,
        )

        # Sensor 3: expires in 45 days (should be included)
        SensorInstallFactory.create(
            sensor=sensor3,
            station=station,
            status=InstallStatus.INSTALLED,
            expiracy_memory_date=today + timedelta(days=45),
            created_by=user.email,
        )

        response = api_client.get(
            reverse(
                "api:v1:sensor-fleet-watchlist",
                kwargs={"fleet_id": sensor_fleet_with_read.id},
            ),
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK
        sensor_ids = {s["id"] for s in response.data["data"]}
        assert str(sensor1.id) in sensor_ids
        assert str(sensor2.id) not in sensor_ids
        assert str(sensor3.id) in sensor_ids

    def test_watchlist_custom_days(
        self,
        api_client: APIClient,
        sensor_fleet_with_read: SensorFleet,
        user: User,
    ) -> None:
        """Custom days parameter filters correctly."""
        today = timezone.localdate()

        sensor1 = SensorFactory.create(fleet=sensor_fleet_with_read)
        sensor2 = SensorFactory.create(fleet=sensor_fleet_with_read)

        station = SubSurfaceStationFactory.create()

        # Sensor 1: expires in 10 days
        SensorInstallFactory.create(
            sensor=sensor1,
            station=station,
            status=InstallStatus.INSTALLED,
            expiracy_memory_date=today + timedelta(days=10),
            created_by=user.email,
        )

        # Sensor 2: expires in 20 days
        SensorInstallFactory.create(
            sensor=sensor2,
            station=station,
            status=InstallStatus.INSTALLED,
            expiracy_battery_date=today + timedelta(days=20),
            created_by=user.email,
        )

        # Request with days=15 - should only include sensor1
        response = api_client.get(
            reverse(
                "api:v1:sensor-fleet-watchlist",
                kwargs={"fleet_id": sensor_fleet_with_read.id},
            )
            + "?days=15",
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK
        sensor_ids = {s["id"] for s in response.data["data"]}
        assert str(sensor1.id) in sensor_ids
        assert str(sensor2.id) not in sensor_ids

    def test_watchlist_empty_results(
        self,
        api_client: APIClient,
        sensor_fleet_with_read: SensorFleet,
        user: User,
    ) -> None:
        """No sensors due returns empty list."""
        today = timezone.localdate()

        sensor = SensorFactory.create(fleet=sensor_fleet_with_read)
        station = SubSurfaceStationFactory.create()

        # Sensor expires in 100 days (beyond default 60)
        SensorInstallFactory.create(
            sensor=sensor,
            station=station,
            status=InstallStatus.INSTALLED,
            expiracy_memory_date=today + timedelta(days=100),
            created_by=user.email,
        )

        response = api_client.get(
            reverse(
                "api:v1:sensor-fleet-watchlist",
                kwargs={"fleet_id": sensor_fleet_with_read.id},
            ),
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"] == []

    def test_watchlist_memory_expiry_only(
        self,
        api_client: APIClient,
        sensor_fleet_with_read: SensorFleet,
        user: User,
    ) -> None:
        """Sensor with only memory expiry is included if due."""
        today = timezone.localdate()

        sensor = SensorFactory.create(fleet=sensor_fleet_with_read)
        station = SubSurfaceStationFactory.create()

        SensorInstallFactory.create(
            sensor=sensor,
            station=station,
            status=InstallStatus.INSTALLED,
            expiracy_memory_date=today + timedelta(days=30),
            expiracy_battery_date=None,
            created_by=user.email,
        )

        response = api_client.get(
            reverse(
                "api:v1:sensor-fleet-watchlist",
                kwargs={"fleet_id": sensor_fleet_with_read.id},
            ),
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["data"]) == 1
        assert response.data["data"][0]["id"] == str(sensor.id)

    def test_watchlist_battery_expiry_only(
        self,
        api_client: APIClient,
        sensor_fleet_with_read: SensorFleet,
        user: User,
    ) -> None:
        """Sensor with only battery expiry is included if due."""
        today = timezone.localdate()

        sensor = SensorFactory.create(fleet=sensor_fleet_with_read)
        station = SubSurfaceStationFactory.create()

        SensorInstallFactory.create(
            sensor=sensor,
            station=station,
            status=InstallStatus.INSTALLED,
            expiracy_memory_date=None,
            expiracy_battery_date=today + timedelta(days=30),
            created_by=user.email,
        )

        response = api_client.get(
            reverse(
                "api:v1:sensor-fleet-watchlist",
                kwargs={"fleet_id": sensor_fleet_with_read.id},
            ),
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["data"]) == 1
        assert response.data["data"][0]["id"] == str(sensor.id)

    def test_watchlist_both_expiry_dates(
        self,
        api_client: APIClient,
        sensor_fleet_with_read: SensorFleet,
        user: User,
    ) -> None:
        """Sensor with both expiry dates is included if either is due."""
        today = timezone.localdate()

        sensor = SensorFactory.create(fleet=sensor_fleet_with_read)
        station = SubSurfaceStationFactory.create()

        # Memory expires in 30 days, battery in 90 days
        SensorInstallFactory.create(
            sensor=sensor,
            station=station,
            status=InstallStatus.INSTALLED,
            expiracy_memory_date=today + timedelta(days=30),
            expiracy_battery_date=today + timedelta(days=90),
            created_by=user.email,
        )

        response = api_client.get(
            reverse(
                "api:v1:sensor-fleet-watchlist",
                kwargs={"fleet_id": sensor_fleet_with_read.id},
            ),
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["data"]) == 1

    def test_watchlist_read_only_permission(
        self,
        api_client: APIClient,
        sensor_fleet_with_read: SensorFleet,
        user: User,
    ) -> None:
        """Read-only user can access watchlist."""
        response = api_client.get(
            reverse(
                "api:v1:sensor-fleet-watchlist",
                kwargs={"fleet_id": sensor_fleet_with_read.id},
            ),
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK

    def test_watchlist_no_permission(
        self,
        api_client: APIClient,
        user: User,
    ) -> None:
        """User without permission gets 403."""
        fleet = SensorFleetFactory.create()

        response = api_client.get(
            reverse(
                "api:v1:sensor-fleet-watchlist",
                kwargs={"fleet_id": fleet.id},
            ),
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_watchlist_unauthenticated(
        self,
        api_client: APIClient,
    ) -> None:
        """Unauthenticated request returns 403."""
        fleet = SensorFleetFactory.create()

        response = api_client.get(
            reverse(
                "api:v1:sensor-fleet-watchlist",
                kwargs={"fleet_id": fleet.id},
            ),
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_watchlist_invalid_fleet_id(
        self,
        api_client: APIClient,
        user: User,
    ) -> None:
        """Invalid fleet_id returns 404."""
        fake_uuid = "00000000-0000-0000-0000-000000000000"

        response = api_client.get(
            reverse(
                "api:v1:sensor-fleet-watchlist",
                kwargs={"fleet_id": fake_uuid},
            ),
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_watchlist_days_zero(
        self,
        api_client: APIClient,
        sensor_fleet_with_read: SensorFleet,
        user: User,
    ) -> None:
        """days=0 returns only expired sensors."""
        today = timezone.localdate()

        sensor1 = SensorFactory.create(fleet=sensor_fleet_with_read)
        sensor2 = SensorFactory.create(fleet=sensor_fleet_with_read)

        station = SubSurfaceStationFactory.create()

        # Sensor 1: expired yesterday
        # install_date must be <= expiracy_memory_date, so set install_date to
        # 2 days ago
        SensorInstallFactory.create(
            sensor=sensor1,
            station=station,
            status=InstallStatus.INSTALLED,
            install_date=today - timedelta(days=2),
            expiracy_memory_date=today - timedelta(days=1),
            created_by=user.email,
        )

        # Sensor 2: expires tomorrow
        SensorInstallFactory.create(
            sensor=sensor2,
            station=station,
            status=InstallStatus.INSTALLED,
            expiracy_memory_date=today + timedelta(days=1),
            created_by=user.email,
        )

        response = api_client.get(
            reverse(
                "api:v1:sensor-fleet-watchlist",
                kwargs={"fleet_id": sensor_fleet_with_read.id},
            )
            + "?days=0",
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK
        sensor_ids = {s["id"] for s in response.data["data"]}
        assert str(sensor1.id) in sensor_ids
        assert str(sensor2.id) not in sensor_ids

    def test_watchlist_negative_days(
        self,
        api_client: APIClient,
        sensor_fleet_with_read: SensorFleet,
        user: User,
    ) -> None:
        """Negative days parameter returns 400 error."""
        response = api_client.get(
            reverse(
                "api:v1:sensor-fleet-watchlist",
                kwargs={"fleet_id": sensor_fleet_with_read.id},
            )
            + "?days=-10",
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "non-negative" in response.data["error"].lower()

    def test_watchlist_invalid_days(
        self,
        api_client: APIClient,
        sensor_fleet_with_read: SensorFleet,
        user: User,
    ) -> None:
        """Invalid days parameter returns 400 error."""
        response = api_client.get(
            reverse(
                "api:v1:sensor-fleet-watchlist",
                kwargs={"fleet_id": sensor_fleet_with_read.id},
            )
            + "?days=invalid",
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "integer" in response.data["error"].lower()

    def test_watchlist_excludes_retrieved_sensors(
        self,
        api_client: APIClient,
        sensor_fleet_with_read: SensorFleet,
        user: User,
    ) -> None:
        """Retrieved sensors are not included in watchlist."""
        today = timezone.localdate()

        sensor1 = SensorFactory.create(fleet=sensor_fleet_with_read)
        sensor2 = SensorFactory.create(fleet=sensor_fleet_with_read)

        station = SubSurfaceStationFactory.create()

        # Sensor 1: installed and expiring soon
        SensorInstallFactory.create(
            sensor=sensor1,
            station=station,
            status=InstallStatus.INSTALLED,
            expiracy_memory_date=today + timedelta(days=30),
            created_by=user.email,
        )

        # Sensor 2: retrieved (should not appear)
        # install_date must be <= uninstall_date, so set install_date to 11 days ago
        SensorInstallFactory.create(
            sensor=sensor2,
            station=station,
            status=InstallStatus.RETRIEVED,
            install_date=today - timedelta(days=11),
            expiracy_memory_date=today + timedelta(days=30),
            uninstall_date=today - timedelta(days=10),
            uninstall_user=user.email,
            created_by=user.email,
        )

        response = api_client.get(
            reverse(
                "api:v1:sensor-fleet-watchlist",
                kwargs={"fleet_id": sensor_fleet_with_read.id},
            ),
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK
        sensor_ids = {s["id"] for s in response.data["data"]}
        assert str(sensor1.id) in sensor_ids
        assert str(sensor2.id) not in sensor_ids

    def test_watchlist_includes_install_info(
        self,
        api_client: APIClient,
        sensor_fleet_with_read: SensorFleet,
        user: User,
    ) -> None:
        """Response includes active install information."""
        today = timezone.localdate()

        sensor = SensorFactory.create(fleet=sensor_fleet_with_read)
        station = SubSurfaceStationFactory.create()

        SensorInstallFactory.create(
            sensor=sensor,
            station=station,
            status=InstallStatus.INSTALLED,
            expiracy_memory_date=today + timedelta(days=30),
            expiracy_battery_date=today + timedelta(days=60),
            created_by=user.email,
        )

        response = api_client.get(
            reverse(
                "api:v1:sensor-fleet-watchlist",
                kwargs={"fleet_id": sensor_fleet_with_read.id},
            ),
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK
        sensor_data = response.data["data"][0]
        assert "latest_install_project" in sensor_data
        assert "latest_install_memory_expiry" in sensor_data
        assert "latest_install_battery_expiry" in sensor_data
        assert "active_installs" in sensor_data
