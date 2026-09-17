"""Direct permission lookup for private GIS Geometry records."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db.models import Exists
from django.db.models import IntegerField
from django.db.models import OuterRef
from django.db.models import QuerySet
from django.db.models import Subquery
from django.db.models.fields.json import KeyTextTransform

from speleodb.common.enums import PermissionLevel
from speleodb.gis.models import GISGeometry
from speleodb.gis.models import GISGeometryUserPermission

if TYPE_CHECKING:
    from speleodb.users.models import User


def get_gis_geometry_permission_level(user: User, geometry: GISGeometry) -> int | None:
    if not geometry.is_active:
        return None
    return (
        GISGeometryUserPermission.objects.filter(
            user=user, gis_geometry=geometry, is_active=True
        )
        .values_list("level", flat=True)
        .first()
    )


def user_has_gis_geometry_access(
    user: User,
    geometry: GISGeometry,
    min_level: int = PermissionLevel.READ_ONLY,
) -> bool:
    level: int | None = get_gis_geometry_permission_level(user, geometry)
    return level is not None and level >= min_level


def accessible_gis_geometries_queryset(user: User) -> QuerySet[GISGeometry]:
    permission_qs = GISGeometryUserPermission.objects.filter(
        gis_geometry=OuterRef("pk"),
        user=user,
        is_active=True,
        level__gte=PermissionLevel.READ_ONLY,
    )
    return (
        GISGeometry.objects.filter(is_active=True)
        .filter(Exists(permission_qs))
        .annotate(
            user_permission_level=Subquery(
                permission_qs.values("level")[:1], output_field=IntegerField()
            ),
            listed_geometry_type=KeyTextTransform("type", "geojson"),
        )
    )
