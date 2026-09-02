# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db.models import Exists
from django.db.models import IntegerField
from django.db.models import OuterRef
from django.db.models import QuerySet
from django.db.models import Subquery

from speleodb.common.enums import PermissionLevel
from speleodb.gis.models import GISLayer
from speleodb.gis.models import GISLayerUserPermission

if TYPE_CHECKING:
    from speleodb.users.models import User


def get_gis_layer_permission_level(user: User, gis_layer: GISLayer) -> int | None:
    if not gis_layer.is_active:
        return None
    return (
        GISLayerUserPermission.objects.filter(
            user=user,
            gis_layer=gis_layer,
            is_active=True,
        )
        .values_list("level", flat=True)
        .first()
    )


def user_has_gis_layer_access(
    user: User,
    gis_layer: GISLayer,
    min_level: int = PermissionLevel.READ_ONLY,
) -> bool:
    permission_level = get_gis_layer_permission_level(user, gis_layer)
    return permission_level is not None and permission_level >= min_level


def accessible_gis_layers_queryset(user: User) -> QuerySet[GISLayer]:
    """Return published readable layers with constant-query caller metadata."""
    permission_qs = GISLayerUserPermission.objects.filter(
        gis_layer=OuterRef("pk"),
        user=user,
        is_active=True,
        level__gte=PermissionLevel.READ_ONLY,
    )
    return (
        GISLayer.objects.filter(is_active=True)
        .filter(Exists(permission_qs))
        .annotate(
            user_permission_level=Subquery(
                permission_qs.values("level")[:1],
                output_field=IntegerField(),
            )
        )
    )
