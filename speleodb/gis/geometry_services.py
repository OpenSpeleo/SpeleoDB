"""Atomic creation and optimistic updates shared by the API and Django admin."""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import Http404

from speleodb.api.v2.gis_geometry_access import user_has_gis_geometry_access
from speleodb.common.enums import PermissionLevel
from speleodb.gis.models import GISGeometry
from speleodb.gis.models import GISGeometryUserPermission
from speleodb.utils.sanitize import sanitize_text

if TYPE_CHECKING:
    from uuid import UUID

    from speleodb.users.models import User

GIS_GEOMETRY_EDITABLE_FIELDS = frozenset({"name", "color", "geojson"})
GIS_GEOMETRY_CONFLICT_MESSAGE = (
    "This geometry was updated elsewhere. Your changes have been kept. "
    "Load the saved version before trying again."
)


class GISGeometryConflictError(ValidationError):
    def __init__(self) -> None:
        super().__init__(GIS_GEOMETRY_CONFLICT_MESSAGE, code="GIS_GEOMETRY_CONFLICT")


def _clean_geometry(geometry: GISGeometry) -> None:
    geometry.name = sanitize_text(geometry.name).strip()
    geometry.color = geometry.color.strip().lower()
    geometry.full_clean()


@transaction.atomic
def create_gis_geometry(geometry: GISGeometry, creator: User) -> GISGeometry:
    geometry.created_by = creator.email
    geometry.revision = 1
    _clean_geometry(geometry)
    geometry.save(force_insert=True)
    GISGeometryUserPermission.objects.create(
        user=creator, gis_geometry=geometry, level=PermissionLevel.ADMIN
    )
    geometry.user_permission_level = PermissionLevel.ADMIN  # type: ignore[attr-defined]
    return geometry


@transaction.atomic
def update_gis_geometry(
    *,
    geometry_id: UUID,
    actor: User,
    expected_revision: int,
    updates: dict[str, Any],
    administrative: bool = False,
) -> GISGeometry:
    try:
        geometry = GISGeometry.objects.select_for_update().get(
            pk=geometry_id, is_active=True
        )
    except GISGeometry.DoesNotExist as exc:
        raise Http404 from exc
    if administrative:
        allowed: bool = actor.is_staff and actor.has_perm("gis.change_gisgeometry")
    else:
        allowed = user_has_gis_geometry_access(
            actor, geometry, PermissionLevel.READ_AND_WRITE
        )
    if not allowed:
        raise PermissionDenied
    if geometry.revision != expected_revision:
        raise GISGeometryConflictError
    if not set(updates) <= GIS_GEOMETRY_EDITABLE_FIELDS:
        raise ValidationError("Only name, color, and GeoJSON may be updated.")
    for field, value in updates.items():
        setattr(geometry, field, value)
    _clean_geometry(geometry)
    geometry.revision += 1
    geometry.save(update_fields=[*updates, "revision", "modified_date"])
    return geometry
