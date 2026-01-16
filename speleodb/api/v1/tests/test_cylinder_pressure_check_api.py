# -*- coding: utf-8 -*-

"""
Comprehensive test suite for Cylinder Pressure Check API endpoints.

Tests cover:
- Pressure Check CRUD operations
- Permission management
- Access control at different permission levels
- Edge cases and validation
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from speleodb.api.v1.tests.factories import CylinderFactory
from speleodb.api.v1.tests.factories import CylinderFleetFactory
from speleodb.api.v1.tests.factories import CylinderFleetUserPermissionFactory
from speleodb.api.v1.tests.factories import CylinderInstallFactory
from speleodb.api.v1.tests.factories import CylinderPressureCheckFactory
from speleodb.common.enums import PermissionLevel
from speleodb.common.enums import UnitSystem
from speleodb.gis.models import Cylinder
from speleodb.gis.models import CylinderFleet
from speleodb.gis.models import CylinderInstall
from speleodb.gis.models import CylinderPressureCheck
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
def cylinder_fleet_with_write(user: User) -> CylinderFleet:
    """Create a cylinder fleet with write permission for user."""
    fleet = CylinderFleetFactory.create(created_by=user.email)
    CylinderFleetUserPermissionFactory.create(
        user=user,
        cylinder_fleet=fleet,
        level=PermissionLevel.READ_AND_WRITE,
    )
    return fleet


@pytest.fixture
def cylinder_fleet_with_read(user: User) -> CylinderFleet:
    """Create a cylinder fleet with read-only permission for user."""
    fleet = CylinderFleetFactory.create(created_by=user.email)
    CylinderFleetUserPermissionFactory.create(
        user=user,
        cylinder_fleet=fleet,
        level=PermissionLevel.READ_ONLY,
    )
    return fleet


@pytest.fixture
def cylinder(cylinder_fleet_with_write: CylinderFleet, user: User) -> Cylinder:
    """Create a cylinder in a fleet with write access."""
    return CylinderFactory.create(
        fleet=cylinder_fleet_with_write, created_by=user.email
    )


@pytest.fixture
def cylinder_install(cylinder: Cylinder, user: User) -> CylinderInstall:
    """Create a cylinder install."""
    return CylinderInstallFactory.create(
        cylinder=cylinder,
        install_user=user.email,
        created_by=user.email,
    )


@pytest.fixture
def pressure_check(
    cylinder_install: CylinderInstall, user: User
) -> CylinderPressureCheck:
    """Create a pressure check."""
    return CylinderPressureCheckFactory.create(
        install=cylinder_install,
        user=user.email,
    )


# ================== HELPER FUNCTIONS ================== #


def get_auth_header(user: User) -> str:
    """Get authorization header for user."""
    token, _ = Token.objects.get_or_create(user=user)
    return f"Token {token.key}"


# ================== TEST CLASSES ================== #


@pytest.mark.django_db
class TestCylinderPressureCheckListCreate:
    """Tests for listing and creating pressure checks."""

    def test_list_pressure_checks(
        self,
        api_client: APIClient,
        cylinder_install: CylinderInstall,
        pressure_check: CylinderPressureCheck,
        user: User,
    ) -> None:
        """Authenticated user can list pressure checks for an install."""
        response = api_client.get(
            reverse(
                "api:v1:cylinder-install-pressure-checks",
                kwargs={"install_id": cylinder_install.id},
            ),
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["data"]) == 1
        assert response.data["data"][0]["id"] == str(pressure_check.id)

    def test_list_pressure_checks_multiple(
        self,
        api_client: APIClient,
        cylinder_install: CylinderInstall,
        user: User,
    ) -> None:
        """Multiple pressure checks are returned in order."""
        _ = CylinderPressureCheckFactory.create(install=cylinder_install, pressure=2800)
        _ = CylinderPressureCheckFactory.create(install=cylinder_install, pressure=2500)
        check3 = CylinderPressureCheckFactory.create(
            install=cylinder_install, pressure=2200
        )

        response = api_client.get(
            reverse(
                "api:v1:cylinder-install-pressure-checks",
                kwargs={"install_id": cylinder_install.id},
            ),
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["data"]) == 3  # noqa: PLR2004
        # Should be ordered by creation_date DESC (most recent first)
        pressures = [c["pressure"] for c in response.data["data"]]
        # check3 was created last, so should be first
        assert pressures[0] == check3.pressure

    def test_list_pressure_checks_empty(
        self,
        api_client: APIClient,
        cylinder_install: CylinderInstall,
        user: User,
    ) -> None:
        """Install with no pressure checks returns empty list."""
        response = api_client.get(
            reverse(
                "api:v1:cylinder-install-pressure-checks",
                kwargs={"install_id": cylinder_install.id},
            ),
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"] == []

    def test_list_pressure_checks_no_permission(
        self,
        api_client: APIClient,
        user: User,
    ) -> None:
        """User without fleet access cannot list pressure checks."""
        install = CylinderInstallFactory.create()
        CylinderPressureCheckFactory.create(install=install)

        response = api_client.get(
            reverse(
                "api:v1:cylinder-install-pressure-checks",
                kwargs={"install_id": install.id},
            ),
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_list_pressure_checks_install_not_found(
        self,
        api_client: APIClient,
        user: User,
    ) -> None:
        """Requesting non-existent install returns 404."""
        fake_uuid = "00000000-0000-0000-0000-000000000000"
        response = api_client.get(
            reverse(
                "api:v1:cylinder-install-pressure-checks",
                kwargs={"install_id": fake_uuid},
            ),
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_create_pressure_check_valid(
        self,
        api_client: APIClient,
        cylinder_install: CylinderInstall,
        user: User,
    ) -> None:
        """User with write access can create pressure check."""
        data = {
            "pressure": 2800,
            "unit_system": UnitSystem.IMPERIAL,
            "check_date": "2025-01-15",
            "notes": "Checked during safety stop",
        }

        response = api_client.post(
            reverse(
                "api:v1:cylinder-install-pressure-checks",
                kwargs={"install_id": cylinder_install.id},
            ),
            data=data,
            format="json",
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["data"]["pressure"] == 2800  # noqa: PLR2004
        assert response.data["data"]["unit_system"] == UnitSystem.IMPERIAL
        assert response.data["data"]["check_date"] == "2025-01-15"
        assert response.data["data"]["user"] == user.email

    def test_create_pressure_check_metric(
        self,
        api_client: APIClient,
        cylinder_install: CylinderInstall,
        user: User,
    ) -> None:
        """User can create pressure check with metric units."""
        data = {
            "pressure": 200,
            "unit_system": UnitSystem.METRIC,
            "check_date": "2025-01-15",
        }

        response = api_client.post(
            reverse(
                "api:v1:cylinder-install-pressure-checks",
                kwargs={"install_id": cylinder_install.id},
            ),
            data=data,
            format="json",
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["data"]["pressure"] == 200  # noqa: PLR2004
        assert response.data["data"]["unit_system"] == UnitSystem.METRIC

    def test_create_pressure_check_without_write_permission(
        self,
        api_client: APIClient,
        cylinder_fleet_with_read: CylinderFleet,
        user: User,
    ) -> None:
        """Read-only user cannot create pressure check."""
        cylinder = CylinderFactory.create(fleet=cylinder_fleet_with_read)
        install = CylinderInstallFactory.create(cylinder=cylinder)

        data = {
            "pressure": 2800,
            "unit_system": UnitSystem.IMPERIAL,
            "check_date": "2025-01-15",
        }

        response = api_client.post(
            reverse(
                "api:v1:cylinder-install-pressure-checks",
                kwargs={"install_id": install.id},
            ),
            data=data,
            format="json",
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_create_pressure_check_missing_required_fields(
        self,
        api_client: APIClient,
        cylinder_install: CylinderInstall,
        user: User,
    ) -> None:
        """Creating pressure check without required fields returns error."""
        data = {"notes": "Just notes"}

        response = api_client.post(
            reverse(
                "api:v1:cylinder-install-pressure-checks",
                kwargs={"install_id": cylinder_install.id},
            ),
            data=data,
            format="json",
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_pressure_check_unauthenticated(
        self,
        api_client: APIClient,
        cylinder_install: CylinderInstall,
    ) -> None:
        """Unauthenticated request returns 403."""
        data = {
            "pressure": 2800,
            "unit_system": UnitSystem.IMPERIAL,
            "check_date": "2025-01-15",
        }

        response = api_client.post(
            reverse(
                "api:v1:cylinder-install-pressure-checks",
                kwargs={"install_id": cylinder_install.id},
            ),
            data=data,
            format="json",
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestCylinderPressureCheckRetrieveUpdateDelete:
    """Tests for retrieving, updating, and deleting pressure checks."""

    def test_retrieve_pressure_check(
        self,
        api_client: APIClient,
        cylinder_install: CylinderInstall,
        pressure_check: CylinderPressureCheck,
        user: User,
    ) -> None:
        """User can retrieve pressure check details."""
        response = api_client.get(
            reverse(
                "api:v1:cylinder-pressure-check-detail",
                kwargs={
                    "install_id": cylinder_install.id,
                    "check_id": pressure_check.id,
                },
            ),
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"]["id"] == str(pressure_check.id)
        assert response.data["data"]["pressure"] == pressure_check.pressure

    def test_retrieve_pressure_check_no_permission(
        self,
        api_client: APIClient,
        user: User,
    ) -> None:
        """User without fleet access cannot retrieve pressure check."""
        install = CylinderInstallFactory.create()
        check = CylinderPressureCheckFactory.create(install=install)

        response = api_client.get(
            reverse(
                "api:v1:cylinder-pressure-check-detail",
                kwargs={"install_id": install.id, "check_id": check.id},
            ),
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_update_pressure_check(
        self,
        api_client: APIClient,
        cylinder_install: CylinderInstall,
        pressure_check: CylinderPressureCheck,
        user: User,
    ) -> None:
        """User can update pressure check."""
        data = {"pressure": 2500, "notes": "Updated reading"}

        response = api_client.patch(
            reverse(
                "api:v1:cylinder-pressure-check-detail",
                kwargs={
                    "install_id": cylinder_install.id,
                    "check_id": pressure_check.id,
                },
            ),
            data=data,
            format="json",
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"]["pressure"] == 2500  # noqa: PLR2004 - valid PSI
        assert response.data["data"]["notes"] == "Updated reading"

    def test_update_pressure_check_unit_system(
        self,
        api_client: APIClient,
        cylinder_install: CylinderInstall,
        pressure_check: CylinderPressureCheck,
        user: User,
    ) -> None:
        """User can update pressure and unit system."""

        data = {"pressure": 200, "unit_system": UnitSystem.METRIC}

        response = api_client.patch(
            reverse(
                "api:v1:cylinder-pressure-check-detail",
                kwargs={
                    "install_id": cylinder_install.id,
                    "check_id": pressure_check.id,
                },
            ),
            data=data,
            format="json",
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"]["pressure"] == 200  # noqa: PLR2004
        assert response.data["data"]["unit_system"] == UnitSystem.METRIC

    def test_update_pressure_check_without_write_permission(
        self,
        api_client: APIClient,
        cylinder_fleet_with_read: CylinderFleet,
        user: User,
    ) -> None:
        """Read-only user cannot update pressure check."""
        cylinder = CylinderFactory.create(fleet=cylinder_fleet_with_read)
        install = CylinderInstallFactory.create(cylinder=cylinder)
        check = CylinderPressureCheckFactory.create(install=install)

        data = {"pressure": 2500}

        response = api_client.patch(
            reverse(
                "api:v1:cylinder-pressure-check-detail",
                kwargs={"install_id": install.id, "check_id": check.id},
            ),
            data=data,
            format="json",
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_delete_pressure_check(
        self,
        api_client: APIClient,
        cylinder_install: CylinderInstall,
        pressure_check: CylinderPressureCheck,
        user: User,
    ) -> None:
        """User can delete pressure check."""
        check_id = pressure_check.id

        response = api_client.delete(
            reverse(
                "api:v1:cylinder-pressure-check-detail",
                kwargs={
                    "install_id": cylinder_install.id,
                    "check_id": check_id,
                },
            ),
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK
        assert not CylinderPressureCheck.objects.filter(id=check_id).exists()

    def test_delete_pressure_check_without_write_permission(
        self,
        api_client: APIClient,
        cylinder_fleet_with_read: CylinderFleet,
        user: User,
    ) -> None:
        """Read-only user cannot delete pressure check."""
        cylinder = CylinderFactory.create(fleet=cylinder_fleet_with_read)
        install = CylinderInstallFactory.create(cylinder=cylinder)
        check = CylinderPressureCheckFactory.create(install=install)

        response = api_client.delete(
            reverse(
                "api:v1:cylinder-pressure-check-detail",
                kwargs={"install_id": install.id, "check_id": check.id},
            ),
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestCylinderPressureCheckValidation:
    """Tests for pressure check validation."""

    def test_pressure_validation_imperial_max(
        self,
        api_client: APIClient,
        cylinder_install: CylinderInstall,
        user: User,
    ) -> None:
        """Imperial pressure cannot exceed 5000 PSI."""
        data = {
            "pressure": 5500,
            "unit_system": UnitSystem.IMPERIAL,
            "check_date": "2025-01-15",
        }

        response = api_client.post(
            reverse(
                "api:v1:cylinder-install-pressure-checks",
                kwargs={"install_id": cylinder_install.id},
            ),
            data=data,
            format="json",
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "pressure" in response.data["errors"]
        # Verify error message is descriptive
        assert "Maximum pressure for PSI is 5000" in str(
            response.data["errors"]["pressure"]
        )

    def test_pressure_validation_metric_max(
        self,
        api_client: APIClient,
        cylinder_install: CylinderInstall,
        user: User,
    ) -> None:
        """Metric pressure cannot exceed 400 BAR."""
        data = {
            "pressure": 450,
            "unit_system": UnitSystem.METRIC,
            "check_date": "2025-01-15",
        }

        response = api_client.post(
            reverse(
                "api:v1:cylinder-install-pressure-checks",
                kwargs={"install_id": cylinder_install.id},
            ),
            data=data,
            format="json",
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "pressure" in response.data["errors"]
        # Verify error message is descriptive
        assert "Maximum pressure for BAR is 400" in str(
            response.data["errors"]["pressure"]
        )

    def test_pressure_validation_negative(
        self,
        api_client: APIClient,
        cylinder_install: CylinderInstall,
        user: User,
    ) -> None:
        """Pressure cannot be negative."""
        data = {
            "pressure": -100,
            "unit_system": UnitSystem.IMPERIAL,
            "check_date": "2025-01-15",
        }

        response = api_client.post(
            reverse(
                "api:v1:cylinder-install-pressure-checks",
                kwargs={"install_id": cylinder_install.id},
            ),
            data=data,
            format="json",
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "pressure" in response.data["errors"]
        # Verify error message is descriptive (Django's MinValueValidator message)
        error_msg = str(response.data["errors"]["pressure"]).lower()
        assert "greater than or equal to 0" in error_msg or "positive" in error_msg

    def test_error_response_format_is_readable(
        self,
        api_client: APIClient,
        cylinder_install: CylinderInstall,
        user: User,
    ) -> None:
        """Verify that validation errors return readable, structured error messages."""
        # Test with multiple validation errors
        data = {
            "pressure": 6000,  # Exceeds max for both PSI (5000) and BAR (400)
            "unit_system": UnitSystem.IMPERIAL,
            "check_date": "2025-01-15",
        }

        response = api_client.post(
            reverse(
                "api:v1:cylinder-install-pressure-checks",
                kwargs={"install_id": cylinder_install.id},
            ),
            data=data,
            format="json",
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        # Verify response structure
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "errors" in response.data, "Error response must contain 'errors' key"
        assert "success" in response.data, "Error response must contain 'success' key"
        assert response.data["success"] is False, "success must be False on errors"

        # Verify errors are in the expected format (field -> list of messages)
        errors = response.data["errors"]
        assert isinstance(errors, dict), "Errors must be a dictionary"
        assert "pressure" in errors, "Field-specific errors must be keyed by field name"

        # Verify error messages are human-readable strings
        pressure_errors = errors["pressure"]
        assert isinstance(pressure_errors, list), "Field errors must be a list"
        assert len(pressure_errors) > 0, "Field errors must have at least one message"
        assert isinstance(pressure_errors[0], str), "Error messages must be strings"
        assert len(pressure_errors[0]) > 10, "Error messages must be descriptive"  # noqa: PLR2004

        # Verify the error message contains useful context
        error_message = pressure_errors[0]
        assert "5000" in error_message or "PSI" in error_message, (
            f"Error message should mention the limit or unit: {error_message}"
        )

    def test_missing_required_field_error_message(
        self,
        api_client: APIClient,
        cylinder_install: CylinderInstall,
        user: User,
    ) -> None:
        """Verify that missing required fields return clear error messages."""
        # Missing pressure and unit_system
        data = {
            "check_date": "2025-01-15",
            "notes": "Test",
        }

        response = api_client.post(
            reverse(
                "api:v1:cylinder-install-pressure-checks",
                kwargs={"install_id": cylinder_install.id},
            ),
            data=data,
            format="json",
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "errors" in response.data

        errors = response.data["errors"]
        # Should have errors for missing required fields
        assert "pressure" in errors or "unit_system" in errors, (
            f"Missing required fields should be reported: {errors}"
        )

        # Error messages should be human-readable
        for field, messages in errors.items():
            for msg in messages:
                assert isinstance(msg, str), f"Error message for {field} must be string"
                assert len(msg) > 0, f"Error message for {field} must not be empty"

    def test_pressure_check_includes_install_info(
        self,
        api_client: APIClient,
        cylinder_install: CylinderInstall,
        pressure_check: CylinderPressureCheck,
        user: User,
    ) -> None:
        """Pressure check response includes install information."""
        response = api_client.get(
            reverse(
                "api:v1:cylinder-pressure-check-detail",
                kwargs={
                    "install_id": cylinder_install.id,
                    "check_id": pressure_check.id,
                },
            ),
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK
        assert "install_id" in response.data["data"]
        assert "cylinder_id" in response.data["data"]
        assert "cylinder_name" in response.data["data"]
        assert "location_name" in response.data["data"]

    def test_full_update_put(
        self,
        api_client: APIClient,
        cylinder_install: CylinderInstall,
        pressure_check: CylinderPressureCheck,
        user: User,
    ) -> None:
        """PUT requires all fields."""
        data = {
            "pressure": 200,  # Valid BAR pressure (max 400)
            "unit_system": UnitSystem.METRIC,
            "check_date": "2025-01-20",
            "notes": "Full update",
            "user": user.email,
        }

        response = api_client.put(
            reverse(
                "api:v1:cylinder-pressure-check-detail",
                kwargs={
                    "install_id": cylinder_install.id,
                    "check_id": pressure_check.id,
                },
            ),
            data=data,
            format="json",
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"]["pressure"] == 200  # noqa: PLR2004 - valid BAR
        assert response.data["data"]["notes"] == "Full update"
        assert response.data["data"]["check_date"] == "2025-01-20"
