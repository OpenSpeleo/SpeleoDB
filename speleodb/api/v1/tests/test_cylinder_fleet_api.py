# -*- coding: utf-8 -*-

"""
Comprehensive test suite for Cylinder Fleet API endpoints.

Tests cover:
- Cylinder Fleet CRUD operations
- Cylinder CRUD operations
- Permission management
- Access control at different permission levels
- Edge cases and validation
"""

from __future__ import annotations

from datetime import date
from datetime import timedelta
from typing import TYPE_CHECKING

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from speleodb.api.v1.tests.factories import CylinderFactory
from speleodb.api.v1.tests.factories import CylinderFleetFactory
from speleodb.api.v1.tests.factories import CylinderFleetUserPermissionFactory
from speleodb.api.v1.tests.factories import CylinderInstallFactory
from speleodb.common.enums import InstallStatus
from speleodb.common.enums import PermissionLevel
from speleodb.common.enums import UnitSystem
from speleodb.gis.models import Cylinder
from speleodb.gis.models import CylinderFleet
from speleodb.gis.models import CylinderFleetUserPermission
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
def cylinder_fleet(user: User) -> CylinderFleet:
    """Create a cylinder fleet."""
    return CylinderFleetFactory.create(created_by=user.email)


@pytest.fixture
def cylinder_fleet_with_admin(user: User) -> CylinderFleet:
    """Create a cylinder fleet with admin permission for user."""
    fleet = CylinderFleetFactory.create(created_by=user.email)
    CylinderFleetUserPermissionFactory(
        user=user,
        cylinder_fleet=fleet,
        level=PermissionLevel.ADMIN,
    )
    return fleet


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
def cylinder(cylinder_fleet_with_admin: CylinderFleet) -> Cylinder:
    """Create a cylinder in a fleet."""
    return CylinderFactory.create(fleet=cylinder_fleet_with_admin)


# ================== HELPER FUNCTIONS ================== #


def get_auth_header(user: User) -> str:
    """Get authorization header for user."""
    token, _ = Token.objects.get_or_create(user=user)
    return f"Token {token.key}"


# ================== TEST CLASSES ================== #


@pytest.mark.django_db
class TestCylinderFleetListCreate:
    """Tests for listing and creating cylinder fleets."""

    def test_list_cylinder_fleets_authenticated(
        self,
        api_client: APIClient,
        user: User,
    ) -> None:
        """Authenticated user can list their accessible fleets."""
        n_fleet = 2
        fleets = CylinderFleetFactory.create_batch(n_fleet, created_by=user.email)

        CylinderFleetUserPermissionFactory.create(user=user, cylinder_fleet=fleets[0])
        CylinderFleetUserPermissionFactory.create(user=user, cylinder_fleet=fleets[1])

        CylinderFleetFactory()

        response = api_client.get(
            reverse("api:v1:cylinder-fleets"),
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["data"]) == n_fleet

    def test_list_cylinder_fleets_with_multiple_permissions(
        self,
        api_client: APIClient,
        user: User,
    ) -> None:
        """Fleets show correct permission levels."""
        fleet_read = CylinderFleetFactory(created_by=user.email)
        fleet_write = CylinderFleetFactory(created_by=user.email)
        fleet_admin = CylinderFleetFactory(created_by=user.email)

        CylinderFleetUserPermissionFactory(
            user=user, cylinder_fleet=fleet_read, level=PermissionLevel.READ_ONLY
        )
        CylinderFleetUserPermissionFactory(
            user=user, cylinder_fleet=fleet_write, level=PermissionLevel.READ_AND_WRITE
        )
        CylinderFleetUserPermissionFactory(
            user=user, cylinder_fleet=fleet_admin, level=PermissionLevel.ADMIN
        )

        response = api_client.get(
            reverse("api:v1:cylinder-fleets"),
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK
        fleets = response.data["data"]

        permission_levels = [f["user_permission_level"] for f in fleets]
        assert PermissionLevel.READ_ONLY in permission_levels
        assert PermissionLevel.READ_AND_WRITE in permission_levels
        assert PermissionLevel.ADMIN in permission_levels

    def test_list_cylinder_fleets_includes_cylinder_count(
        self,
        api_client: APIClient,
        cylinder_fleet_with_admin: CylinderFleet,
        user: User,
    ) -> None:
        """Fleet listing includes accurate cylinder count."""
        n_cylinders = 3
        CylinderFactory.create_batch(n_cylinders, fleet=cylinder_fleet_with_admin)

        response = api_client.get(
            reverse("api:v1:cylinder-fleets"),
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK
        fleet_data = response.data["data"][0]
        assert fleet_data["cylinder_count"] == n_cylinders

    def test_list_cylinder_fleets_empty(
        self,
        api_client: APIClient,
        user: User,
    ) -> None:
        """User with no fleet access gets empty list."""
        CylinderFleetFactory()

        response = api_client.get(
            reverse("api:v1:cylinder-fleets"),
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"] == []

    def test_create_cylinder_fleet_valid(
        self,
        api_client: APIClient,
        user: User,
    ) -> None:
        """User can create a cylinder fleet and gets ADMIN permission."""
        data = {
            "name": "Test Fleet",
            "description": "Test Description",
            "is_active": True,
        }

        response = api_client.post(
            reverse("api:v1:cylinder-fleets"),
            data=data,
            format="json",
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["data"]["name"] == "Test Fleet"
        assert response.data["data"]["created_by"] == user.email

        fleet_id = response.data["data"]["id"]
        perm = CylinderFleetUserPermission.objects.get(
            user=user, cylinder_fleet_id=fleet_id
        )
        assert perm.level == PermissionLevel.ADMIN

    def test_create_cylinder_fleet_with_initial_cylinders(
        self,
        api_client: APIClient,
        user: User,
    ) -> None:
        """User can create fleet with initial cylinders in one request."""
        data = {
            "name": "Fleet with Cylinders",
            "description": "Test",
        }

        response = api_client.post(
            reverse("api:v1:cylinder-fleets"),
            data=data,
            format="json",
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_201_CREATED

    def test_create_cylinder_fleet_invalid_name(
        self,
        api_client: APIClient,
        user: User,
    ) -> None:
        """Creating fleet with invalid name returns validation error."""
        data = {"name": "", "description": "Test"}

        response = api_client.post(
            reverse("api:v1:cylinder-fleets"),
            data=data,
            format="json",
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "name" in response.data["errors"]

    def test_create_cylinder_fleet_unauthenticated(
        self,
        api_client: APIClient,
    ) -> None:
        """Unauthenticated request returns 401."""
        data = {"name": "Test Fleet"}

        response = api_client.post(
            reverse("api:v1:cylinder-fleets"),
            data=data,
            format="json",
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestCylinderFleetRetrieveUpdateDelete:
    """Tests for retrieving, updating, and deleting cylinder fleets."""

    def test_retrieve_cylinder_fleet_as_admin(
        self,
        api_client: APIClient,
        cylinder_fleet_with_admin: CylinderFleet,
        user: User,
    ) -> None:
        """Admin can retrieve fleet details."""
        response = api_client.get(
            reverse(
                "api:v1:cylinder-fleet-detail",
                kwargs={"fleet_id": cylinder_fleet_with_admin.id},
            ),
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"]["id"] == str(cylinder_fleet_with_admin.id)
        assert response.data["data"]["name"] == cylinder_fleet_with_admin.name

    def test_retrieve_cylinder_fleet_as_read_only(
        self,
        api_client: APIClient,
        cylinder_fleet_with_read: CylinderFleet,
        user: User,
    ) -> None:
        """Read-only user can view fleet."""
        response = api_client.get(
            reverse(
                "api:v1:cylinder-fleet-detail",
                kwargs={"fleet_id": cylinder_fleet_with_read.id},
            ),
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK

    def test_retrieve_cylinder_fleet_no_permission(
        self,
        api_client: APIClient,
        user: User,
    ) -> None:
        """User without permission gets 403."""
        fleet = CylinderFleetFactory.create()

        response = api_client.get(
            reverse("api:v1:cylinder-fleet-detail", kwargs={"fleet_id": fleet.id}),
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_update_cylinder_fleet_as_write(
        self,
        api_client: APIClient,
        cylinder_fleet_with_write: CylinderFleet,
        user: User,
    ) -> None:
        """Write user can update fleet."""
        data = {
            "name": "Updated Name",
            "description": "Updated Description",
        }

        response = api_client.patch(
            reverse(
                "api:v1:cylinder-fleet-detail",
                kwargs={"fleet_id": cylinder_fleet_with_write.id},
            ),
            data=data,
            format="json",
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"]["name"] == "Updated Name"

        cylinder_fleet_with_write.refresh_from_db()
        assert cylinder_fleet_with_write.name == "Updated Name"

    def test_update_cylinder_fleet_as_read_only(
        self,
        api_client: APIClient,
        cylinder_fleet_with_read: CylinderFleet,
        user: User,
    ) -> None:
        """Read-only user cannot update fleet."""
        data = {"name": "Updated Name"}

        response = api_client.patch(
            reverse(
                "api:v1:cylinder-fleet-detail",
                kwargs={"fleet_id": cylinder_fleet_with_read.id},
            ),
            data=data,
            format="json",
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_partial_update_cylinder_fleet(
        self,
        api_client: APIClient,
        cylinder_fleet_with_write: CylinderFleet,
        user: User,
    ) -> None:
        """PATCH allows partial updates."""
        original_description = cylinder_fleet_with_write.description
        data = {"name": "New Name Only"}

        response = api_client.patch(
            reverse(
                "api:v1:cylinder-fleet-detail",
                kwargs={"fleet_id": cylinder_fleet_with_write.id},
            ),
            data=data,
            format="json",
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK
        cylinder_fleet_with_write.refresh_from_db()
        assert cylinder_fleet_with_write.name == "New Name Only"
        assert cylinder_fleet_with_write.description == original_description

    def test_delete_cylinder_fleet_as_admin(
        self,
        api_client: APIClient,
        cylinder_fleet_with_admin: CylinderFleet,
        user: User,
    ) -> None:
        """Admin can deactivate fleet."""
        response = api_client.delete(
            reverse(
                "api:v1:cylinder-fleet-detail",
                kwargs={"fleet_id": cylinder_fleet_with_admin.id},
            ),
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK

        cylinder_fleet_with_admin.refresh_from_db()
        assert cylinder_fleet_with_admin.is_active is False

    def test_delete_cylinder_fleet_as_write(
        self,
        api_client: APIClient,
        cylinder_fleet_with_write: CylinderFleet,
        user: User,
    ) -> None:
        """Write user cannot delete fleet."""
        response = api_client.delete(
            reverse(
                "api:v1:cylinder-fleet-detail",
                kwargs={"fleet_id": cylinder_fleet_with_write.id},
            ),
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_delete_cascades_to_permissions(
        self,
        api_client: APIClient,
        cylinder_fleet_with_admin: CylinderFleet,
        user: User,
        other_user: User,
    ) -> None:
        """Deleting fleet deactivates all permissions."""
        CylinderFleetUserPermissionFactory(
            user=other_user,
            cylinder_fleet=cylinder_fleet_with_admin,
            level=PermissionLevel.READ_ONLY,
        )

        response = api_client.delete(
            reverse(
                "api:v1:cylinder-fleet-detail",
                kwargs={"fleet_id": cylinder_fleet_with_admin.id},
            ),
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK

        perms = CylinderFleetUserPermission.objects.filter(
            cylinder_fleet=cylinder_fleet_with_admin
        )
        assert all(not p.is_active for p in perms)

    def test_update_invalid_data(
        self,
        api_client: APIClient,
        cylinder_fleet_with_write: CylinderFleet,
        user: User,
    ) -> None:
        """Invalid data returns validation errors."""
        data = {"name": "x" * 100}

        response = api_client.patch(
            reverse(
                "api:v1:cylinder-fleet-detail",
                kwargs={"fleet_id": cylinder_fleet_with_write.id},
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
            reverse("api:v1:cylinder-fleet-detail", kwargs={"fleet_id": fake_uuid}),
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestCylinderListCreate:
    """Tests for listing and creating cylinders in a fleet."""

    def test_list_cylinders_in_fleet(
        self,
        api_client: APIClient,
        cylinder_fleet_with_admin: CylinderFleet,
        user: User,
    ) -> None:
        """User can list all cylinders in a fleet."""
        n_cylinders = 3
        CylinderFactory.create_batch(n_cylinders, fleet=cylinder_fleet_with_admin)

        response = api_client.get(
            reverse(
                "api:v1:cylinder-fleet-cylinders",
                kwargs={"fleet_id": cylinder_fleet_with_admin.id},
            ),
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["data"]) == n_cylinders

    def test_create_cylinder_valid(
        self,
        api_client: APIClient,
        cylinder_fleet_with_write: CylinderFleet,
        user: User,
    ) -> None:
        """User with write access can create cylinder."""
        data = {
            "name": "New Cylinder",
            "o2_percentage": 21,
            "he_percentage": 0,
            "pressure": 3000,
            "unit_system": UnitSystem.IMPERIAL,
        }

        response = api_client.post(
            reverse(
                "api:v1:cylinder-fleet-cylinders",
                kwargs={"fleet_id": cylinder_fleet_with_write.id},
            ),
            data=data,
            format="json",
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["data"]["name"] == "New Cylinder"

    def test_create_cylinder_read_only_forbidden(
        self,
        api_client: APIClient,
        cylinder_fleet_with_read: CylinderFleet,
        user: User,
    ) -> None:
        """Read-only user cannot create cylinder."""
        data = {
            "name": "New Cylinder",
            "o2_percentage": 21,
            "he_percentage": 0,
            "pressure": 3000,
            "unit_system": UnitSystem.IMPERIAL,
        }

        response = api_client.post(
            reverse(
                "api:v1:cylinder-fleet-cylinders",
                kwargs={"fleet_id": cylinder_fleet_with_read.id},
            ),
            data=data,
            format="json",
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_create_cylinder_missing_required_fields(
        self,
        api_client: APIClient,
        cylinder_fleet_with_write: CylinderFleet,
        user: User,
    ) -> None:
        """Missing required fields returns validation error."""
        data = {"name": "Incomplete Cylinder"}

        response = api_client.post(
            reverse(
                "api:v1:cylinder-fleet-cylinders",
                kwargs={"fleet_id": cylinder_fleet_with_write.id},
            ),
            data=data,
            format="json",
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_cylinder_with_dates(
        self,
        api_client: APIClient,
        cylinder_fleet_with_write: CylinderFleet,
        user: User,
    ) -> None:
        """User can create cylinder with manufactured and inspection dates."""
        data = {
            "name": "Dated Cylinder",
            "o2_percentage": 32,
            "he_percentage": 0,
            "pressure": 3000,
            "unit_system": UnitSystem.IMPERIAL,
            "manufactured_date": "2020-06-15",
            "last_visual_inspection_date": "2023-03-10",
            "last_hydrostatic_test_date": "2022-08-20",
        }

        response = api_client.post(
            reverse(
                "api:v1:cylinder-fleet-cylinders",
                kwargs={"fleet_id": cylinder_fleet_with_write.id},
            ),
            data=data,
            format="json",
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["data"]["manufactured_date"] == "2020-06-15"
        assert response.data["data"]["last_visual_inspection_date"] == "2023-03-10"
        assert response.data["data"]["last_hydrostatic_test_date"] == "2022-08-20"

    def test_create_cylinder_with_null_dates(
        self,
        api_client: APIClient,
        cylinder_fleet_with_write: CylinderFleet,
        user: User,
    ) -> None:
        """User can create cylinder without optional date fields."""
        data = {
            "name": "No Dates Cylinder",
            "o2_percentage": 21,
            "he_percentage": 0,
            "pressure": 3000,
            "unit_system": UnitSystem.IMPERIAL,
        }

        response = api_client.post(
            reverse(
                "api:v1:cylinder-fleet-cylinders",
                kwargs={"fleet_id": cylinder_fleet_with_write.id},
            ),
            data=data,
            format="json",
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["data"]["manufactured_date"] is None
        assert response.data["data"]["last_visual_inspection_date"] is None
        assert response.data["data"]["last_hydrostatic_test_date"] is None


@pytest.mark.django_db
class TestCylinderRetrieveUpdateDelete:
    """Tests for retrieving, updating, and deleting cylinders."""

    def test_retrieve_cylinder(
        self,
        api_client: APIClient,
        cylinder: Cylinder,
        user: User,
    ) -> None:
        """User can retrieve cylinder details."""
        response = api_client.get(
            reverse("api:v1:cylinder-detail", kwargs={"id": cylinder.id}),
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"]["id"] == str(cylinder.id)

    def test_update_cylinder(
        self,
        api_client: APIClient,
        cylinder_fleet_with_write: CylinderFleet,
        user: User,
    ) -> None:
        """User can update cylinder."""
        cylinder = CylinderFactory.create(fleet=cylinder_fleet_with_write)
        data = {"name": "Updated Cylinder", "owner": "New Owner"}

        response = api_client.patch(
            reverse("api:v1:cylinder-detail", kwargs={"id": cylinder.id}),
            data=data,
            format="json",
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"]["name"] == "Updated Cylinder"

    def test_update_cylinder_dates(
        self,
        api_client: APIClient,
        cylinder_fleet_with_write: CylinderFleet,
        user: User,
    ) -> None:
        """User can update cylinder date fields."""
        cylinder = CylinderFactory.create(
            fleet=cylinder_fleet_with_write,
            manufactured_date=None,
        )
        data = {
            "manufactured_date": "2019-01-15",
            "last_visual_inspection_date": "2024-01-10",
            "last_hydrostatic_test_date": "2023-06-20",
        }

        response = api_client.patch(
            reverse("api:v1:cylinder-detail", kwargs={"id": cylinder.id}),
            data=data,
            format="json",
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"]["manufactured_date"] == "2019-01-15"
        assert response.data["data"]["last_visual_inspection_date"] == "2024-01-10"
        assert response.data["data"]["last_hydrostatic_test_date"] == "2023-06-20"

    def test_update_cylinder_clear_dates(
        self,
        api_client: APIClient,
        cylinder_fleet_with_write: CylinderFleet,
        user: User,
    ) -> None:
        """User can clear cylinder date fields by setting to null."""

        cylinder = CylinderFactory.create(
            fleet=cylinder_fleet_with_write,
            manufactured_date=date(2020, 1, 1),
            last_visual_inspection_date=date(2023, 1, 1),
            last_hydrostatic_test_date=date(2022, 1, 1),
        )
        data = {
            "manufactured_date": None,
            "last_visual_inspection_date": None,
            "last_hydrostatic_test_date": None,
        }

        response = api_client.patch(
            reverse("api:v1:cylinder-detail", kwargs={"id": cylinder.id}),
            data=data,
            format="json",
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"]["manufactured_date"] is None
        assert response.data["data"]["last_visual_inspection_date"] is None
        assert response.data["data"]["last_hydrostatic_test_date"] is None

    def test_update_cylinder_without_write_permission(
        self,
        api_client: APIClient,
        cylinder_fleet_with_read: CylinderFleet,
        user: User,
    ) -> None:
        """Read-only user cannot update cylinder."""
        cylinder = CylinderFactory.create(fleet=cylinder_fleet_with_read)

        response = api_client.patch(
            reverse("api:v1:cylinder-detail", kwargs={"id": cylinder.id}),
            data={"name": "Updated Cylinder"},
            format="json",
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_delete_cylinder(
        self,
        api_client: APIClient,
        cylinder_fleet_with_write: CylinderFleet,
        user: User,
    ) -> None:
        """User can delete cylinder."""
        cylinder = CylinderFactory.create(fleet=cylinder_fleet_with_write)

        response = api_client.delete(
            reverse("api:v1:cylinder-detail", kwargs={"id": cylinder.id}),
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK
        assert not Cylinder.objects.filter(id=cylinder.id).exists()

    def test_delete_cylinder_without_write_permission(
        self,
        api_client: APIClient,
        cylinder_fleet_with_read: CylinderFleet,
        user: User,
    ) -> None:
        """Read-only user cannot delete cylinder."""
        cylinder = CylinderFactory.create(fleet=cylinder_fleet_with_read)

        response = api_client.delete(
            reverse("api:v1:cylinder-detail", kwargs={"id": cylinder.id}),
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestCylinderFleetPermissions:
    """Tests for fleet permission management."""

    def test_list_fleet_permissions(
        self,
        api_client: APIClient,
        cylinder_fleet_with_admin: CylinderFleet,
        user: User,
        other_user: User,
    ) -> None:
        """Admin can list all permissions for fleet."""
        CylinderFleetUserPermissionFactory(
            user=other_user,
            cylinder_fleet=cylinder_fleet_with_admin,
            level=PermissionLevel.READ_ONLY,
        )

        response = api_client.get(
            reverse(
                "api:v1:cylinder-fleet-permissions",
                kwargs={"fleet_id": cylinder_fleet_with_admin.id},
            ),
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["data"]) >= 2  # noqa: PLR2004

    def test_grant_permission_as_admin(
        self,
        api_client: APIClient,
        cylinder_fleet_with_admin: CylinderFleet,
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
                "api:v1:cylinder-fleet-permissions",
                kwargs={"fleet_id": cylinder_fleet_with_admin.id},
            ),
            data=data,
            format="json",
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert CylinderFleetUserPermission.objects.filter(
            user=other_user, cylinder_fleet=cylinder_fleet_with_admin
        ).exists()

    def test_grant_permission_as_non_admin(
        self,
        api_client: APIClient,
        cylinder_fleet_with_write: CylinderFleet,
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
                "api:v1:cylinder-fleet-permissions",
                kwargs={"fleet_id": cylinder_fleet_with_write.id},
            ),
            data=data,
            format="json",
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_revoke_permission_as_admin(
        self,
        api_client: APIClient,
        cylinder_fleet_with_admin: CylinderFleet,
        user: User,
        other_user: User,
    ) -> None:
        """Admin can revoke other users' permissions."""
        perm = CylinderFleetUserPermissionFactory.create(
            user=other_user,
            cylinder_fleet=cylinder_fleet_with_admin,
            level=PermissionLevel.READ_ONLY,
        )

        response = api_client.delete(
            reverse(
                "api:v1:cylinder-fleet-permissions",
                kwargs={"fleet_id": cylinder_fleet_with_admin.id},
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
        cylinder_fleet_with_admin: CylinderFleet,
        user: User,
    ) -> None:
        """User cannot revoke their own permission."""
        _ = CylinderFleetUserPermission.objects.get(
            user=user, cylinder_fleet=cylinder_fleet_with_admin
        )

        response = api_client.delete(
            reverse(
                "api:v1:cylinder-fleet-permissions",
                kwargs={"fleet_id": cylinder_fleet_with_admin.id},
            ),
            data={"user": user.email},
            format="json",
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_update_permission_as_admin(
        self,
        api_client: APIClient,
        cylinder_fleet_with_admin: CylinderFleet,
        user: User,
        other_user: User,
    ) -> None:
        """Admin can update a user's permission level."""
        _ = CylinderFleetUserPermissionFactory.create(
            user=other_user,
            cylinder_fleet=cylinder_fleet_with_admin,
            level=PermissionLevel.READ_ONLY,
        )

        response = api_client.put(
            reverse(
                "api:v1:cylinder-fleet-permissions",
                kwargs={"fleet_id": cylinder_fleet_with_admin.id},
            ),
            data={
                "user": other_user.email,
                "level": PermissionLevel.READ_AND_WRITE.label,
            },
            format="json",
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK

    def test_invalid_permission_level(
        self,
        api_client: APIClient,
        cylinder_fleet_with_admin: CylinderFleet,
        user: User,
        other_user: User,
    ) -> None:
        """Invalid permission level returns 400."""
        response = api_client.post(
            reverse(
                "api:v1:cylinder-fleet-permissions",
                kwargs={"fleet_id": cylinder_fleet_with_admin.id},
            ),
            data={"user": other_user.email, "level": "INVALID"},
            format="json",
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_invalid_user_email(
        self,
        api_client: APIClient,
        cylinder_fleet_with_admin: CylinderFleet,
        user: User,
    ) -> None:
        """Invalid user email returns error."""
        response = api_client.post(
            reverse(
                "api:v1:cylinder-fleet-permissions",
                kwargs={"fleet_id": cylinder_fleet_with_admin.id},
            ),
            data={"user": "missing@example.com", "level": "READ_ONLY"},
            format="json",
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestCylinderFleetPermissionLevels:
    """Tests for permission-based access control."""

    def test_read_only_cannot_update_fleet(
        self,
        api_client: APIClient,
        cylinder_fleet_with_read: CylinderFleet,
        user: User,
    ) -> None:
        """Read-only user cannot update fleet."""
        data = {"name": "Updated"}

        response = api_client.patch(
            reverse(
                "api:v1:cylinder-fleet-detail",
                kwargs={"fleet_id": cylinder_fleet_with_read.id},
            ),
            data=data,
            format="json",
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_read_and_write_cannot_delete(
        self,
        api_client: APIClient,
        cylinder_fleet_with_write: CylinderFleet,
        user: User,
    ) -> None:
        """Write user cannot delete fleet."""
        response = api_client.delete(
            reverse(
                "api:v1:cylinder-fleet-detail",
                kwargs={"fleet_id": cylinder_fleet_with_write.id},
            ),
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_admin_can_delete(
        self,
        api_client: APIClient,
        cylinder_fleet_with_admin: CylinderFleet,
        user: User,
    ) -> None:
        """Admin can delete fleet."""
        response = api_client.delete(
            reverse(
                "api:v1:cylinder-fleet-detail",
                kwargs={"fleet_id": cylinder_fleet_with_admin.id},
            ),
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK

    def test_unauthenticated_blocked(self, api_client: APIClient) -> None:
        """Unauthenticated requests are blocked."""
        fleet = CylinderFleetFactory.create()

        response = api_client.get(
            reverse("api:v1:cylinder-fleet-detail", kwargs={"fleet_id": fleet.id})
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_inactive_fleet_not_listed(self, api_client: APIClient, user: User) -> None:
        """Inactive fleets are not listed."""
        fleet = CylinderFleetFactory(created_by=user.email, is_active=False)
        CylinderFleetUserPermissionFactory(user=user, cylinder_fleet=fleet)

        response = api_client.get(
            reverse("api:v1:cylinder-fleets"),
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["data"]) == 0


@pytest.mark.django_db
class TestCylinderFleetEdgeCases:
    """Edge cases and integration tests."""

    def test_fleet_name_max_length(self, api_client: APIClient, user: User) -> None:
        """Fleet name cannot exceed 50 characters."""
        data = {"name": "x" * 51}

        response = api_client.post(
            reverse("api:v1:cylinder-fleets"),
            data=data,
            format="json",
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_cylinder_name_max_length(
        self,
        api_client: APIClient,
        cylinder_fleet_with_write: CylinderFleet,
        user: User,
    ) -> None:
        """Cylinder name cannot exceed 50 characters."""
        data = {
            "name": "x" * 51,
            "o2_percentage": 21,
            "he_percentage": 0,
            "pressure": 3000,
            "unit_system": UnitSystem.IMPERIAL,
        }

        response = api_client.post(
            reverse(
                "api:v1:cylinder-fleet-cylinders",
                kwargs={"fleet_id": cylinder_fleet_with_write.id},
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
            reverse("api:v1:cylinder-fleets"),
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
            reverse("api:v1:cylinder-fleets"),
            data=data,
            format="json",
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["data"]["name"] == "Fleet™ 测试 🚀"


@pytest.mark.django_db
class TestCylinderFleetExport:
    """Tests for exporting cylinder fleet data to Excel."""

    def test_export_cylinders_excel(
        self,
        api_client: APIClient,
        cylinder_fleet_with_read: CylinderFleet,
        user: User,
    ) -> None:
        """Read-only user can export cylinders to Excel."""
        cylinder1 = CylinderFactory.create(
            fleet=cylinder_fleet_with_read, name="Cylinder 1"
        )
        _ = CylinderFactory.create(fleet=cylinder_fleet_with_read, name="Cylinder 2")

        CylinderInstallFactory.create(
            cylinder=cylinder1,
            status=InstallStatus.INSTALLED,
        )

        response = api_client.get(
            reverse(
                "api:v1:cylinder-fleet-cylinders-export",
                kwargs={"fleet_id": cylinder_fleet_with_read.id},
            ),
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK
        assert (
            response["Content-Type"]
            == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        assert "cylinder_fleet_" in response["Content-Disposition"]

    def test_export_cylinders_no_permission(
        self,
        api_client: APIClient,
        user: User,
    ) -> None:
        """User without permission cannot export."""
        fleet = CylinderFleetFactory.create()

        response = api_client.get(
            reverse(
                "api:v1:cylinder-fleet-cylinders-export",
                kwargs={"fleet_id": fleet.id},
            ),
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestCylinderFleetWatchlist:
    """Tests for cylinder fleet watchlist endpoint."""

    def test_watchlist_default_days(
        self,
        api_client: APIClient,
        cylinder_fleet_with_read: CylinderFleet,
        user: User,
    ) -> None:
        """Default days parameter (60) returns cylinders installed longer than 60."""
        today = timezone.localdate()

        cylinder1 = CylinderFactory.create(fleet=cylinder_fleet_with_read)
        cylinder2 = CylinderFactory.create(fleet=cylinder_fleet_with_read)
        cylinder3 = CylinderFactory.create(fleet=cylinder_fleet_with_read)

        CylinderInstallFactory.create(
            cylinder=cylinder1,
            status=InstallStatus.INSTALLED,
            install_date=today - timedelta(days=90),
            created_by=user.email,
        )

        CylinderInstallFactory.create(
            cylinder=cylinder2,
            status=InstallStatus.INSTALLED,
            install_date=today - timedelta(days=30),
            created_by=user.email,
        )

        CylinderInstallFactory.create(
            cylinder=cylinder3,
            status=InstallStatus.INSTALLED,
            install_date=today - timedelta(days=61),
            created_by=user.email,
        )

        response = api_client.get(
            reverse(
                "api:v1:cylinder-fleet-watchlist",
                kwargs={"fleet_id": cylinder_fleet_with_read.id},
            ),
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK
        cylinder_ids = {c["id"] for c in response.data["data"]}
        assert str(cylinder1.id) in cylinder_ids
        assert str(cylinder2.id) not in cylinder_ids
        assert str(cylinder3.id) in cylinder_ids

    def test_watchlist_custom_days(
        self,
        api_client: APIClient,
        cylinder_fleet_with_read: CylinderFleet,
        user: User,
    ) -> None:
        """Custom days parameter filters correctly."""
        today = timezone.localdate()

        cylinder1 = CylinderFactory.create(fleet=cylinder_fleet_with_read)
        cylinder2 = CylinderFactory.create(fleet=cylinder_fleet_with_read)

        CylinderInstallFactory.create(
            cylinder=cylinder1,
            status=InstallStatus.INSTALLED,
            install_date=today - timedelta(days=20),
            created_by=user.email,
        )

        CylinderInstallFactory.create(
            cylinder=cylinder2,
            status=InstallStatus.INSTALLED,
            install_date=today - timedelta(days=10),
            created_by=user.email,
        )

        response = api_client.get(
            reverse(
                "api:v1:cylinder-fleet-watchlist",
                kwargs={"fleet_id": cylinder_fleet_with_read.id},
            )
            + "?days=15",
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK
        cylinder_ids = {c["id"] for c in response.data["data"]}
        assert str(cylinder1.id) in cylinder_ids
        assert str(cylinder2.id) not in cylinder_ids

    def test_watchlist_empty_results(
        self,
        api_client: APIClient,
        cylinder_fleet_with_read: CylinderFleet,
        user: User,
    ) -> None:
        """No cylinders due returns empty list."""
        today = timezone.localdate()

        cylinder = CylinderFactory.create(fleet=cylinder_fleet_with_read)
        CylinderInstallFactory.create(
            cylinder=cylinder,
            status=InstallStatus.INSTALLED,
            install_date=today - timedelta(days=10),
            created_by=user.email,
        )

        response = api_client.get(
            reverse(
                "api:v1:cylinder-fleet-watchlist",
                kwargs={"fleet_id": cylinder_fleet_with_read.id},
            ),
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"] == []

    def test_watchlist_invalid_days(
        self,
        api_client: APIClient,
        cylinder_fleet_with_read: CylinderFleet,
        user: User,
    ) -> None:
        """Invalid days returns 400."""
        response = api_client.get(
            reverse(
                "api:v1:cylinder-fleet-watchlist",
                kwargs={"fleet_id": cylinder_fleet_with_read.id},
            )
            + "?days=invalid",
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_watchlist_negative_days(
        self,
        api_client: APIClient,
        cylinder_fleet_with_read: CylinderFleet,
        user: User,
    ) -> None:
        """Negative days returns 400."""
        response = api_client.get(
            reverse(
                "api:v1:cylinder-fleet-watchlist",
                kwargs={"fleet_id": cylinder_fleet_with_read.id},
            )
            + "?days=-1",
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestCylinderFleetWatchlistExport:
    """Tests for exporting cylinder fleet watchlist to Excel."""

    def test_export_watchlist_excel(
        self,
        api_client: APIClient,
        cylinder_fleet_with_read: CylinderFleet,
        user: User,
    ) -> None:
        """Read-only user can export watchlist."""
        cylinder = CylinderFactory.create(fleet=cylinder_fleet_with_read)
        CylinderInstallFactory.create(
            cylinder=cylinder,
            status=InstallStatus.INSTALLED,
            install_date=timezone.localdate() - timedelta(days=90),
            created_by=user.email,
        )

        response = api_client.get(
            reverse(
                "api:v1:cylinder-fleet-watchlist-export",
                kwargs={"fleet_id": cylinder_fleet_with_read.id},
            ),
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK
        assert (
            response["Content-Type"]
            == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        assert "cylinder_fleet_watchlist_" in response["Content-Disposition"]
