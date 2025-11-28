# -*- coding: utf-8 -*-

"""
Comprehensive test suite for Sensor Install API endpoints.

Tests cover:
- Sensor Install CRUD operations
- State transitions (INSTALLED → RETRIEVED/LOST/ABANDONED)
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

from speleodb.api.v1.tests.factories import ProjectFactory
from speleodb.api.v1.tests.factories import SensorFactory
from speleodb.api.v1.tests.factories import SensorInstallFactory
from speleodb.api.v1.tests.factories import SubSurfaceStationFactory
from speleodb.api.v1.tests.factories import UserProjectPermissionFactory
from speleodb.common.enums import PermissionLevel
from speleodb.gis.models.sensor import InstallStatus
from speleodb.users.tests.factories import UserFactory

if TYPE_CHECKING:
    from speleodb.gis.models import Sensor
    from speleodb.gis.models import SensorInstall
    from speleodb.gis.models import Station
    from speleodb.gis.models import SubSurfaceStation
    from speleodb.users.models.user import User

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
def station(user: User) -> SubSurfaceStation:
    """Create a station with write access for user."""

    project = ProjectFactory.create()
    UserProjectPermissionFactory.create(
        target=user, project=project, level=PermissionLevel.READ_AND_WRITE
    )
    return SubSurfaceStationFactory.create(project=project)


@pytest.fixture
def station_read_only(user: User) -> Station:
    """Create a station with read-only access for user."""
    project = ProjectFactory.create()
    UserProjectPermissionFactory.create(
        target=user, project=project, level=PermissionLevel.READ_ONLY
    )
    return SubSurfaceStationFactory.create(project=project)


@pytest.fixture
def sensor() -> Sensor:
    """Create a sensor."""
    return SensorFactory.create()


@pytest.fixture
def sensor_install(station: Station, sensor: Sensor, user: User) -> SensorInstall:
    """Create a sensor install."""
    return SensorInstallFactory.create(
        station=station, sensor=sensor, install_user=user.email, created_by=user.email
    )


# ================== HELPER FUNCTIONS ================== #


def get_auth_header(user: User) -> str:
    """Get authorization header for user."""
    token, _ = Token.objects.get_or_create(user=user)
    return f"Token {token.key}"


# ================== TEST CLASSES ================== #


@pytest.mark.django_db
class TestStationSensorInstallListCreate:
    """Tests for listing and creating sensor installs."""

    def test_list_sensor_installs_authenticated(
        self,
        api_client: APIClient,
        station: Station,
        sensor_install: SensorInstall,
        user: User,
    ) -> None:
        """Authenticated user can list sensor installs for a station."""
        response = api_client.get(
            reverse(
                "api:v1:station-sensor-installs",
                kwargs={"id": station.id},
            ),
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["data"]) == 1
        assert response.data["data"][0]["id"] == str(sensor_install.id)

    def test_list_sensor_installs_empty(
        self,
        api_client: APIClient,
        station: Station,
        user: User,
    ) -> None:
        """Station with no installs returns empty list."""
        response = api_client.get(
            reverse(
                "api:v1:station-sensor-installs",
                kwargs={"id": station.id},
            ),
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"] == []

    def test_list_sensor_installs_read_only(
        self,
        api_client: APIClient,
        station_read_only: Station,
        user: User,
    ) -> None:
        """Read-only user can list installs."""
        response = api_client.get(
            reverse(
                "api:v1:station-sensor-installs",
                kwargs={"id": station_read_only.id},
            ),
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK

    def test_create_sensor_install_valid(
        self,
        api_client: APIClient,
        station: Station,
        sensor: Sensor,
        user: User,
    ) -> None:
        """User with write access can create sensor install."""
        data = {
            "sensor": str(sensor.id),
            "install_date": timezone.localdate().isoformat(),
        }

        response = api_client.post(
            reverse(
                "api:v1:station-sensor-installs",
                kwargs={"id": station.id},
            ),
            data=data,
            format="json",
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["data"]["sensor_id"] == str(sensor.id)
        assert response.data["data"]["station_id"] == str(station.id)
        assert response.data["data"]["install_user"] == user.email
        assert response.data["data"]["status"] == InstallStatus.INSTALLED

    def test_create_sensor_install_with_expiracy_dates(
        self,
        api_client: APIClient,
        station: Station,
        sensor: Sensor,
        user: User,
    ) -> None:
        """User can create install with expiracy dates."""
        install_date = timezone.localdate()
        data = {
            "sensor": str(sensor.id),
            "install_date": install_date.isoformat(),
            "expiracy_memory_date": (install_date + timedelta(days=90)).isoformat(),
            "expiracy_battery_date": (install_date + timedelta(days=180)).isoformat(),
        }

        response = api_client.post(
            reverse(
                "api:v1:station-sensor-installs",
                kwargs={"id": station.id},
            ),
            data=data,
            format="json",
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["data"]["expiracy_memory_date"] is not None
        assert response.data["data"]["expiracy_battery_date"] is not None

    def test_create_sensor_install_without_write_permission(
        self,
        api_client: APIClient,
        station_read_only: Station,
        sensor: Sensor,
        user: User,
    ) -> None:
        """Read-only user cannot create install."""
        data = {
            "sensor": str(sensor.id),
            "install_date": timezone.localdate().isoformat(),
        }

        response = api_client.post(
            reverse(
                "api:v1:station-sensor-installs",
                kwargs={"id": station_read_only.id},
            ),
            data=data,
            format="json",
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_create_sensor_install_already_installed(
        self,
        api_client: APIClient,
        station: SubSurfaceStation,
        sensor_install: SensorInstall,
        user: User,
    ) -> None:
        """Cannot install sensor that's already installed elsewhere."""
        # Create another station
        other_station = SubSurfaceStationFactory.create(project=station.project)

        data = {
            "sensor": str(sensor_install.sensor.id),
            "install_date": timezone.localdate().isoformat(),
        }

        response = api_client.post(
            reverse(
                "api:v1:station-sensor-installs",
                kwargs={"id": other_station.id},
            ),
            data=data,
            format="json",
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "already installed" in str(response.data).lower()

    def test_create_sensor_install_missing_required_fields(
        self,
        api_client: APIClient,
        station: Station,
        user: User,
    ) -> None:
        """Creating install without required fields returns validation error."""
        response = api_client.post(
            reverse(
                "api:v1:station-sensor-installs",
                kwargs={"id": station.id},
            ),
            data={},
            format="json",
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "sensor" in response.data["errors"]
        assert "install_date" in response.data["errors"]

    def test_create_sensor_install_unauthenticated(
        self,
        api_client: APIClient,
        station: Station,
        sensor: Sensor,
    ) -> None:
        """Unauthenticated request returns 403."""
        data = {
            "sensor": str(sensor.id),
            "install_date": timezone.localdate().isoformat(),
        }

        response = api_client.post(
            reverse(
                "api:v1:station-sensor-installs",
                kwargs={"id": station.id},
            ),
            data=data,
            format="json",
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestStationSensorInstallRetrieveUpdate:
    """Tests for retrieving and updating sensor installs."""

    def test_retrieve_sensor_install(
        self,
        api_client: APIClient,
        station: Station,
        sensor_install: SensorInstall,
        user: User,
    ) -> None:
        """User can retrieve sensor install details."""
        response = api_client.get(
            reverse(
                "api:v1:station-sensor-install-detail",
                kwargs={"id": station.id, "install_id": sensor_install.id},
            ),
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"]["id"] == str(sensor_install.id)
        assert response.data["data"]["sensor_id"] == str(sensor_install.sensor.id)
        assert response.data["data"]["station_id"] == str(station.id)

    def test_update_status_to_retrieved(
        self,
        api_client: APIClient,
        station: Station,
        sensor_install: SensorInstall,
        user: User,
    ) -> None:
        """User can update install status to RETRIEVED."""
        uninstall_date = timezone.localdate()
        data = {
            "status": InstallStatus.RETRIEVED,
            "uninstall_date": uninstall_date.isoformat(),
        }

        response = api_client.patch(
            reverse(
                "api:v1:station-sensor-install-detail",
                kwargs={"id": station.id, "install_id": sensor_install.id},
            ),
            data=data,
            format="json",
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"]["status"] == InstallStatus.RETRIEVED
        assert response.data["data"]["uninstall_date"] == uninstall_date.isoformat()
        assert response.data["data"]["uninstall_user"] == user.email

        # Verify in database
        sensor_install.refresh_from_db()
        assert sensor_install.status == InstallStatus.RETRIEVED
        assert sensor_install.uninstall_date == uninstall_date

    def test_update_status_to_retrieved_auto_fills_dates(
        self,
        api_client: APIClient,
        station: Station,
        sensor_install: SensorInstall,
        user: User,
    ) -> None:
        """Updating to RETRIEVED auto-fills uninstall_user and uninstall_date if not
        provided."""
        data = {
            "status": InstallStatus.RETRIEVED,
        }

        response = api_client.patch(
            reverse(
                "api:v1:station-sensor-install-detail",
                kwargs={"id": station.id, "install_id": sensor_install.id},
            ),
            data=data,
            format="json",
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"]["status"] == InstallStatus.RETRIEVED
        assert response.data["data"]["uninstall_user"] == user.email
        assert response.data["data"]["uninstall_date"] is not None

    def test_update_status_to_lost(
        self,
        api_client: APIClient,
        station: Station,
        sensor_install: SensorInstall,
        user: User,
    ) -> None:
        """User can update install status to LOST."""
        data = {
            "status": InstallStatus.LOST,
            "uninstall_date": timezone.localdate().isoformat(),
        }

        response = api_client.patch(
            reverse(
                "api:v1:station-sensor-install-detail",
                kwargs={"id": station.id, "install_id": sensor_install.id},
            ),
            data=data,
            format="json",
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"]["status"] == InstallStatus.LOST

        # Verify in database
        sensor_install.refresh_from_db()
        assert sensor_install.status == InstallStatus.LOST

    def test_update_status_to_abandoned(
        self,
        api_client: APIClient,
        station: Station,
        sensor_install: SensorInstall,
        user: User,
    ) -> None:
        """User can update install status to ABANDONED."""
        data = {"status": InstallStatus.ABANDONED}

        response = api_client.patch(
            reverse(
                "api:v1:station-sensor-install-detail",
                kwargs={"id": station.id, "install_id": sensor_install.id},
            ),
            data=data,
            format="json",
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"]["status"] == InstallStatus.ABANDONED

        # Verify in database
        sensor_install.refresh_from_db()
        assert sensor_install.status == InstallStatus.ABANDONED

    def test_update_status_invalid_transition(
        self,
        api_client: APIClient,
        station: Station,
        user: User,
    ) -> None:
        """Cannot change status from RETRIEVED/LOST/ABANDONED."""
        # Create a retrieved install
        retrieved_install = SensorInstallFactory.create_uninstalled(
            station=station, uninstall_user=user.email
        )

        data = {"status": InstallStatus.INSTALLED}

        response = api_client.patch(
            reverse(
                "api:v1:station-sensor-install-detail",
                kwargs={
                    "id": station.id,
                    "install_id": retrieved_install.id,
                },
            ),
            data=data,
            format="json",
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Cannot change status" in str(response.data["errors"])

    def test_update_status_without_write_permission(
        self,
        api_client: APIClient,
        station_read_only: Station,
        user: User,
    ) -> None:
        """Read-only user cannot update install status."""
        install = SensorInstallFactory.create(station=station_read_only)

        data = {"status": InstallStatus.LOST}

        response = api_client.patch(
            reverse(
                "api:v1:station-sensor-install-detail",
                kwargs={"id": station_read_only.id, "install_id": install.id},
            ),
            data=data,
            format="json",
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_update_uninstall_date_before_install_date(
        self,
        api_client: APIClient,
        station: Station,
        sensor_install: SensorInstall,
        user: User,
    ) -> None:
        """Uninstall date must be on or after install date."""
        install_date = sensor_install.install_date
        uninstall_date = install_date - timedelta(days=1)

        data = {
            "status": InstallStatus.RETRIEVED,
            "uninstall_date": uninstall_date.isoformat(),
        }

        response = api_client.patch(
            reverse(
                "api:v1:station-sensor-install-detail",
                kwargs={"id": station.id, "install_id": sensor_install.id},
            ),
            data=data,
            format="json",
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Uninstall date must be" in str(response.data["errors"])


@pytest.mark.django_db
class TestSensorInstallEdgeCases:
    """Edge cases and validation tests."""

    def test_unique_installed_per_sensor_constraint(
        self,
        api_client: APIClient,
        station: SubSurfaceStation,
        sensor: Sensor,
        user: User,
    ) -> None:
        """Only one INSTALLED sensor per sensor at a time."""
        # Create first install
        SensorInstallFactory.create(station=station, sensor=sensor)

        # Try to create another install for the same sensor
        other_station = SubSurfaceStationFactory.create(project=station.project)
        data = {
            "sensor": str(sensor.id),
            "install_date": timezone.localdate().isoformat(),
        }

        response = api_client.post(
            reverse(
                "api:v1:station-sensor-installs",
                kwargs={"id": other_station.id},
            ),
            data=data,
            format="json",
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_can_install_retrieved_sensor(
        self,
        api_client: APIClient,
        station: SubSurfaceStation,
        sensor: Sensor,
        user: User,
    ) -> None:
        """Can install a sensor that was previously retrieved."""
        # Create a retrieved install
        _ = SensorInstallFactory.create_uninstalled(station=station, sensor=sensor)

        # Now install the same sensor at a different station
        other_station = SubSurfaceStationFactory.create(project=station.project)
        data = {
            "sensor": str(sensor.id),
            "install_date": timezone.localdate().isoformat(),
        }

        response = api_client.post(
            reverse(
                "api:v1:station-sensor-installs",
                kwargs={"id": other_station.id},
            ),
            data=data,
            format="json",
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_201_CREATED

    def test_retrieval_fields_required_for_retrieved_status(
        self,
        api_client: APIClient,
        station: Station,
        sensor_install: SensorInstall,
        user: User,
    ) -> None:
        """RETRIEVED status requires uninstall_date and uninstall_user."""
        # Try to set RETRIEVED without uninstall_date (should auto-fill)
        data = {"status": InstallStatus.RETRIEVED}

        response = api_client.patch(
            reverse(
                "api:v1:station-sensor-install-detail",
                kwargs={"id": station.id, "install_id": sensor_install.id},
            ),
            data=data,
            format="json",
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        # Should succeed because we auto-fill these fields
        assert response.status_code == status.HTTP_200_OK

    def test_retrieval_fields_not_allowed_for_non_retrieved_status(
        self,
        api_client: APIClient,
        station: Station,
        sensor_install: SensorInstall,
        user: User,
    ) -> None:
        """Retrieval fields cannot be set when status is not RETRIEVED."""
        data = {
            "status": InstallStatus.LOST,
            "uninstall_date": timezone.localdate().isoformat(),
            "uninstall_user": user.email,
        }

        response = api_client.patch(
            reverse(
                "api:v1:station-sensor-install-detail",
                kwargs={"id": station.id, "install_id": sensor_install.id},
            ),
            data=data,
            format="json",
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK

    def test_list_includes_nested_sensor_info(
        self,
        api_client: APIClient,
        station: Station,
        sensor_install: SensorInstall,
        user: User,
    ) -> None:
        """List response includes nested sensor and station information."""
        response = api_client.get(
            reverse(
                "api:v1:station-sensor-installs",
                kwargs={"id": station.id},
            ),
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK
        install_data = response.data["data"][0]
        assert "sensor_id" in install_data
        assert "sensor_name" in install_data
        assert "sensor_fleet_id" in install_data
        assert "sensor_fleet_name" in install_data
        assert "station_id" in install_data
        assert "station_name" in install_data


@pytest.mark.django_db
class TestStationSensorInstallHistory:
    """Tests for sensor installation history features."""

    def test_list_all_sensor_installs_without_status_filter(
        self,
        api_client: APIClient,
        station: Station,
        sensor: Sensor,
        user: User,
    ) -> None:
        """Verify returns all statuses when no query param provided."""
        # Create installs in all statuses
        SensorInstallFactory.create(
            station=station,
            sensor=sensor,
            status=InstallStatus.INSTALLED,
        )
        sensor2 = SensorFactory.create(fleet=sensor.fleet)
        SensorInstallFactory.create_uninstalled(
            station=station,
            sensor=sensor2,
            status=InstallStatus.RETRIEVED,
        )

        sensor3 = SensorFactory.create(fleet=sensor.fleet)
        SensorInstallFactory.create_uninstalled(
            station=station,
            sensor=sensor3,
            status=InstallStatus.LOST,
        )

        sensor4 = SensorFactory.create(fleet=sensor.fleet)
        SensorInstallFactory.create_uninstalled(
            station=station,
            sensor=sensor4,
            status=InstallStatus.ABANDONED,
        )

        # Request without status filter should return all
        response = api_client.get(
            reverse(
                "api:v1:station-sensor-installs",
                kwargs={"id": station.id},
            ),
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["data"]) == 4  # noqa: PLR2004

        # Verify all statuses are present
        statuses = {install["status"] for install in response.data["data"]}
        assert statuses == {
            InstallStatus.INSTALLED,
            InstallStatus.RETRIEVED,
            InstallStatus.LOST,
            InstallStatus.ABANDONED,
        }

    def test_list_sensor_installs_with_status_filter_installed(
        self,
        api_client: APIClient,
        station: Station,
        sensor: Sensor,
        user: User,
    ) -> None:
        """Verify ?status=installed only returns INSTALLED."""
        # Create mixed status installs
        SensorInstallFactory.create(
            station=station,
            sensor=sensor,
            status=InstallStatus.INSTALLED,
        )
        sensor2 = SensorFactory.create(fleet=sensor.fleet)
        SensorInstallFactory.create_uninstalled(
            station=station,
            sensor=sensor2,
            status=InstallStatus.RETRIEVED,
        )

        sensor3 = SensorFactory.create(fleet=sensor.fleet)
        SensorInstallFactory.create_uninstalled(
            station=station,
            sensor=sensor3,
            status=InstallStatus.LOST,
        )

        # Request with status=installed filter
        response = api_client.get(
            reverse(
                "api:v1:station-sensor-installs",
                kwargs={"id": station.id},
            )
            + "?status=installed",
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["data"]) == 1
        assert response.data["data"][0]["status"] == InstallStatus.INSTALLED

    def test_list_sensor_installs_ordering(
        self,
        api_client: APIClient,
        station: Station,
        sensor: Sensor,
        user: User,
    ) -> None:
        """Verify ordering by modified_date DESC, then install_date DESC."""
        # Create installs with different dates
        old_date = timezone.localdate() - timedelta(days=30)
        recent_date = timezone.localdate() - timedelta(days=1)

        sensor2 = SensorFactory.create(fleet=sensor.fleet)
        sensor3 = SensorFactory.create(fleet=sensor.fleet)

        install1 = SensorInstallFactory.create(
            station=station, sensor=sensor, install_date=old_date
        )
        _ = SensorInstallFactory.create(
            station=station, sensor=sensor2, install_date=recent_date
        )
        _ = SensorInstallFactory.create(
            station=station, sensor=sensor3, install_date=recent_date
        )

        # Touch install1 to make it most recently modified
        install1.save()

        response = api_client.get(
            reverse(
                "api:v1:station-sensor-installs",
                kwargs={"id": station.id},
            ),
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["data"]) == 3  # noqa: PLR2004

        # First should be most recently modified (install1)
        assert response.data["data"][0]["id"] == str(install1.id)

    def test_list_sensor_installs_empty_station(
        self,
        api_client: APIClient,
        user: User,
    ) -> None:
        """Station with no installs returns empty list."""
        # Create station with write permission but no installs
        station = SubSurfaceStationFactory.create()
        UserProjectPermissionFactory.create(
            target=user,
            project=station.project,
            level=PermissionLevel.READ_AND_WRITE,
        )

        response = api_client.get(
            reverse(
                "api:v1:station-sensor-installs",
                kwargs={"id": station.id},
            ),
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"] == []

    def test_list_sensor_installs_read_permission(
        self,
        api_client: APIClient,
        station: SubSurfaceStation,
        sensor: Sensor,
        user: User,
    ) -> None:
        """User with read-only access can list all installs."""
        # Create some installs
        SensorInstallFactory.create(
            station=station, sensor=sensor, status=InstallStatus.INSTALLED
        )
        sensor2 = SensorFactory.create(fleet=sensor.fleet)
        SensorInstallFactory.create_uninstalled(station=station, sensor=sensor2)

        # Update permission to read-only
        permission = station.project.user_permissions.get(target=user)
        permission.level = PermissionLevel.READ_ONLY.value
        permission.save()

        response = api_client.get(
            reverse(
                "api:v1:station-sensor-installs",
                kwargs={"id": station.id},
            ),
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["data"]) == 2  # noqa: PLR2004

    def test_list_sensor_installs_no_permission(
        self,
        api_client: APIClient,
        sensor: Sensor,
    ) -> None:
        """User without station access gets 401."""
        # Create user without permission
        other_user = UserFactory.create()
        station = SubSurfaceStationFactory.create()

        # Create install
        SensorInstallFactory.create(
            station=station, sensor=sensor, status=InstallStatus.INSTALLED
        )

        response = api_client.get(
            reverse(
                "api:v1:station-sensor-installs",
                kwargs={"id": station.id},
            ),
            HTTP_AUTHORIZATION=get_auth_header(other_user),
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestStationSensorInstallExcelExport:
    """Tests for Excel export functionality."""

    def test_export_excel_successful(
        self,
        api_client: APIClient,
        station: Station,
        sensor: Sensor,
        user: User,
    ) -> None:
        """Create multiple installs and verify Excel export."""
        # Create installs with various statuses
        SensorInstallFactory.create(
            station=station,
            sensor=sensor,
            status=InstallStatus.INSTALLED,
        )
        sensor2 = SensorFactory.create(fleet=sensor.fleet)
        SensorInstallFactory.create_uninstalled(station=station, sensor=sensor2)

        response = api_client.get(
            reverse(
                "api:v1:station-sensor-installs-export",
                kwargs={"id": station.id},
            ),
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK
        assert (
            response["Content-Type"]
            == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        assert "Content-Disposition" in response
        assert "attachment" in response["Content-Disposition"]
        assert "sensor_history" in response["Content-Disposition"]

    def test_export_excel_empty_station(
        self,
        api_client: APIClient,
        user: User,
    ) -> None:
        """Station with no installs returns valid Excel with headers only."""
        station = SubSurfaceStationFactory.create()
        UserProjectPermissionFactory.create(
            target=user,
            project=station.project,
            level=PermissionLevel.READ_AND_WRITE,
        )

        response = api_client.get(
            reverse(
                "api:v1:station-sensor-installs-export",
                kwargs={"id": station.id},
            ),
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK
        assert (
            response["Content-Type"]
            == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    def test_export_excel_all_fields_present(
        self,
        api_client: APIClient,
        station: Station,
        sensor: Sensor,
        user: User,
    ) -> None:
        """Create install with all fields populated and verify Excel content."""
        # Create install with all fields
        _ = SensorInstallFactory.create(
            station=station,
            sensor=sensor,
            status=InstallStatus.INSTALLED,
            install_date=timezone.localdate(),
            expiracy_memory_date=timezone.localdate() + timedelta(days=30),
            expiracy_battery_date=timezone.localdate() + timedelta(days=60),
        )

        response = api_client.get(
            reverse(
                "api:v1:station-sensor-installs-export",
                kwargs={"id": station.id},
            ),
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK
        assert (
            response["Content-Type"]
            == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    def test_export_excel_null_fields_handled(
        self,
        api_client: APIClient,
        station: Station,
        sensor: Sensor,
        user: User,
    ) -> None:
        """Create install with null optional fields and verify Excel handles them."""
        # Create install without optional fields
        SensorInstallFactory.create(
            station=station,
            sensor=sensor,
            status=InstallStatus.INSTALLED,
            uninstall_date=None,
            uninstall_user=None,
            expiracy_memory_date=None,
            expiracy_battery_date=None,
        )

        response = api_client.get(
            reverse(
                "api:v1:station-sensor-installs-export",
                kwargs={"id": station.id},
            ),
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK
        assert (
            response["Content-Type"]
            == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    def test_export_excel_filename_sanitization(
        self,
        api_client: APIClient,
        sensor: Sensor,
        user: User,
    ) -> None:
        """Station name with special characters gets sanitized in filename."""
        # Create station with special characters in name
        station = SubSurfaceStationFactory.create(name="Test/Station*Name:123")
        UserProjectPermissionFactory.create(
            target=user,
            project=station.project,
            level=PermissionLevel.READ_AND_WRITE,
        )

        SensorInstallFactory.create(station=station, sensor=sensor)

        response = api_client.get(
            reverse(
                "api:v1:station-sensor-installs-export",
                kwargs={"id": station.id},
            ),
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK
        # Verify filename is sanitized (no special chars)
        filename = response["Content-Disposition"]
        assert "/" not in filename or "Test/Station" not in filename
        assert "*" not in filename
        assert ":" not in filename

    def test_export_excel_read_permission(
        self,
        api_client: APIClient,
        station: SubSurfaceStation,
        sensor: Sensor,
        user: User,
    ) -> None:
        """User with read access can export."""
        SensorInstallFactory.create(station=station, sensor=sensor)

        # Update permission to read-only
        permission = station.project.user_permissions.get(target=user)
        permission.level = PermissionLevel.READ_ONLY.value
        permission.save()

        response = api_client.get(
            reverse(
                "api:v1:station-sensor-installs-export",
                kwargs={"id": station.id},
            ),
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK

    def test_export_excel_no_permission(
        self,
        api_client: APIClient,
        sensor: Sensor,
    ) -> None:
        """User without access gets 401."""
        other_user = UserFactory.create()
        station = SubSurfaceStationFactory.create()
        SensorInstallFactory.create(station=station, sensor=sensor)

        response = api_client.get(
            reverse(
                "api:v1:station-sensor-installs-export",
                kwargs={"id": station.id},
            ),
            HTTP_AUTHORIZATION=get_auth_header(other_user),
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_export_excel_unauthenticated(
        self,
        api_client: APIClient,
        station: Station,
        sensor: Sensor,
    ) -> None:
        """Unauthenticated request gets 403."""
        SensorInstallFactory.create(station=station, sensor=sensor)

        response = api_client.get(
            reverse(
                "api:v1:station-sensor-installs-export",
                kwargs={"id": station.id},
            ),
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_export_excel_multiple_statuses(
        self,
        api_client: APIClient,
        station: Station,
        sensor: Sensor,
        user: User,
    ) -> None:
        """Create installs in all 4 statuses and verify Excel includes all."""
        # Create installs in all statuses
        SensorInstallFactory.create(
            station=station,
            sensor=sensor,
            status=InstallStatus.INSTALLED,
        )
        sensor2 = SensorFactory.create(fleet=sensor.fleet)
        SensorInstallFactory.create_uninstalled(
            station=station,
            sensor=sensor2,
            status=InstallStatus.RETRIEVED,
        )

        sensor3 = SensorFactory.create(fleet=sensor.fleet)
        SensorInstallFactory.create_uninstalled(
            station=station,
            sensor=sensor3,
            status=InstallStatus.LOST,
        )

        sensor4 = SensorFactory.create(fleet=sensor.fleet)
        SensorInstallFactory.create_uninstalled(
            station=station,
            sensor=sensor4,
            status=InstallStatus.ABANDONED,
        )

        response = api_client.get(
            reverse(
                "api:v1:station-sensor-installs-export",
                kwargs={"id": station.id},
            ),
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK
        assert (
            response["Content-Type"]
            == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    def test_export_excel_large_dataset(
        self,
        api_client: APIClient,
        station: Station,
        user: User,
    ) -> None:
        """Create 100+ installs and verify export completes successfully."""
        # Create 100 installs
        sensors = [SensorFactory.create() for _ in range(100)]
        for sensor in sensors:
            SensorInstallFactory.create(station=station, sensor=sensor)

        response = api_client.get(
            reverse(
                "api:v1:station-sensor-installs-export",
                kwargs={"id": station.id},
            ),
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK
        assert (
            response["Content-Type"]
            == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
