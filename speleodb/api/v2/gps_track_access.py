# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db.models import Exists
from django.db.models import IntegerField
from django.db.models import OuterRef
from django.db.models import QuerySet
from django.db.models import Subquery

from speleodb.common.enums import PermissionLevel
from speleodb.gis.models import GPSTrack
from speleodb.gis.models import GPSTrackUserPermission

if TYPE_CHECKING:
    from speleodb.users.models import User


def get_gps_track_permission_level(
    user: User,
    gps_track: GPSTrack,
) -> int | None:
    """Return the user's active permission level on an active GPS Track."""
    if not gps_track.is_active:
        return None

    return (
        GPSTrackUserPermission.objects.filter(
            user=user,
            gps_track=gps_track,
            is_active=True,
        )
        .values_list("level", flat=True)
        .first()
    )


def user_has_gps_track_access(
    user: User,
    gps_track: GPSTrack,
    min_level: int = PermissionLevel.READ_ONLY,
) -> bool:
    """Check whether a user has ``min_level`` access to an active GPS Track."""
    permission_level = get_gps_track_permission_level(
        user=user,
        gps_track=gps_track,
    )
    return permission_level is not None and permission_level >= min_level


def accessible_gps_tracks_queryset(user: User) -> QuerySet[GPSTrack]:
    """Return active GPS Tracks readable by the user with access annotations."""
    permission_qs = GPSTrackUserPermission.objects.filter(
        gps_track=OuterRef("pk"),
        user=user,
        is_active=True,
        level__gte=PermissionLevel.READ_ONLY,
    )

    return (
        GPSTrack.objects.filter(is_active=True)
        .filter(Exists(permission_qs))
        .annotate(
            user_permission_level=Subquery(
                permission_qs.values("level")[:1],
                output_field=IntegerField(),
            ),
        )
    )
