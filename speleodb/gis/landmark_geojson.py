"""Permission-independent Landmark GeoJSON shared by viewers and exports."""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

from geojson import Feature  # type: ignore[attr-defined]
from geojson import Point  # type: ignore[attr-defined]

if TYPE_CHECKING:
    from speleodb.gis.models import Landmark


def landmark_geojson_feature(
    instance: Landmark,
    *,
    coordinate_precision: int | None = None,
) -> dict[str, Any]:
    """Serialize public record fields; callers add their own access metadata."""
    return Feature(  # type: ignore[no-untyped-call]
        id=str(instance.id),
        geometry=Point(  # type: ignore[no-untyped-call]
            (float(instance.longitude), float(instance.latitude)),
            precision=coordinate_precision,
        ),
        properties={
            "name": instance.name,
            "description": instance.description,
            "collection": str(instance.collection_id),
            "collection_name": instance.collection.name,
            "collection_type": instance.collection.collection_type,
            "collection_color": instance.collection.color,
            "is_personal_collection": instance.collection.is_personal,
            "created_by": instance.created_by,
            "creation_date": instance.creation_date.isoformat()
            if instance.creation_date
            else None,
        },
    )
