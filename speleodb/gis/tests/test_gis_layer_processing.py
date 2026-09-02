"""Focused tests for GIS Layer processor selection and conversion."""

from __future__ import annotations

import io
import math
import zipfile
from pathlib import Path
from typing import Any

import orjson
import pytest
import shapefile
from django.core.validators import MaxLengthValidator
from django.core.validators import MinLengthValidator
from pyproj import CRS

from speleodb.gis.gis_layer_processing import BaseGISLayerProcessor
from speleodb.gis.gis_layer_processing import GISLayerProcessingError
from speleodb.gis.gis_layer_processing import KMLProcessor
from speleodb.gis.gis_layer_processing import KMZProcessor
from speleodb.gis.gis_layer_processing import ShapefileProcessor
from speleodb.gis.gis_layer_processing import TopoJSONProcessor
from speleodb.gis.gis_layer_processing import compile_gis_layer_bytes
from speleodb.gis.gis_layer_processing import processor_for_filename
from speleodb.gis.gis_layer_processing.common import iter_coordinate_positions
from speleodb.utils.validators import LatitudeValidator
from speleodb.utils.validators import LongitudeValidator

GIS_LAYER_ARTIFACTS = (
    Path(__file__).resolve().parents[2]
    / "api"
    / "v2"
    / "tests"
    / "artifacts"
    / "gis_layers"
)
KML = (
    b'<kml xmlns="http://www.opengis.net/kml/2.2"><Placemark><name>Entrance</name>'
    b"<Point><coordinates>-87.5,20.1</coordinates></Point></Placemark></kml>"
)
US_STATES_FEATURE_COUNT = 52


def _assert_renderable_feature_collection(data: Any) -> None:
    assert isinstance(data, dict)
    assert data.get("type") == "FeatureCollection"
    features = data.get("features")
    assert isinstance(features, list)
    assert features

    position_count = 0
    for feature in features:
        assert isinstance(feature, dict)
        assert feature.get("type") == "Feature"
        geometry = feature.get("geometry")
        assert isinstance(geometry, dict)
        assert geometry.get("type") in {
            "Point",
            "MultiPoint",
            "LineString",
            "MultiLineString",
            "Polygon",
            "MultiPolygon",
            "GeometryCollection",
        }
        for position in iter_coordinate_positions(geometry):
            MinLengthValidator(2)(position)
            MaxLengthValidator(3)(position)
            assert all(isinstance(value, int | float) for value in position)
            assert all(math.isfinite(value) for value in position)
            LongitudeValidator()(position[0])
            LatitudeValidator()(position[1])
            position_count += 1
    assert position_count > 0


def test_kml_is_converted_to_geojson() -> None:
    result = compile_gis_layer_bytes(KML, filename="layer.kml")
    data = orjson.loads(result.display_geojson)

    assert data["type"] == "FeatureCollection"
    assert data["features"][0]["properties"]["name"] == "Entrance"


def test_kmz_is_converted_to_geojson() -> None:
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as kmz:
        kmz.writestr("doc.kml", KML)

    result = compile_gis_layer_bytes(archive.getvalue(), filename="layer.kmz")

    assert orjson.loads(result.display_geojson)["type"] == "FeatureCollection"


def test_geojson_is_rejected_by_the_converter() -> None:
    with pytest.raises(GISLayerProcessingError, match="uploaded directly"):
        compile_gis_layer_bytes(
            b'{"type":"FeatureCollection","features":[]}',
            filename="layer.geojson",
        )


@pytest.mark.parametrize(
    ("filename", "processor_type"),
    [
        ("layer.kml", KMLProcessor),
        ("layer.kmz", KMZProcessor),
        ("layer.topojson", TopoJSONProcessor),
        ("layer.zip", ShapefileProcessor),
    ],
)
def test_processor_is_selected_by_file_extension(
    filename: str,
    processor_type: type[BaseGISLayerProcessor],
) -> None:
    assert isinstance(processor_for_filename(filename), processor_type)


def test_unsupported_extension_has_a_user_friendly_error() -> None:
    with pytest.raises(GISLayerProcessingError, match="not supported"):
        processor_for_filename("layer.gpkg")


def test_topojson_is_converted_to_geojson() -> None:
    topology = {
        "type": "Topology",
        "transform": {"scale": [0.1, 0.1], "translate": [-88, 20]},
        "arcs": [[[0, 0], [5, 5]]],
        "objects": {
            "survey": {
                "type": "GeometryCollection",
                "geometries": [
                    {
                        "type": "LineString",
                        "arcs": [0],
                        "properties": {"name": "Traverse"},
                    }
                ],
            }
        },
    }

    result = compile_gis_layer_bytes(
        orjson.dumps(topology),
        filename="layer.topojson",
    )
    data = orjson.loads(result.display_geojson)

    assert data["features"][0]["geometry"]["coordinates"] == [
        [-88.0, 20.0],
        [-87.5, 20.5],
    ]


def test_zipped_shapefile_is_converted_to_wgs84_geojson() -> None:
    shp = io.BytesIO()
    shx = io.BytesIO()
    dbf = io.BytesIO()
    writer = shapefile.Writer(shp=shp, shx=shx, dbf=dbf)
    try:
        writer.field("name", "C")  # type: ignore[arg-type]  # pyshp stub binds self twice
        writer.point(-87.5, 20.1)
        writer.record("Entrance")
    finally:
        writer.close()
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as zip_file:
        zip_file.writestr("caves.shp", shp.getvalue())
        zip_file.writestr("caves.shx", shx.getvalue())
        zip_file.writestr("caves.dbf", dbf.getvalue())
        zip_file.writestr("caves.prj", CRS.from_epsg(4326).to_wkt())

    result = compile_gis_layer_bytes(archive.getvalue(), filename="caves.zip")
    data = orjson.loads(result.display_geojson)

    assert data["features"][0]["properties"]["name"] == "Entrance"
    assert data["features"][0]["geometry"]["coordinates"] == [-87.5, 20.1]


@pytest.mark.parametrize(
    ("relative_path", "expected_feature_count"),
    [
        pytest.param(
            Path("mx_protected_areas") / "Áreas Naturales Protegidas 2018.kmz",
            None,
            id="mexico-protected-areas-kmz",
        ),
        pytest.param(
            Path("us_states/us_states_5m.kml"),
            52,
            id="us-states-kml",
        ),
        pytest.param(
            Path("us_states/us_states_5m.kmz"),
            52,
            id="us-states-kmz",
        ),
        pytest.param(
            Path("us_states/us_states_5m.topojson"),
            52,
            id="us-states-topojson",
        ),
        pytest.param(
            Path("us_states/us_states_5m.zip"),
            52,
            id="us-states-shapefile",
        ),
    ],
)
def test_real_world_artifact_is_converted_to_renderable_geojson(
    relative_path: Path,
    expected_feature_count: int | None,
) -> None:
    source_path = GIS_LAYER_ARTIFACTS / relative_path

    result = compile_gis_layer_bytes(
        source_path.read_bytes(),
        filename=source_path.name,
    )
    data = orjson.loads(result.display_geojson)

    _assert_renderable_feature_collection(data)
    if expected_feature_count is not None:
        assert len(data["features"]) == expected_feature_count


def test_real_world_geojson_artifact_is_ready_for_direct_display() -> None:
    source_path = GIS_LAYER_ARTIFACTS / "us_states" / "us_states_5m.geojson"

    data = orjson.loads(source_path.read_bytes())

    _assert_renderable_feature_collection(data)
    assert len(data["features"]) == US_STATES_FEATURE_COUNT
