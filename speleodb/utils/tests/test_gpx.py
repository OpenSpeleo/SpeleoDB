# -*- coding: utf-8 -*-

from __future__ import annotations

import re
from typing import TYPE_CHECKING
from typing import cast

import gpxpy
import pytest
from django.test import override_settings

from speleodb.utils.gpx import GPX_CONTENT_TYPE
from speleodb.utils.gpx import GPX_CREATOR
from speleodb.utils.gpx import GPX_VERSION
from speleodb.utils.gpx import InvalidGPSTrackGeoJSONError
from speleodb.utils.gpx import dated_export_filename
from speleodb.utils.gpx import gps_track_geojson_to_gpx
from speleodb.utils.gpx import gpx_download_response
from speleodb.utils.gpx import new_gpx_document
from speleodb.utils.gpx import sanitize_export_filename

if TYPE_CHECKING:
    from collections.abc import Iterable


def _feature(geometry_type: str, coordinates: object) -> dict[str, object]:
    return {
        "type": "Feature",
        "geometry": {"type": geometry_type, "coordinates": coordinates},
        "properties": {},
    }


def _feature_collection(*features: dict[str, object]) -> dict[str, object]:
    return {"type": "FeatureCollection", "features": list(features)}


def test_new_gpx_document_has_canonical_speleodb_metadata() -> None:
    gpx = new_gpx_document(name="Cueva Águila", description="Survey route")

    assert gpx.creator == GPX_CREATOR
    assert gpx.version == GPX_VERSION
    assert gpx.name == "Cueva Águila"
    assert gpx.description == "Survey route"


@pytest.mark.parametrize(
    ("value", "fallback", "expected"),
    [
        ('  Track\\/*?:"<>|\r\n Name  ', "track", "Track Name"),
        ("   ", "track", "track"),
        ("Tulum - ruta", "track", "Tulum - ruta"),
    ],
)
def test_sanitize_export_filename(
    value: str,
    fallback: str,
    expected: str,
) -> None:
    assert sanitize_export_filename(value, fallback=fallback) == expected


@override_settings(TIME_ZONE="UTC")
def test_dated_export_filename_has_safe_component_and_gpx_extension() -> None:
    filename = dated_export_filename(
        prefix="gps_track",
        name=' Cenote: "East" ',
        extension="gpx",
        fallback="track",
    )

    assert re.fullmatch(r"gps_track_Cenote East_\d{4}-\d{2}-\d{2}\.gpx", filename)


def test_gpx_response_is_utf8_gpx_11_without_library_branding() -> None:
    response = gpx_download_response(
        gpx=new_gpx_document(name="Cueva Águila & Norte"),
        filename="gps_track_cueva.gpx",
    )
    xml = b"".join(cast("Iterable[bytes]", response.streaming_content)).decode("utf-8")

    assert response["Content-Type"] == GPX_CONTENT_TYPE
    assert response["Content-Disposition"] == (
        'attachment; filename="gps_track_cueva.gpx"'
    )
    assert '<gpx xmlns="http://www.topografix.com/GPX/1/1"' in xml
    assert 'version="1.1"' in xml
    assert 'creator="SpeleoDB"' in xml
    assert "gpx.py -- https://github.com/tkrajina/gpxpy" not in xml
    assert gpxpy.parse(xml).name == "Cueva Águila & Norte"


def test_gps_track_conversion_preserves_segments_points_and_elevation() -> None:
    geojson = _feature_collection(
        _feature(
            "LineString",
            [
                [-87.1, 20.1],
                [-87.2, 20.2, 12.5],
            ],
        ),
        _feature(
            "MultiLineString",
            [
                [[-87.3, 20.3, -2], [-87.4, 20.4, 0]],
                [[-87.5, 20.5], [-87.6, 20.6]],
            ],
        ),
    )

    gpx = gps_track_geojson_to_gpx(geojson, track_name="Ordered Track")

    assert len(gpx.tracks) == 1
    assert gpx.tracks[0].name == "Ordered Track"
    segments = gpx.tracks[0].segments
    exported_segments = [
        [(point.longitude, point.latitude, point.elevation) for point in segment.points]
        for segment in segments
    ]
    expected_segments = [
        [(-87.1, 20.1, None), (-87.2, 20.2, 12.5)],
        [(-87.3, 20.3, -2.0), (-87.4, 20.4, 0.0)],
        [(-87.5, 20.5, None), (-87.6, 20.6, None)],
    ]
    assert exported_segments == expected_segments
    assert len(segments) == len(expected_segments)


def test_empty_feature_collection_produces_valid_named_empty_track() -> None:
    gpx = gps_track_geojson_to_gpx(
        _feature_collection(),
        track_name="Empty Track",
    )
    parsed = gpxpy.parse(gpx.to_xml(version=GPX_VERSION))

    assert parsed.name == "Empty Track"
    assert len(parsed.tracks) == 1
    assert parsed.tracks[0].name == "Empty Track"
    assert parsed.tracks[0].segments == []


@pytest.mark.parametrize(
    ("geojson", "message"),
    [
        ({"type": "LineString", "coordinates": []}, "FeatureCollection"),
        (
            {"type": "FeatureCollection", "features": "invalid"},
            "features must be an array",
        ),
        (_feature_collection({"type": "invalid"}), "must have type 'Feature'"),
        (_feature_collection(_feature("Point", [-87.1, 20.1])), "unsupported"),
        (_feature_collection(_feature("LineString", [])), "at least two"),
        (
            _feature_collection(
                _feature("LineString", [[-87.1, 20.1], ["west", 20.2]])
            ),
            "must be a number",
        ),
        (
            _feature_collection(
                _feature("LineString", [[-187.1, 20.1], [-87.2, 20.2]])
            ),
            "longitude",
        ),
        (
            _feature_collection(
                _feature("LineString", [[-87.1, 20.1, 1, 2], [-87.2, 20.2]])
            ),
            "optional elevation",
        ),
        (
            _feature_collection(_feature("MultiLineString", [])),
            "must contain a line",
        ),
    ],
)
def test_gps_track_conversion_rejects_malformed_or_lossy_geometry(
    geojson: object,
    message: str,
) -> None:
    with pytest.raises(InvalidGPSTrackGeoJSONError, match=message):
        gps_track_geojson_to_gpx(geojson, track_name="Invalid")
