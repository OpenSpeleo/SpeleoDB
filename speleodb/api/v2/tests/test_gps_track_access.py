"""Tests for centralized GPS Track queryset and DRF access-level behavior."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING
from typing import Any

import pytest
from rest_framework.test import APIRequestFactory
from rest_framework.views import APIView

from speleodb.api.v2.gps_track_access import accessible_gps_tracks_queryset
from speleodb.api.v2.gps_track_access import get_gps_track_permission_level
from speleodb.api.v2.gps_track_access import user_has_gps_track_access
from speleodb.api.v2.permissions import SDB_AdminAccess
from speleodb.api.v2.permissions import SDB_ReadAccess
from speleodb.api.v2.permissions import SDB_WriteAccess
from speleodb.api.v2.tests.factories import GPSTrackFactory
from speleodb.api.v2.tests.factories import GPSTrackUserPermissionFactory
from speleodb.common.enums import PermissionLevel
from speleodb.users.tests.factories import UserFactory

if TYPE_CHECKING:
    from speleodb.gis.models import GPSTrackUserPermission
    from speleodb.users.models import User


def _request_for(user: User) -> Any:
    request: Any = APIRequestFactory().get("/")
    request.user = user
    return request


def _user(prefix: str) -> User:
    return UserFactory.create(email=f"{prefix}-{uuid.uuid4()}@test.local")


@pytest.mark.django_db
class TestAccessibleGPSTracksQueryset:
    def test_returns_exact_active_readable_tracks_with_permission_level(self) -> None:
        user = _user("query-user")
        created = GPSTrackFactory.create(creator=user, name="Created")
        shared = GPSTrackFactory.create(name="Shared")
        GPSTrackUserPermissionFactory.create(
            user=user,
            gps_track=shared,
            level=PermissionLevel.READ_AND_WRITE,
        )
        _ = GPSTrackFactory.create(name="Inaccessible")
        inactive = GPSTrackFactory.create(name="Inactive")
        GPSTrackUserPermissionFactory.create(
            user=user,
            gps_track=inactive,
            level=PermissionLevel.READ_ONLY,
        )
        inactive.is_active = False
        inactive.save(update_fields=["is_active", "modified_date"])
        revoked = GPSTrackFactory.create(name="Revoked")
        revoked_permission = GPSTrackUserPermissionFactory.create(
            user=user,
            gps_track=revoked,
            level=PermissionLevel.READ_ONLY,
        )
        revoked_permission.deactivate(deactivated_by=user)

        tracks = list(accessible_gps_tracks_queryset(user=user))

        assert [track.id for track in tracks] == [shared.id, created.id]
        levels = {
            track.name: track.user_permission_level  # type: ignore[attr-defined]
            for track in tracks
        }
        assert levels == {
            "Created": PermissionLevel.ADMIN,
            "Shared": PermissionLevel.READ_AND_WRITE,
        }
        assert all(track.created_by for track in tracks)

    def test_permission_level_helpers_reject_inactive_track_and_permission(
        self,
    ) -> None:
        user = _user("helper-user")
        gps_track = GPSTrackFactory.create()
        permission = GPSTrackUserPermissionFactory.create(
            user=user,
            gps_track=gps_track,
            level=PermissionLevel.READ_AND_WRITE,
        )

        assert (
            get_gps_track_permission_level(user=user, gps_track=gps_track)
            == PermissionLevel.READ_AND_WRITE
        )
        assert user_has_gps_track_access(
            user=user,
            gps_track=gps_track,
            min_level=PermissionLevel.READ_AND_WRITE,
        )
        assert not user_has_gps_track_access(
            user=user,
            gps_track=gps_track,
            min_level=PermissionLevel.ADMIN,
        )

        permission.deactivate(deactivated_by=user)
        assert get_gps_track_permission_level(user=user, gps_track=gps_track) is None

        permission.reactivate(level=PermissionLevel.ADMIN)
        gps_track.is_active = False
        gps_track.save(update_fields=["is_active", "modified_date"])
        assert get_gps_track_permission_level(user=user, gps_track=gps_track) is None


@pytest.mark.django_db
class TestGPSTrackBaseAccessLevel:
    @pytest.mark.parametrize(
        ("level", "can_read", "can_write", "can_admin"),
        [
            (PermissionLevel.READ_ONLY, True, False, False),
            (PermissionLevel.READ_AND_WRITE, True, True, False),
            (PermissionLevel.ADMIN, True, True, True),
        ],
    )
    def test_permission_matrix(
        self,
        level: PermissionLevel,
        can_read: bool,
        can_write: bool,
        can_admin: bool,
    ) -> None:
        user = _user(f"matrix-{level}")
        gps_track = GPSTrackFactory.create()
        permission = GPSTrackUserPermissionFactory.create(
            user=user,
            gps_track=gps_track,
            level=level,
        )
        request = _request_for(user)
        view = APIView()

        assert (
            SDB_ReadAccess().has_object_permission(request, view, gps_track) is can_read
        )
        assert (
            SDB_WriteAccess().has_object_permission(request, view, gps_track)
            is can_write
        )
        assert (
            SDB_AdminAccess().has_object_permission(request, view, gps_track)
            is can_admin
        )
        assert (
            SDB_ReadAccess().has_object_permission(request, view, permission)
            is can_read
        )

    def test_inactive_track_or_permission_denies_access(self) -> None:
        user = _user("inactive-user")
        gps_track = GPSTrackFactory.create()
        permission = GPSTrackUserPermissionFactory.create(
            user=user,
            gps_track=gps_track,
            level=PermissionLevel.ADMIN,
        )
        request = _request_for(user)
        view = APIView()

        permission.deactivate(deactivated_by=user)
        assert not SDB_ReadAccess().has_object_permission(request, view, gps_track)

        permission.reactivate(level=PermissionLevel.ADMIN)
        gps_track.is_active = False
        gps_track.save(update_fields=["is_active", "modified_date"])
        assert not SDB_ReadAccess().has_object_permission(request, view, gps_track)

    def test_stranger_has_no_access(self) -> None:
        gps_track = GPSTrackFactory.create()
        request = _request_for(_user("stranger"))

        assert not SDB_ReadAccess().has_object_permission(request, APIView(), gps_track)

    def test_permission_row_delegates_to_parent_track(self) -> None:
        user = _user("permission-parent-user")
        permission: GPSTrackUserPermission = GPSTrackUserPermissionFactory.create(
            user=user,
            level=PermissionLevel.ADMIN,
        )

        assert SDB_AdminAccess().has_object_permission(
            _request_for(user),
            APIView(),
            permission,
        )
