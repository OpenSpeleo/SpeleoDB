# -*- coding: utf-8 -*-

from __future__ import annotations

import contextlib
import math
from typing import TYPE_CHECKING
from typing import Any
from typing import BinaryIO

import orjson
from django.core.exceptions import ValidationError
from django.core.validators import MaxLengthValidator
from django.core.validators import MinLengthValidator
from openspeleo_lib.constants import OSPL_GEOJSON_DIGIT_PRECISION

from speleodb.gis.gis_layer_processing.errors import GISLayerProcessingError
from speleodb.gis.gis_layer_processing.errors import ProcessingErrorCode
from speleodb.utils.validators import LatitudeValidator
from speleodb.utils.validators import LongitudeValidator

if TYPE_CHECKING:
    from collections.abc import Iterable
    from collections.abc import Iterator
    from collections.abc import Mapping
    from collections.abc import Sequence


def read_source(file_obj: BinaryIO) -> bytes:
    chunks: list[bytes] = []
    with contextlib.suppress(OSError, ValueError):
        file_obj.seek(0)
    try:
        while chunk := file_obj.read(1024 * 1024):
            chunks.append(chunk)
    finally:
        with contextlib.suppress(OSError, ValueError):
            file_obj.seek(0)
    return b"".join(chunks)


def deterministic_json(value: Any) -> bytes:
    return orjson.dumps(value, option=orjson.OPT_SORT_KEYS)


def iter_coordinate_positions(geometry: Mapping[str, Any]) -> Iterator[list[float]]:
    geometry_type = geometry.get("type")
    if not isinstance(geometry_type, str):
        return
    if geometry_type == "GeometryCollection":
        for child in geometry.get("geometries", []):
            yield from iter_coordinate_positions(child)
        return

    coordinates = geometry.get("coordinates")
    nesting = {
        "Point": 0,
        "MultiPoint": 1,
        "LineString": 1,
        "MultiLineString": 2,
        "Polygon": 2,
        "MultiPolygon": 3,
    }.get(geometry_type)
    if nesting is None:
        return
    yield from _descend_positions(coordinates, nesting)


def _descend_positions(value: Any, levels: int) -> Iterator[list[float]]:
    if levels == 0:
        if isinstance(value, list):
            yield value
        return
    if isinstance(value, list):
        for child in value:
            yield from _descend_positions(child, levels - 1)


def explode_geometry_collections(
    features: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Explode collection children into stable Mapbox-renderable Features."""
    exploded: list[dict[str, Any]] = []
    for feature in features:
        geometry = feature["geometry"]
        if geometry["type"] != "GeometryCollection":
            exploded.append(feature)
            continue
        children = _flatten_geometry_collection(geometry)
        for index, child in enumerate(children, start=1):
            exploded.append(
                feature
                | {
                    "id": f"{feature['id']}:geometry:{index:04d}",
                    "geometry": child,
                }
            )
    return exploded


def _flatten_geometry_collection(
    geometry: Mapping[str, Any],
) -> list[dict[str, Any]]:
    flattened: list[dict[str, Any]] = []
    for child in geometry["geometries"]:
        if child["type"] == "GeometryCollection":
            flattened.extend(_flatten_geometry_collection(child))
        else:
            flattened.append(child)
    return flattened


def calculate_bbox(
    positions: Iterable[Sequence[float]],
) -> list[float] | None:
    """Calculate an RFC 7946 bbox using the shortest longitude interval."""
    longitudes: list[float] = []
    min_latitude = math.inf
    max_latitude = -math.inf
    for position in positions:
        longitude = float(position[0])
        latitude = float(position[1])
        longitudes.append(longitude)
        min_latitude = min(min_latitude, latitude)
        max_latitude = max(max_latitude, latitude)
    if not longitudes:
        return None

    normalized = sorted(
        ((longitude + 180.0) % 360.0) - 180.0 for longitude in longitudes
    )
    if len(normalized) == 1:
        west = east = normalized[0]
    else:
        gaps = [
            normalized[index + 1] - normalized[index]
            for index in range(len(normalized) - 1)
        ]
        gaps.append(normalized[0] + 360.0 - normalized[-1])
        largest_gap_index = max(range(len(gaps)), key=gaps.__getitem__)
        west = normalized[(largest_gap_index + 1) % len(normalized)]
        east = normalized[largest_gap_index]
    return [west, min_latitude, east, max_latitude]


def validate_position(position: Any, *, context: str) -> list[float]:
    if not isinstance(position, list):
        raise GISLayerProcessingError(
            ProcessingErrorCode.GEOJSON_INVALID,
            "A coordinate position has an invalid dimensionality.",
            details={"context": context},
        )
    try:
        MinLengthValidator(2)(position)
        MaxLengthValidator(3)(position)
    except ValidationError as exc:
        raise GISLayerProcessingError(
            ProcessingErrorCode.GEOJSON_INVALID,
            "A coordinate position has an invalid dimensionality.",
            details={"context": context},
        ) from exc
    converted: list[float] = []
    for value in position:
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise GISLayerProcessingError(
                ProcessingErrorCode.GEOJSON_INVALID,
                "A coordinate contains a non-numeric value.",
                details={"context": context},
            )
        number = float(value)
        if not math.isfinite(number):
            raise GISLayerProcessingError(
                ProcessingErrorCode.GEOJSON_INVALID,
                "A coordinate contains a non-finite value.",
                details={"context": context},
            )
        converted.append(number)
    longitude, latitude = converted[:2]
    try:
        LongitudeValidator()(longitude)
        LatitudeValidator()(latitude)
    except ValidationError as exc:
        raise GISLayerProcessingError(
            ProcessingErrorCode.GEOJSON_INVALID,
            "A coordinate is outside the WGS84 longitude/latitude range.",
            details={"context": context},
        ) from exc
    normalized = [
        round(longitude, OSPL_GEOJSON_DIGIT_PRECISION),
        round(latitude, OSPL_GEOJSON_DIGIT_PRECISION),
    ]
    if altitude := converted[2:]:
        normalized.append(round(altitude[0], OSPL_GEOJSON_DIGIT_PRECISION))
    return normalized
