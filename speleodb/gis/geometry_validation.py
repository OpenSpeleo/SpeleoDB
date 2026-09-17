"""The shared authoring contract for small, manually edited GIS geometries."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path
from typing import Any

from django.core.exceptions import ValidationError
from shapely.geometry import Polygon

GIS_GEOMETRY_CONTRACT: dict[str, Any] = json.loads(
    Path(__file__).with_name("geometry_contract.json").read_text()
)
GIS_GEOMETRY_MAX_VERTICES: int = GIS_GEOMETRY_CONTRACT["max_vertices"]
GIS_GEOMETRY_MAX_AREA_M2: int = GIS_GEOMETRY_CONTRACT["max_area_m2"]
GIS_GEOMETRY_WARNING_AREA_M2: int = GIS_GEOMETRY_CONTRACT["warning_area_m2"]
GIS_GEOMETRY_EARTH_RADIUS_M: float = GIS_GEOMETRY_CONTRACT["earth_radius_m"]
GIS_GEOMETRY_NAME_MAX_LENGTH: int = GIS_GEOMETRY_CONTRACT["name_max_length"]
GIS_GEOMETRY_TYPES: frozenset[str] = frozenset(GIS_GEOMETRY_CONTRACT["types"])
POSITION_DIMENSIONS: int = GIS_GEOMETRY_CONTRACT["position_dimensions"]
MIN_LINE_VERTICES: int = GIS_GEOMETRY_CONTRACT["min_line_vertices"]
MIN_POLYGON_VERTICES: int = GIS_GEOMETRY_CONTRACT["min_polygon_vertices"]
LONGITUDE_LIMIT: int = GIS_GEOMETRY_CONTRACT["longitude_limit"]
LATITUDE_LIMIT: int = GIS_GEOMETRY_CONTRACT["latitude_limit"]
SQUARE_METRES_PER_SQUARE_KILOMETRE: int = GIS_GEOMETRY_CONTRACT[
    "square_metres_per_square_kilometre"
]
GIS_GEOMETRY_MAX_AREA_KM2: float = (
    GIS_GEOMETRY_MAX_AREA_M2 / SQUARE_METRES_PER_SQUARE_KILOMETRE
)
GIS_GEOMETRY_LIMIT_HELP = (
    f"The bounding box must not exceed {GIS_GEOMETRY_MAX_AREA_KM2:g} km², "
    f"with a maximum of {GIS_GEOMETRY_MAX_VERTICES} vertices, "
    "to keep map editing and rendering responsive. Polygon closure does not "
    "count as a vertex."
)

type Position = tuple[float, float]


@dataclass(frozen=True)
class GeometryMetrics:
    bbox: tuple[float, float, float, float]
    bbox_area_m2: float
    vertex_count: int


def _position(value: Any) -> Position:
    if not isinstance(value, list) or len(value) != POSITION_DIMENSIONS:
        raise ValidationError("Each position must contain longitude and latitude only.")
    numbers: list[float] = []
    for component in value:
        if isinstance(component, bool) or not isinstance(component, int | float):
            raise ValidationError("Coordinates must be finite numbers.")
        try:
            number: float = float(component)
        except OverflowError as exc:
            raise ValidationError("Coordinates must be finite numbers.") from exc
        if not math.isfinite(number):
            raise ValidationError("Coordinates must be finite numbers.")
        numbers.append(number)
    longitude, latitude = numbers
    if not -LONGITUDE_LIMIT <= longitude <= LONGITUDE_LIMIT:
        raise ValidationError(
            f"Longitude must be between {-LONGITUDE_LIMIT} and "
            f"{LONGITUDE_LIMIT} degrees."
        )
    if not -LATITUDE_LIMIT <= latitude <= LATITUDE_LIMIT:
        raise ValidationError(
            f"Latitude must be between {-LATITUDE_LIMIT} and {LATITUDE_LIMIT} degrees."
        )
    return longitude, latitude


def bounding_box_metrics(
    positions: list[Position], vertex_count: int
) -> GeometryMetrics:
    """Measure the spherical coordinate rectangle, never a shortest wrapped arc.

    The sin difference is expressed as a product for precision near the poles.
    Keep this formula and its constants aligned with the browser's geometry rules.
    """
    west: float = min(position[0] for position in positions)
    east: float = max(position[0] for position in positions)
    south: float = min(position[1] for position in positions)
    north: float = max(position[1] for position in positions)
    area: float = (
        GIS_GEOMETRY_EARTH_RADIUS_M**2
        * math.radians(east - west)
        * 2
        * math.cos(math.radians((north + south) / 2))
        * math.sin(math.radians((north - south) / 2))
    )
    return GeometryMetrics((west, south, east, north), area, vertex_count)


def inspect_gis_geometry(value: Any) -> GeometryMetrics:
    """Validate one bare 2D Geometry and return its derived measurements."""
    if not isinstance(value, dict) or set(value) != {"type", "coordinates"}:
        raise ValidationError(
            "GeoJSON must be a Geometry object containing only type and coordinates."
        )
    geometry_type: Any = value["type"]
    if not isinstance(geometry_type, str) or geometry_type not in GIS_GEOMETRY_TYPES:
        raise ValidationError("Choose a LineString or simple Polygon.")
    coordinates: Any = value["coordinates"]
    if geometry_type == "Polygon":
        if not isinstance(coordinates, list) or len(coordinates) != 1:
            raise ValidationError("Polygons must have one outer ring and no holes.")
        coordinates = coordinates[0]
    if not isinstance(coordinates, list):
        raise ValidationError("Coordinates must be an array of positions.")
    vertex_count: int = len(coordinates) - (geometry_type == "Polygon")
    if vertex_count > GIS_GEOMETRY_MAX_VERTICES:
        raise ValidationError(
            f"A geometry may contain at most {GIS_GEOMETRY_MAX_VERTICES} vertices "
            "for map performance. Polygon closure does not count as a vertex."
        )
    positions: list[Position] = [_position(position) for position in coordinates]
    minimum: int = (
        MIN_POLYGON_VERTICES if geometry_type == "Polygon" else MIN_LINE_VERTICES
    )
    if len(set(positions)) < minimum:
        raise ValidationError(f"This shape needs at least {minimum} distinct vertices.")
    if geometry_type == "Polygon" and positions[0] != positions[-1]:
        raise ValidationError("A polygon ring must end at its first coordinate.")
    if any(start == end for start, end in pairwise(positions)):
        raise ValidationError("Consecutive vertices must have different coordinates.")
    if geometry_type == "Polygon" and len(set(positions[:-1])) != vertex_count:
        raise ValidationError("Polygon vertices must not repeat except at closure.")
    if any(
        abs(end[0] - start[0]) > LONGITUDE_LIMIT for start, end in pairwise(positions)
    ):
        raise ValidationError("Shapes crossing the antimeridian are not supported.")
    if geometry_type == "Polygon" and not Polygon(positions).is_valid:  # type: ignore[no-untyped-call]
        raise ValidationError(
            "Polygon edges must not cross or touch, and the polygon must "
            "enclose an area."
        )
    metrics: GeometryMetrics = bounding_box_metrics(positions, vertex_count)
    if metrics.bbox_area_m2 > GIS_GEOMETRY_MAX_AREA_M2:
        raise ValidationError(
            f"The bounding box exceeds {GIS_GEOMETRY_MAX_AREA_KM2:g} km². "
            "Reduce the shape's extent to keep "
            "map editing and rendering responsive."
        )
    return metrics


def validate_gis_geometry(value: Any) -> None:
    """Django field validator shared by API, admin, and model validation."""
    inspect_gis_geometry(value)
