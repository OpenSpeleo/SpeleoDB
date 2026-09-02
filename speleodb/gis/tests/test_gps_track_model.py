"""Tests for GPS Track sharing model invariants and admin integration."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING
from typing import Any
from typing import cast

import pytest
from django.contrib import admin
from django.db import IntegrityError
from django.db import transaction
from django.test import RequestFactory

from speleodb.api.v2.tests.factories import GPSTrackFactory
from speleodb.common.enums import PermissionLevel
from speleodb.gis.models import GPSTrack
from speleodb.gis.models import GPSTrackUserPermission
from speleodb.permissions.admin.gps_track import GPSTrackUserPermissionAdmin
from speleodb.permissions.admin.gps_track import GPSTrackUserPermissionProxy
from speleodb.users.tests.factories import UserFactory

if TYPE_CHECKING:
    from speleodb.users.models import User


def _user(prefix: str) -> User:
    return UserFactory.create(email=f"{prefix}-{uuid.uuid4()}@test.local")


@pytest.mark.django_db
class TestGPSTrackModel:
    def test_new_track_creates_single_active_creator_admin_permission(self) -> None:
        creator = _user("creator")
        gps_track = GPSTrackFactory.create(creator=creator)

        permission = GPSTrackUserPermission.objects.get(
            user=creator,
            gps_track=gps_track,
        )

        assert permission.level == PermissionLevel.ADMIN
        assert permission.is_active
        assert permission.deactivated_by is None
        assert gps_track.permissions.count() == 1

    def test_updating_track_does_not_duplicate_creator_permission(self) -> None:
        gps_track = GPSTrackFactory.create()

        gps_track.name = "Updated name"
        gps_track.save(update_fields=["name", "modified_date"])

        assert gps_track.permissions.count() == 1

    def test_track_stores_creator_email(self) -> None:
        creator = _user("creator-email")
        gps_track = GPSTrackFactory.create(creator=creator)

        assert gps_track.created_by == creator.email

    def test_deactivate_soft_deletes_track_and_only_active_permissions(self) -> None:
        gps_track = GPSTrackFactory.create()
        collaborator = _user("collaborator")
        active_permission = GPSTrackUserPermission.objects.create(
            user=collaborator,
            gps_track=gps_track,
            level=PermissionLevel.READ_ONLY,
        )
        previously_revoked = GPSTrackUserPermission.objects.create(
            user=_user("revoked-user"),
            gps_track=gps_track,
            level=PermissionLevel.READ_ONLY,
        )
        original_deactivator = _user("original-deactivator")
        previously_revoked.deactivate(deactivated_by=original_deactivator)

        administrator = gps_track.permissions.get(level=PermissionLevel.ADMIN).user
        gps_track.deactivate(deactivated_by=administrator)

        gps_track.refresh_from_db()
        active_permission.refresh_from_db()
        previously_revoked.refresh_from_db()
        assert not gps_track.is_active
        assert not active_permission.is_active
        assert active_permission.deactivated_by == administrator
        assert not previously_revoked.is_active
        assert previously_revoked.deactivated_by == original_deactivator


@pytest.mark.django_db
class TestGPSTrackUserPermissionModel:
    def test_permission_uniqueness(self) -> None:
        gps_track = GPSTrackFactory.create()
        collaborator = _user("unique-collaborator")
        GPSTrackUserPermission.objects.create(
            user=collaborator,
            gps_track=gps_track,
            level=PermissionLevel.READ_ONLY,
        )

        with pytest.raises(IntegrityError), transaction.atomic():
            GPSTrackUserPermission.objects.create(
                user=collaborator,
                gps_track=gps_track,
                level=PermissionLevel.READ_AND_WRITE,
            )

    def test_deactivate_and_reactivate_preserve_audit_history(self) -> None:
        gps_track = GPSTrackFactory.create()
        collaborator = _user("lifecycle-collaborator")
        permission = GPSTrackUserPermission.objects.create(
            user=collaborator,
            gps_track=gps_track,
            level=PermissionLevel.READ_ONLY,
        )

        administrator = gps_track.permissions.get(level=PermissionLevel.ADMIN).user
        permission.deactivate(deactivated_by=administrator)
        permission.refresh_from_db()
        assert not permission.is_active
        assert permission.deactivated_by == administrator

        permission.reactivate(level=PermissionLevel.READ_AND_WRITE)
        permission.refresh_from_db()
        assert permission.is_active
        assert permission.level == PermissionLevel.READ_AND_WRITE
        assert permission.deactivated_by is None

    def test_level_choices_exclude_web_viewer_and_level_label_is_readable(
        self,
    ) -> None:
        permission = GPSTrackUserPermission.objects.get(
            gps_track=GPSTrackFactory.create(),
        )
        choices = permission._meta.get_field("level").choices  # noqa: SLF001
        assert choices is not None
        level_values = {value for value, _label in choices}

        assert PermissionLevel.WEB_VIEWER not in level_values
        assert level_values == {
            PermissionLevel.READ_ONLY,
            PermissionLevel.READ_AND_WRITE,
            PermissionLevel.ADMIN,
        }
        assert str(permission.level_label) == "ADMIN"
        assert repr(permission) == f"<GPSTrackUserPermission: {permission}>"

    def test_permission_indexes_cover_active_access_queries(self) -> None:
        index_fields = {
            tuple(index.fields)
            for index in GPSTrackUserPermission._meta.indexes  # noqa: SLF001
        }

        assert ("user", "is_active") in index_fields
        assert ("gps_track", "is_active") in index_fields
        assert ("user", "gps_track", "is_active") in index_fields


@pytest.mark.django_db
class TestGPSTrackAdmin:
    def test_track_admin_exposes_active_state_and_disables_hard_delete(self) -> None:
        gps_track_admin = admin.site._registry[GPSTrack]  # noqa: SLF001
        request: Any = RequestFactory().get("/")

        assert "is_active" in gps_track_admin.list_display
        assert "is_active" in gps_track_admin.list_filter
        assert "is_active" in gps_track_admin.readonly_fields
        assert not gps_track_admin.has_delete_permission(request)

    def test_permission_proxy_is_registered(self) -> None:
        assert GPSTrackUserPermissionProxy._meta.proxy  # noqa: SLF001
        assert GPSTrackUserPermissionProxy in admin.site._registry  # noqa: SLF001

    def test_permission_admin_preserves_identity_and_lifecycle_fields(self) -> None:
        permission_admin = GPSTrackUserPermissionAdmin(
            GPSTrackUserPermissionProxy,
            admin.site,
        )
        request: Any = RequestFactory().get("/")

        assert not permission_admin.has_delete_permission(request)
        assert {"is_active", "deactivated_by"} <= set(
            permission_admin.get_readonly_fields(request)
        )
        assert {"user", "gps_track"} <= set(
            permission_admin.get_readonly_fields(
                request,
                cast("GPSTrackUserPermissionProxy", object()),
            )
        )
