"""Tests for Cylinder Fleet serializers."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from speleodb.api.v1.serializers.cylinder_fleet import CylinderFleetSerializer
from speleodb.api.v1.serializers.cylinder_fleet import (
    CylinderFleetUserPermissionSerializer,
)
from speleodb.api.v1.serializers.cylinder_fleet import CylinderFleetWithPermSerializer
from speleodb.api.v1.serializers.cylinder_fleet import CylinderSerializer
from speleodb.api.v1.tests.factories import CylinderFactory
from speleodb.api.v1.tests.factories import CylinderFleetFactory
from speleodb.api.v1.tests.factories import CylinderFleetUserPermissionFactory
from speleodb.api.v1.tests.factories import CylinderInstallFactory
from speleodb.common.enums import PermissionLevel
from speleodb.common.enums import UnitSystem
from speleodb.gis.models import CylinderFleetUserPermission
from speleodb.users.tests.factories import UserFactory

if TYPE_CHECKING:
    from speleodb.gis.models import CylinderFleet
    from speleodb.users.models import User


@pytest.fixture
def user() -> User:
    return UserFactory.create()


@pytest.fixture
def fleet(user: User) -> CylinderFleet:
    return CylinderFleetFactory.create(created_by=user.email)


@pytest.mark.django_db
class TestCylinderSerializer:
    def test_serialize_cylinder_with_install(self, fleet: CylinderFleet) -> None:
        cylinder = CylinderFactory.create(
            fleet=fleet,
            name="Cylinder A",
            o2_percentage=21,
            he_percentage=0,
            pressure=3000,
            unit_system=UnitSystem.IMPERIAL,
        )
        install = CylinderInstallFactory.create(
            cylinder=cylinder,
            location_name="Cave Entrance",
            latitude=10.123456,
            longitude=-85.654321,
        )

        serializer = CylinderSerializer(cylinder)
        data = serializer.data

        assert data["id"] == str(cylinder.id)
        assert data["fleet_id"] == str(fleet.id)
        assert data["fleet_name"] == fleet.name
        assert data["latest_install_location"] == install.location_name
        assert data["latest_install_lat"] == float(install.latitude)
        assert data["latest_install_long"] == float(install.longitude)
        assert data["latest_install_date"] == install.install_date.isoformat()
        assert len(data["active_installs"]) == 1

    def test_serialize_cylinder_without_install(self, fleet: CylinderFleet) -> None:
        cylinder = CylinderFactory.create(fleet=fleet)
        serializer = CylinderSerializer(cylinder)
        data = serializer.data

        assert data["latest_install_location"] is None
        assert data["latest_install_lat"] is None
        assert data["latest_install_long"] is None
        assert data["latest_install_date"] is None
        assert data["active_installs"] == []


@pytest.mark.django_db
class TestCylinderFleetSerializer:
    def test_name_validation(self) -> None:
        serializer = CylinderFleetSerializer(data={"name": "   "})
        assert not serializer.is_valid()
        assert "name" in serializer.errors

    def test_created_by_required(self) -> None:
        serializer = CylinderFleetSerializer(data={"name": "Fleet"})
        assert not serializer.is_valid()
        assert "non_field_errors" in serializer.errors

    def test_created_by_cannot_update(self, fleet: CylinderFleet) -> None:
        serializer = CylinderFleetSerializer(
            fleet,
            data={"created_by": "new@example.com"},
            partial=True,
        )
        assert not serializer.is_valid()
        assert "non_field_errors" in serializer.errors

    def test_create_assigns_admin_permission(self, user: User) -> None:
        serializer = CylinderFleetSerializer(
            data={"name": "New Fleet", "created_by": user.email}
        )
        assert serializer.is_valid(), serializer.errors
        fleet = serializer.save()

        perm = CylinderFleetUserPermission.objects.get(
            user=user, cylinder_fleet=fleet, is_active=True
        )
        assert perm.level == PermissionLevel.ADMIN

    def test_cylinder_count(self, fleet: CylinderFleet) -> None:
        CylinderFactory.create_batch(2, fleet=fleet)
        serializer = CylinderFleetSerializer(fleet)
        assert serializer.data["cylinder_count"] == 2  # noqa: PLR2004


@pytest.mark.django_db
class TestCylinderFleetWithPermSerializer:
    def test_permission_label(self, fleet: CylinderFleet) -> None:
        # These are annotated fields expected by the serializer, not model fields
        fleet.cylinder_count = 0  # type: ignore[attr-defined]
        fleet.user_permission_level = PermissionLevel.ADMIN  # type: ignore[attr-defined]
        serializer = CylinderFleetWithPermSerializer(fleet)
        data = serializer.data

        assert data["user_permission_level_label"] == PermissionLevel.ADMIN.label


@pytest.mark.django_db
class TestCylinderFleetUserPermissionSerializer:
    def test_user_full_name_fallback(self, user: User, fleet: CylinderFleet) -> None:
        permission = CylinderFleetUserPermissionFactory.create(
            user=user,
            cylinder_fleet=fleet,
            level=PermissionLevel.READ_ONLY,
        )
        serializer = CylinderFleetUserPermissionSerializer(permission)
        assert serializer.data["user_full_name"] == user.email

    def test_validate_level_invalid(self, user: User, fleet: CylinderFleet) -> None:
        serializer = CylinderFleetUserPermissionSerializer(
            data={"level": 999, "user_email": user.email}
        )
        assert not serializer.is_valid()
        assert "level" in serializer.errors

    def test_validate_user_email_missing(self, fleet: CylinderFleet) -> None:
        serializer = CylinderFleetUserPermissionSerializer(
            data={"user_email": "missing@example.com", "level": PermissionLevel.ADMIN}
        )
        assert not serializer.is_valid()
        assert "user_email" in serializer.errors
