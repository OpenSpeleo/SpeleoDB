# -*- coding: utf-8 -*-

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from collections.abc import Sequence
from typing import Any

import gpxpy.gpx
from django.http import StreamingHttpResponse
from django.utils import timezone

GPX_CONTENT_TYPE = "application/gpx+xml"
GPX_CREATOR = "SpeleoDB"
GPX_VERSION = "1.1"
_GEOJSON_LINE_MIN_POSITIONS = 2
_GEOJSON_POSITION_LENGTHS = frozenset({2, 3})
_GEOJSON_ELEVATION_INDEX = 2
_LONGITUDE_RANGE = (-180.0, 180.0)
_LATITUDE_RANGE = (-90.0, 90.0)


class InvalidGPSTrackGeoJSONError(ValueError):
    """Raised when stored GPS Track GeoJSON cannot be exported without data loss."""


def new_gpx_document(
    *,
    name: str,
    description: str | None = None,
) -> gpxpy.gpx.GPX:
    """Create a SpeleoDB-authored GPX 1.1 document."""
    gpx = gpxpy.gpx.GPX()
    gpx.creator = GPX_CREATOR
    gpx.version = GPX_VERSION
    gpx.name = name
    gpx.description = description
    return gpx


def sanitize_export_filename(value: str, *, fallback: str) -> str:
    """Remove characters that are unsafe in an attachment filename component."""
    filename = re.sub(r'[\\/*?:"<>|\x00-\x1f\x7f]', "", value).strip()
    return filename or fallback


def dated_export_filename(
    *,
    prefix: str,
    name: str,
    extension: str,
    fallback: str,
) -> str:
    """Build a filesystem-safe, local-date-stamped export filename."""
    safe_name = sanitize_export_filename(name, fallback=fallback)
    return f"{prefix}_{safe_name}_{timezone.localdate().isoformat()}.{extension}"


def gpx_download_response(
    *,
    gpx: gpxpy.gpx.GPX,
    filename: str,
) -> StreamingHttpResponse:
    """Render a GPX document as a UTF-8 attachment response."""
    response = StreamingHttpResponse(
        [gpx.to_xml(version=GPX_VERSION).encode("utf-8")],
        content_type=GPX_CONTENT_TYPE,
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def gps_track_geojson_to_gpx(
    geojson: Any,
    *,
    track_name: str,
) -> gpxpy.gpx.GPX:
    """Convert GeoJSON line features to one ordered GPX track.

    Every LineString becomes one GPX segment. Every member of a
    MultiLineString becomes one segment, retaining feature, member, and point
    order. Only two- and three-dimensional positions are accepted because GPX
    cannot represent additional GeoJSON ordinates without silently losing data.
    """
    feature_collection = _mapping(
        geojson,
        context="GeoJSON document",
    )
    if feature_collection.get("type") != "FeatureCollection":
        raise InvalidGPSTrackGeoJSONError(
            "GPS Track file must be a GeoJSON FeatureCollection."
        )

    features = _sequence(
        feature_collection.get("features"),
        context="FeatureCollection features",
    )

    gpx = new_gpx_document(name=track_name)
    gpx_track = gpxpy.gpx.GPXTrack(name=track_name)
    gpx.tracks.append(gpx_track)

    for feature_index, raw_feature in enumerate(features):
        feature = _mapping(raw_feature, context=f"Feature {feature_index}")
        if feature.get("type") != "Feature":
            raise InvalidGPSTrackGeoJSONError(
                f"Feature {feature_index} must have type 'Feature'."
            )

        geometry = _mapping(
            feature.get("geometry"),
            context=f"Feature {feature_index} geometry",
        )
        geometry_type = geometry.get("type")
        coordinates = geometry.get("coordinates")

        if geometry_type == "LineString":
            gpx_track.segments.append(
                _line_string_to_segment(
                    coordinates,
                    context=f"Feature {feature_index} LineString",
                )
            )
        elif geometry_type == "MultiLineString":
            line_strings = _sequence(
                coordinates,
                context=f"Feature {feature_index} MultiLineString coordinates",
            )
            if not line_strings:
                raise InvalidGPSTrackGeoJSONError(
                    f"Feature {feature_index} MultiLineString must contain a line."
                )
            for line_index, line_string in enumerate(line_strings):
                gpx_track.segments.append(
                    _line_string_to_segment(
                        line_string,
                        context=(
                            f"Feature {feature_index} MultiLineString line {line_index}"
                        ),
                    )
                )
        else:
            raise InvalidGPSTrackGeoJSONError(
                f"Feature {feature_index} has unsupported geometry type "
                f"'{geometry_type}'. Only LineString and MultiLineString are supported."
            )

    return gpx


def _line_string_to_segment(
    raw_coordinates: Any,
    *,
    context: str,
) -> gpxpy.gpx.GPXTrackSegment:
    coordinates = _sequence(raw_coordinates, context=f"{context} coordinates")
    if len(coordinates) < _GEOJSON_LINE_MIN_POSITIONS:
        raise InvalidGPSTrackGeoJSONError(
            f"{context} must contain at least two positions."
        )

    segment = gpxpy.gpx.GPXTrackSegment()
    for point_index, raw_position in enumerate(coordinates):
        position = _sequence(
            raw_position,
            context=f"{context} position {point_index}",
        )
        if len(position) not in _GEOJSON_POSITION_LENGTHS:
            raise InvalidGPSTrackGeoJSONError(
                f"{context} position {point_index} must contain longitude, latitude, "
                "and optional elevation."
            )

        values = tuple(
            _finite_number(
                value,
                context=f"{context} position {point_index} ordinate {ordinate_index}",
            )
            for ordinate_index, value in enumerate(position)
        )
        longitude, latitude = values[:2]
        elevation = (
            values[_GEOJSON_ELEVATION_INDEX]
            if len(values) > _GEOJSON_ELEVATION_INDEX
            else None
        )
        if not _LONGITUDE_RANGE[0] <= longitude <= _LONGITUDE_RANGE[1]:
            raise InvalidGPSTrackGeoJSONError(
                f"{context} position {point_index} longitude is outside [-180, 180]."
            )
        if not _LATITUDE_RANGE[0] <= latitude <= _LATITUDE_RANGE[1]:
            raise InvalidGPSTrackGeoJSONError(
                f"{context} position {point_index} latitude is outside [-90, 90]."
            )

        segment.points.append(
            gpxpy.gpx.GPXTrackPoint(
                latitude=latitude,
                longitude=longitude,
                elevation=elevation,
            )
        )
    return segment


def _mapping(value: Any, *, context: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise InvalidGPSTrackGeoJSONError(f"{context} must be an object.")
    return value


def _sequence(value: Any, *, context: str) -> Sequence[Any]:
    if not isinstance(value, Sequence) or isinstance(value, str | bytes | bytearray):
        raise InvalidGPSTrackGeoJSONError(f"{context} must be an array.")
    return value


def _finite_number(value: Any, *, context: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise InvalidGPSTrackGeoJSONError(f"{context} must be a number.")
    number = float(value)
    if not math.isfinite(number):
        raise InvalidGPSTrackGeoJSONError(f"{context} must be finite.")
    return number
