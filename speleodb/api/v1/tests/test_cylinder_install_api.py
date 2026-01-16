# -*- coding: utf-8 -*-

"""
Comprehensive test suite for Cylinder Install API endpoints.

Tests cover:
- Cylinder Install CRUD operations
- State transitions (INSTALLED → RETRIEVED/LOST/ABANDONED)
- GeoJSON endpoint
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

from speleodb.api.v1.tests.factories import CylinderFactory
from speleodb.api.v1.tests.factories import CylinderFleetFactory
from speleodb.api.v1.tests.factories import CylinderFleetUserPermissionFactory
from speleodb.api.v1.tests.factories import CylinderInstallFactory
from speleodb.api.v1.tests.factories import ProjectFactory
from speleodb.api.v1.tests.factories import UserProjectPermissionFactory
from speleodb.common.enums import InstallStatus
from speleodb.common.enums import PermissionLevel
from speleodb.common.enums import UnitSystem
from speleodb.gis.models import Cylinder
from speleodb.gis.models import CylinderFleet
from speleodb.gis.models import CylinderInstall
from speleodb.users.tests.factories import UserFactory

if TYPE_CHECKING:
    from speleodb.surveys.models import Project
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
def cylinder(cylinder_fleet_with_write: CylinderFleet, user: User) -> Cylinder:
    """Create a cylinder in a fleet with write access."""
    return CylinderFactory.create(
        fleet=cylinder_fleet_with_write, created_by=user.email
    )


@pytest.fixture
def project(user: User) -> Project:
    """Create a project with write access for user."""
    project = ProjectFactory.create()
    UserProjectPermissionFactory.create(
        target=user,
        project=project,
        level=PermissionLevel.READ_AND_WRITE,
    )
    return project


@pytest.fixture
def cylinder_install(
    cylinder: Cylinder, project: Project, user: User
) -> CylinderInstall:
    """Create a cylinder install."""
    return CylinderInstallFactory.create(
        cylinder=cylinder,
        project=project,
        install_user=user.email,
        created_by=user.email,
    )


# ================== HELPER FUNCTIONS ================== #


def get_auth_header(user: User) -> str:
    """Get authorization header for user."""
    token, _ = Token.objects.get_or_create(user=user)
    return f"Token {token.key}"


# ================== TEST CLASSES ================== #


@pytest.mark.django_db
class TestCylinderInstallListCreate:
    """Tests for listing and creating cylinder installs."""

    def test_list_cylinder_installs_authenticated(
        self,
        api_client: APIClient,
        cylinder_install: CylinderInstall,
        user: User,
    ) -> None:
        """Authenticated user can list cylinder installs they have access to."""
        response = api_client.get(
            reverse("api:v1:cylinder-installs"),
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["data"]) == 1
        assert response.data["data"][0]["id"] == str(cylinder_install.id)

    def test_list_cylinder_installs_filter_by_cylinder(
        self,
        api_client: APIClient,
        cylinder: Cylinder,
        user: User,
    ) -> None:
        """Can filter installs by cylinder_id."""
        install1 = CylinderInstallFactory.create(cylinder=cylinder)
        # Create another install with a different cylinder
        other_cylinder = CylinderFactory.create(fleet=cylinder.fleet)
        CylinderInstallFactory.create(cylinder=other_cylinder)

        response = api_client.get(
            reverse("api:v1:cylinder-installs") + f"?cylinder_id={cylinder.id}",
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["data"]) == 1
        assert response.data["data"][0]["id"] == str(install1.id)

    def test_list_cylinder_installs_filter_by_status(
        self,
        api_client: APIClient,
        cylinder_fleet_with_write: CylinderFleet,
        user: User,
    ) -> None:
        """Can filter installs by status."""
        cylinder1 = CylinderFactory.create(fleet=cylinder_fleet_with_write)
        cylinder2 = CylinderFactory.create(fleet=cylinder_fleet_with_write)

        CylinderInstallFactory.create(
            cylinder=cylinder1, status=InstallStatus.INSTALLED
        )
        CylinderInstallFactory.create_uninstalled(
            cylinder=cylinder2, install_status=InstallStatus.RETRIEVED
        )

        response = api_client.get(
            reverse("api:v1:cylinder-installs") + "?status=installed",
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["data"]) == 1
        assert response.data["data"][0]["status"] == InstallStatus.INSTALLED

    def test_list_cylinder_installs_empty(
        self,
        api_client: APIClient,
        user: User,
    ) -> None:
        """User with no accessible installs gets empty list."""
        # Create an install for a fleet user doesn't have access to
        CylinderInstallFactory.create()

        response = api_client.get(
            reverse("api:v1:cylinder-installs"),
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"] == []

    def test_create_cylinder_install_valid(
        self,
        api_client: APIClient,
        cylinder: Cylinder,
        project: Project,
        user: User,
    ) -> None:
        """User with write access can create cylinder install."""
        data = {
            "cylinder": str(cylinder.id),
            "project": str(project.id),
            "latitude": "30.0000000",
            "longitude": "-84.0000000",
            "location_name": "Test Cave",
            "install_date": timezone.localdate().isoformat(),
            "unit_system": UnitSystem.METRIC,
        }

        response = api_client.post(
            reverse("api:v1:cylinder-installs"),
            data=data,
            format="json",
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["data"]["cylinder_id"] == str(cylinder.id)
        assert response.data["data"]["project_id"] == str(project.id)
        assert response.data["data"]["location_name"] == "Test Cave"
        assert response.data["data"]["install_user"] == user.email
        assert response.data["data"]["status"] == InstallStatus.INSTALLED

    def test_create_cylinder_install_with_distance(
        self,
        api_client: APIClient,
        cylinder: Cylinder,
        project: Project,
        user: User,
    ) -> None:
        """User can create install with distance from entry."""
        data = {
            "cylinder": str(cylinder.id),
            "project": str(project.id),
            "latitude": "30.0000000",
            "longitude": "-84.0000000",
            "location_name": "Deep Cave",
            "install_date": timezone.localdate().isoformat(),
            "distance_from_entry": 1500,
            "unit_system": UnitSystem.METRIC,
        }

        response = api_client.post(
            reverse("api:v1:cylinder-installs"),
            data=data,
            format="json",
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["data"]["distance_from_entry"] == 1500  # noqa: PLR2004

    def test_create_cylinder_install_without_write_permission(
        self,
        api_client: APIClient,
        cylinder_fleet_with_read: CylinderFleet,
        project: Project,
        user: User,
    ) -> None:
        """Read-only user cannot create install."""
        cylinder = CylinderFactory.create(fleet=cylinder_fleet_with_read)
        data = {
            "cylinder": str(cylinder.id),
            "project": str(project.id),
            "latitude": "30.0000000",
            "longitude": "-84.0000000",
            "location_name": "Test Cave",
            "install_date": timezone.localdate().isoformat(),
            "unit_system": UnitSystem.METRIC,
        }

        response = api_client.post(
            reverse("api:v1:cylinder-installs"),
            data=data,
            format="json",
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_create_cylinder_install_already_installed(
        self,
        api_client: APIClient,
        cylinder_install: CylinderInstall,
        project: Project,
        user: User,
    ) -> None:
        """Cannot install cylinder that's already installed."""
        data = {
            "cylinder": str(cylinder_install.cylinder.id),
            "project": str(project.id),
            "latitude": "31.0000000",
            "longitude": "-85.0000000",
            "location_name": "Other Cave",
            "install_date": timezone.localdate().isoformat(),
            "unit_system": UnitSystem.METRIC,
        }

        response = api_client.post(
            reverse("api:v1:cylinder-installs"),
            data=data,
            format="json",
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "already installed" in str(response.data).lower()

    def test_create_cylinder_install_missing_required_fields(
        self,
        api_client: APIClient,
        cylinder: Cylinder,
        user: User,
    ) -> None:
        """Creating install without required fields returns validation error."""
        data = {"cylinder": str(cylinder.id)}

        response = api_client.post(
            reverse("api:v1:cylinder-installs"),
            data=data,
            format="json",
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_cylinder_install_unauthenticated(
        self,
        api_client: APIClient,
        cylinder: Cylinder,
    ) -> None:
        """Unauthenticated request returns 403."""
        data = {
            "cylinder": str(cylinder.id),
            "latitude": "30.0000000",
            "longitude": "-84.0000000",
            "install_date": timezone.localdate().isoformat(),
            "unit_system": UnitSystem.METRIC,
        }

        response = api_client.post(
            reverse("api:v1:cylinder-installs"),
            data=data,
            format="json",
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestCylinderInstallRetrieveUpdateDelete:
    """Tests for retrieving, updating, and deleting cylinder installs."""

    def test_retrieve_cylinder_install(
        self,
        api_client: APIClient,
        cylinder_install: CylinderInstall,
        user: User,
    ) -> None:
        """User can retrieve cylinder install details."""
        response = api_client.get(
            reverse(
                "api:v1:cylinder-install-detail",
                kwargs={"install_id": cylinder_install.id},
            ),
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"]["id"] == str(cylinder_install.id)
        assert response.data["data"]["cylinder_id"] == str(cylinder_install.cylinder.id)

    def test_retrieve_cylinder_install_no_permission(
        self,
        api_client: APIClient,
        user: User,
    ) -> None:
        """User without fleet access cannot retrieve install."""
        install = CylinderInstallFactory.create()

        response = api_client.get(
            reverse(
                "api:v1:cylinder-install-detail",
                kwargs={"install_id": install.id},
            ),
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_update_status_to_retrieved(
        self,
        api_client: APIClient,
        cylinder_install: CylinderInstall,
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
                "api:v1:cylinder-install-detail",
                kwargs={"install_id": cylinder_install.id},
            ),
            data=data,
            format="json",
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"]["status"] == InstallStatus.RETRIEVED
        assert response.data["data"]["uninstall_date"] == uninstall_date.isoformat()
        assert response.data["data"]["uninstall_user"] == user.email

    def test_update_status_to_retrieved_auto_fills_dates(
        self,
        api_client: APIClient,
        cylinder_install: CylinderInstall,
        user: User,
    ) -> None:
        """Updating to RETRIEVED auto-fills uninstall fields if not provided."""
        data = {"status": InstallStatus.RETRIEVED}

        response = api_client.patch(
            reverse(
                "api:v1:cylinder-install-detail",
                kwargs={"install_id": cylinder_install.id},
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
        cylinder_install: CylinderInstall,
        user: User,
    ) -> None:
        """User can update install status to LOST."""
        data = {"status": InstallStatus.LOST}

        response = api_client.patch(
            reverse(
                "api:v1:cylinder-install-detail",
                kwargs={"install_id": cylinder_install.id},
            ),
            data=data,
            format="json",
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"]["status"] == InstallStatus.LOST

    def test_update_status_to_abandoned(
        self,
        api_client: APIClient,
        cylinder_install: CylinderInstall,
        user: User,
    ) -> None:
        """User can update install status to ABANDONED."""
        data = {"status": InstallStatus.ABANDONED}

        response = api_client.patch(
            reverse(
                "api:v1:cylinder-install-detail",
                kwargs={"install_id": cylinder_install.id},
            ),
            data=data,
            format="json",
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"]["status"] == InstallStatus.ABANDONED

    def test_update_status_invalid_transition(
        self,
        api_client: APIClient,
        cylinder_fleet_with_write: CylinderFleet,
        user: User,
    ) -> None:
        """Cannot change status from RETRIEVED/LOST/ABANDONED."""
        cylinder = CylinderFactory.create(fleet=cylinder_fleet_with_write)
        retrieved_install = CylinderInstallFactory.create_uninstalled(
            cylinder=cylinder,
            install_status=InstallStatus.RETRIEVED,
            uninstall_user=user.email,
        )

        data = {"status": InstallStatus.INSTALLED}

        response = api_client.patch(
            reverse(
                "api:v1:cylinder-install-detail",
                kwargs={"install_id": retrieved_install.id},
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
        cylinder_fleet_with_read: CylinderFleet,
        user: User,
    ) -> None:
        """Read-only user cannot update install status."""
        cylinder = CylinderFactory.create(fleet=cylinder_fleet_with_read)
        install = CylinderInstallFactory.create(cylinder=cylinder)

        data = {"status": InstallStatus.LOST}

        response = api_client.patch(
            reverse(
                "api:v1:cylinder-install-detail",
                kwargs={"install_id": install.id},
            ),
            data=data,
            format="json",
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_update_location_name(
        self,
        api_client: APIClient,
        cylinder_install: CylinderInstall,
        user: User,
    ) -> None:
        """User can update location name."""
        data = {"location_name": "Updated Location"}

        response = api_client.patch(
            reverse(
                "api:v1:cylinder-install-detail",
                kwargs={"install_id": cylinder_install.id},
            ),
            data=data,
            format="json",
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["data"]["location_name"] == "Updated Location"

    def test_delete_cylinder_install(
        self,
        api_client: APIClient,
        cylinder_install: CylinderInstall,
        user: User,
    ) -> None:
        """User can delete cylinder install."""
        install_id = cylinder_install.id

        response = api_client.delete(
            reverse(
                "api:v1:cylinder-install-detail",
                kwargs={"install_id": install_id},
            ),
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK
        assert not CylinderInstall.objects.filter(id=install_id).exists()

    def test_delete_cylinder_install_without_write_permission(
        self,
        api_client: APIClient,
        cylinder_fleet_with_read: CylinderFleet,
        user: User,
    ) -> None:
        """Read-only user cannot delete install."""
        cylinder = CylinderFactory.create(fleet=cylinder_fleet_with_read)
        install = CylinderInstallFactory.create(cylinder=cylinder)

        response = api_client.delete(
            reverse(
                "api:v1:cylinder-install-detail",
                kwargs={"install_id": install.id},
            ),
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestCylinderInstallGeoJSON:
    """Tests for GeoJSON endpoint."""

    def test_geojson_returns_feature_collection(
        self,
        api_client: APIClient,
        cylinder_install: CylinderInstall,
        user: User,
    ) -> None:
        """GeoJSON endpoint returns FeatureCollection."""
        response = api_client.get(
            reverse("api:v1:cylinder-installs-geojson"),
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["type"] == "FeatureCollection"
        assert len(response.data["features"]) == 1

    def test_geojson_feature_structure(
        self,
        api_client: APIClient,
        cylinder_install: CylinderInstall,
        user: User,
    ) -> None:
        """GeoJSON features have correct structure."""
        response = api_client.get(
            reverse("api:v1:cylinder-installs-geojson"),
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        feature = response.data["features"][0]
        assert feature["type"] == "Feature"
        assert "geometry" in feature
        assert "properties" in feature
        assert feature["geometry"]["type"] == "Point"
        assert len(feature["geometry"]["coordinates"]) == 2  # noqa: PLR2004

        props = feature["properties"]
        assert props["id"] == str(cylinder_install.id)
        assert props["cylinder_id"] == str(cylinder_install.cylinder.id)
        assert "location_name" in props
        assert "o2_percentage" in props
        assert "he_percentage" in props

    def test_geojson_only_installed_cylinders(
        self,
        api_client: APIClient,
        cylinder_fleet_with_write: CylinderFleet,
        user: User,
    ) -> None:
        """GeoJSON only returns INSTALLED cylinders."""
        cylinder1 = CylinderFactory.create(fleet=cylinder_fleet_with_write)
        cylinder2 = CylinderFactory.create(fleet=cylinder_fleet_with_write)

        CylinderInstallFactory.create(
            cylinder=cylinder1, status=InstallStatus.INSTALLED
        )
        CylinderInstallFactory.create_uninstalled(
            cylinder=cylinder2, install_status=InstallStatus.RETRIEVED
        )

        response = api_client.get(
            reverse("api:v1:cylinder-installs-geojson"),
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["features"]) == 1
        assert (
            response.data["features"][0]["properties"]["status"]
            == InstallStatus.INSTALLED
        )

    def test_geojson_only_accessible_fleets(
        self,
        api_client: APIClient,
        cylinder_install: CylinderInstall,
        user: User,
    ) -> None:
        """GeoJSON only returns cylinders from fleets user has access to."""
        # Create install for fleet user doesn't have access to
        CylinderInstallFactory.create()

        response = api_client.get(
            reverse("api:v1:cylinder-installs-geojson"),
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK
        # Should only see the one install from accessible fleet
        assert len(response.data["features"]) == 1
        assert response.data["features"][0]["properties"]["id"] == str(
            cylinder_install.id
        )

    def test_geojson_unauthenticated(
        self,
        api_client: APIClient,
    ) -> None:
        """Unauthenticated request returns 403."""
        response = api_client.get(
            reverse("api:v1:cylinder-installs-geojson"),
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestCylinderInstallEdgeCases:
    """Edge cases and validation tests."""

    def test_can_install_retrieved_cylinder(
        self,
        api_client: APIClient,
        cylinder_fleet_with_write: CylinderFleet,
        project: Project,
        user: User,
    ) -> None:
        """Can install a cylinder that was previously retrieved."""
        cylinder = CylinderFactory.create(fleet=cylinder_fleet_with_write)
        # Create a retrieved install
        CylinderInstallFactory.create_uninstalled(
            cylinder=cylinder, project=project, install_status=InstallStatus.RETRIEVED
        )

        # Now install the same cylinder again
        data = {
            "cylinder": str(cylinder.id),
            "project": str(project.id),
            "latitude": "30.0000000",
            "longitude": "-84.0000000",
            "location_name": "New Location",
            "install_date": timezone.localdate().isoformat(),
            "unit_system": UnitSystem.METRIC,
        }

        response = api_client.post(
            reverse("api:v1:cylinder-installs"),
            data=data,
            format="json",
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_201_CREATED

    def test_uninstall_date_before_install_date_invalid(
        self,
        api_client: APIClient,
        cylinder_install: CylinderInstall,
        user: User,
    ) -> None:
        """Uninstall date must be on or after install date."""
        install_date = cylinder_install.install_date
        uninstall_date = install_date - timedelta(days=1)

        data = {
            "status": InstallStatus.RETRIEVED,
            "uninstall_date": uninstall_date.isoformat(),
        }

        response = api_client.patch(
            reverse(
                "api:v1:cylinder-install-detail",
                kwargs={"install_id": cylinder_install.id},
            ),
            data=data,
            format="json",
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Uninstall date must be" in str(response.data["errors"])

    def test_latitude_longitude_validation(
        self,
        api_client: APIClient,
        cylinder: Cylinder,
        project: Project,
        user: User,
    ) -> None:
        """Latitude and longitude are validated."""
        data = {
            "cylinder": str(cylinder.id),
            "project": str(project.id),
            "latitude": "100.0000000",  # Invalid: > 90
            "longitude": "-84.0000000",
            "location_name": "Test Cave",
            "install_date": timezone.localdate().isoformat(),
            "unit_system": UnitSystem.METRIC,
        }

        response = api_client.post(
            reverse("api:v1:cylinder-installs"),
            data=data,
            format="json",
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_list_includes_nested_info(
        self,
        api_client: APIClient,
        cylinder_install: CylinderInstall,
        user: User,
    ) -> None:
        """List response includes nested cylinder and fleet information."""
        response = api_client.get(
            reverse("api:v1:cylinder-installs"),
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK
        install_data = response.data["data"][0]
        assert "cylinder_id" in install_data
        assert "cylinder_name" in install_data
        assert "cylinder_fleet_id" in install_data
        assert "cylinder_fleet_name" in install_data

    def test_pressure_check_count_in_response(
        self,
        api_client: APIClient,
        cylinder_install: CylinderInstall,
        user: User,
    ) -> None:
        """Install response includes pressure check count."""
        response = api_client.get(
            reverse(
                "api:v1:cylinder-install-detail",
                kwargs={"install_id": cylinder_install.id},
            ),
            HTTP_AUTHORIZATION=get_auth_header(user),
        )

        assert response.status_code == status.HTTP_200_OK
        assert "pressure_check_count" in response.data["data"]
        assert response.data["data"]["pressure_check_count"] == 0
