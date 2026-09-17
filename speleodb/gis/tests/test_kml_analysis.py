"""KML inspection and publication share geometry decisions and resource budgets."""

from __future__ import annotations

import io
import struct
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Any

import orjson
import pytest

from speleodb.gis.gis_layer_processing import GISLayerProcessingError
from speleodb.gis.gis_layer_processing import analyze_kml_kmz
from speleodb.gis.gis_layer_processing import analyze_kml_kmz_bytes
from speleodb.gis.gis_layer_processing import compile_gis_layer
from speleodb.gis.gis_layer_processing import compile_gis_layer_bytes
from speleodb.gis.gis_layer_processing import limits
from speleodb.gis.gis_layer_processing.common import deterministic_json
from speleodb.gis.gis_layer_processing.errors import ProcessingErrorCode
from speleodb.gis.gis_layer_processing.kml import _encode_geojson

if TYPE_CHECKING:
    from speleodb.gis.gis_layer_processing.types import KMLAnalysis

POINT = "<Point><coordinates>-87.5,20.1</coordinates></Point>"
LINE = "<LineString><coordinates>-87,20 -88,21</coordinates></LineString>"
POLYGON = (
    "<Polygon><outerBoundaryIs><LinearRing><coordinates>"
    "-87,20 -88,21 -87,21 -87,20"
    "</coordinates></LinearRing></outerBoundaryIs></Polygon>"
)
ARTIFACTS = Path(__file__).resolve().parents[2] / "api/v2/tests/artifacts"
MIXED_SAMPLE_PLACEMARKS = 6
MAX_INSPECTION_BYTES = 3000
ROUNDED_LONGITUDE = -87.1234568
ROUNDED_LATITUDE = 20.1234568
ZIP_END_RECORD_SIZE = 22
ZIP_END_RECORD_COUNTS_OFFSET = 8
ZIP64_END_RECORD_COUNTS_OFFSET = 24
ZIP_DIRECTORY_FILENAME_LENGTH_OFFSET = 28


def _document(contents: str) -> bytes:
    return (
        '<kml xmlns="http://www.opengis.net/kml/2.2" '
        'xmlns:gx="http://www.google.com/kml/ext/2.2"><Document>'
        f"{contents}</Document></kml>"
    ).encode()


def _placemark(geometry: str, name: str = "") -> str:
    return f"<Placemark><name>{name}</name>{geometry}</Placemark>"


def _analyze(contents: str) -> KMLAnalysis:
    return analyze_kml_kmz_bytes(_document(contents), filename="places.kml")


def _archive(members: dict[str, bytes]) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, value in members.items():
            archive.writestr(name, value)
    return output.getvalue()


def test_inspection_distinguishes_source_features_parts_and_eligible_places() -> None:
    analysis = _analyze(
        _placemark(POINT, "First")
        + _placemark(
            "<MultiGeometry>"
            f"{POINT}<MultiGeometry><Point><coordinates>-88,21</coordinates>"
            "</Point></MultiGeometry></MultiGeometry>",
            "Point group",
        )
        + _placemark(f"<MultiGeometry>{POINT}{LINE}</MultiGeometry>")
        + _placemark(f"<MultiGeometry>{POINT}<Model/></MultiGeometry>")
        + _placemark(POLYGON)
        + _placemark("")
    )

    report = analysis.inspection()
    assert report["source_placemarks"] == MIXED_SAMPLE_PLACEMARKS
    assert report["places"] == {
        "eligible_placemarks": 2,
        "point_count": 3,
        "unique_coordinate_count": 2,
        "duplicate_coordinate_count": 1,
        "skipped_placemarks": 4,
    }
    assert report["overlay"] == {
        "source_placemarks": 5,
        "feature_count": 6,
        "point_parts": 5,
        "line_parts": 1,
        "polygon_parts": 1,
    }
    assert [point.name for point in analysis.landmark_candidates] == [
        "First",
        "Point group",
        "Point group",
    ]
    assert "coordinates" not in orjson.dumps(report).decode()
    assert "First" not in orjson.dumps(report).decode()


@pytest.mark.parametrize(
    "geometry",
    [
        f"<MultiGeometry>{POINT}{LINE}</MultiGeometry>",
        f"<MultiGeometry>{POINT}<Model/></MultiGeometry>",
        f"<MultiGeometry>{POINT}<gx:Track/></MultiGeometry>",
        f'<MultiGeometry>{POINT}<custom:Geometry xmlns:custom="urn:custom"/>'
        "</MultiGeometry>",
    ],
)
def test_mixed_geometry_never_extracts_anchor_points(geometry: str) -> None:
    analysis = _analyze(_placemark(geometry))
    assert not analysis.landmark_candidates
    assert analysis.point_parts == 1


def test_foreign_geometry_is_reported_once_but_metadata_children_are_not() -> None:
    analysis = _analyze(
        _placemark(
            f'<MultiGeometry>{POINT}<custom:Geometry xmlns:custom="urn:custom">'
            "<custom:Coordinates>unknown</custom:Coordinates>"
            "</custom:Geometry></MultiGeometry>"
            '<ExtendedData><custom:Metadata xmlns:custom="urn:custom"/></ExtendedData>'
        )
    )
    warnings = {item.code: item.count for item in analysis.warnings}
    assert warnings == {"UNSUPPORTEDEXTENSION": 1, "PLACEMARKS_NOT_IMPORTED": 1}


def test_metadata_and_update_payloads_are_not_source_placemarks() -> None:
    analysis = _analyze(
        "<name>Actual document</name>"
        "<ExtendedData><Document><name>Embedded metadata document</name>"
        "<visibility>0</visibility>"
        + _placemark(POINT, "Metadata payload")
        + "</Document></ExtendedData>"
        "<NetworkLinkControl><Update><Create><Document>"
        + _placemark(POINT, "Remote update payload")
        + "</Document></Create></Update></NetworkLinkControl>"
        + _placemark(POINT, "Actual feature")
    )
    assert analysis.source_placemarks == 1
    assert analysis.overlay_placemarks == 1
    assert [candidate.name for candidate in analysis.landmark_candidates] == [
        "Actual feature"
    ]
    properties = analysis.feature_collection["features"][0]["properties"]
    assert properties["folder_path"] == ["Actual document"]
    assert properties["initial_visibility"] is True
    assert "UNSUPPORTED_UPDATE" in {warning.code for warning in analysis.warnings}


def test_normalization_preserves_unicode_and_bounds_only_landmark_names() -> None:
    name = "Cénote " + "é" * 110
    description = (
        "<description><![CDATA[<b>Agua &amp; más</b>\nSecond line]]></description>"
    )
    analysis = _analyze(_placemark(POINT + description, name))

    candidate = analysis.landmark_candidates[0]
    assert candidate.name == name[:100]
    assert candidate.description == "Agua & más\nSecond line"
    assert analysis.feature_collection["features"][0]["properties"]["name"] == name
    warning = next(
        item for item in analysis.warnings if item.code == "LANDMARK_NAMES_SHORTENED"
    )
    assert warning.count == 1
    assert warning.modes == ("places",)


def test_unnamed_and_rounded_candidates_remain_ready_for_confirmation() -> None:
    analysis = _analyze(
        _placemark(
            "<Point><coordinates>-87.123456789,20.123456789,4</coordinates></Point>"
        )
    )
    candidate = analysis.landmark_candidates[0]
    assert candidate.name == ""
    assert candidate.longitude == ROUNDED_LONGITUDE
    assert candidate.latitude == ROUNDED_LATITUDE
    assert {item.code for item in analysis.warnings} == {"GEOMETRY_DISPLAYED_IN_2D"}


def test_unsupported_constructs_are_reported_without_child_warning_noise() -> None:
    analysis = _analyze(
        "<NetworkLink><Link><href>http://localhost/private</href></Link></NetworkLink>"
        "<GroundOverlay><Icon><href>images/test.png</href></Icon></GroundOverlay>"
        + _placemark("<Model><Location><latitude>20</latitude></Location></Model>")
        + "<gx:Tour><gx:Playlist><gx:FlyTo><LookAt><heading>0</heading>"
        "</LookAt></gx:FlyTo></gx:Playlist></gx:Tour>"
    )
    assert {item.code for item in analysis.warnings} == {
        "UNSUPPORTED_NETWORKLINK",
        "UNSUPPORTED_GROUNDOVERLAY",
        "UNSUPPORTED_MODEL",
        "UNSUPPORTED_TOUR",
        "PLACEMARKS_NOT_IMPORTED",
    }
    assert analysis.inspection()["overlay"]["feature_count"] == 0
    with pytest.raises(GISLayerProcessingError) as error:
        compile_gis_layer_bytes(_document(_placemark("<Model/>")), filename="empty.kml")
    assert error.value.code == ProcessingErrorCode.KML_NO_RENDERABLE_GEOMETRY


def test_comment_nodes_shared_styles_polygon_holes_and_serialization_survive() -> None:
    polygon = POLYGON.replace(
        "</Polygon>",
        "<innerBoundaryIs><LinearRing><coordinates>"
        "-87.1,20.1 -87.2,20.2 -87.1,20.2 -87.1,20.1"
        "</coordinates></LinearRing></innerBoundaryIs></Polygon>",
    )
    analysis = _analyze(
        '<Style id="blue"><PolyStyle><color>ffcc5500</color></PolyStyle></Style>'
        + _placemark("<!-- comment --><styleUrl>#blue</styleUrl>" + polygon, "Area")
    )
    feature = analysis.feature_collection["features"][0]
    outer_and_inner_ring_count = 2
    assert len(feature["geometry"]["coordinates"]) == outer_and_inner_ring_count
    assert feature["properties"]["render_color"] == "#0055cc"
    assert analysis.display_geojson == deterministic_json(analysis.feature_collection)


@pytest.mark.parametrize("inline", [False, True])
def test_local_styles_have_one_aggregated_overlay_appearance_warning(
    inline: bool,
) -> None:
    style = (
        '<Style id="blue"><LineStyle><color>ffcc5500</color>'
        "<width>3</width></LineStyle></Style>"
    )
    if inline:
        source = _placemark(style + POINT)
    else:
        source = (
            style + '<StyleMap id="mapped"><Pair><key>normal</key>'
            "<styleUrl>#blue</styleUrl></Pair></StyleMap>"
            + _placemark("<styleUrl>#mapped</styleUrl>" + POINT)
        )
    analysis = _analyze(source)
    assert [
        (warning.code, warning.count, warning.modes) for warning in analysis.warnings
    ] == [("LAYER_APPEARANCE", 1, ("overlay",))]


def test_hidden_folder_and_placemark_visibility_is_reported_for_both_modes() -> None:
    analysis = _analyze(
        "<Folder><visibility>0</visibility>"
        + _placemark(POINT)
        + "</Folder>"
        + _placemark("<visibility>0</visibility>" + POINT)
    )
    warning = next(
        item for item in analysis.warnings if item.code == "HIDDEN_ITEMS_INCLUDED"
    )
    assert warning.modes == ("places", "overlay")
    hidden_declarations = 2
    assert warning.count == hidden_declarations
    assert all(
        feature["properties"]["initial_visibility"] is False
        for feature in analysis.feature_collection["features"]
    )


def test_default_visibility_empty_styles_and_structural_children_do_not_warn() -> None:
    analysis = _analyze(
        '<Style id="empty"><LineStyle/></Style>'
        '<StyleMap id="mapped"><Pair><key>normal</key>'
        "<styleUrl>#empty</styleUrl></Pair></StyleMap>"
        + _placemark(
            "<visibility>1</visibility><styleUrl>#mapped</styleUrl>"
            "<LookAt><latitude>20</latitude><longitude>-87.5</longitude>"
            "<heading>0</heading></LookAt>" + POINT
        )
    )
    assert not analysis.warnings


def test_known_missing_xsi_namespace_is_repaired_and_reported() -> None:
    source = _document(_placemark(POINT)).replace(
        b"<kml ", b'<kml xsi:schemaLocation="schema" '
    )
    analysis = analyze_kml_kmz_bytes(source, filename="repair.kml")
    assert len(analysis.landmark_candidates) == 1
    assert "NAMESPACE_REPAIRED" in {warning.code for warning in analysis.warnings}


def test_kmz_uses_primary_document_and_reports_unimported_extra_documents() -> None:
    source = _archive(
        {
            "secondary.kml": _document(_placemark(LINE)),
            "doc.kml": _document(_placemark(POINT, "Primary")),
            "assets/icon.png": b"not decoded or read",
        }
    )
    analysis = analyze_kml_kmz_bytes(source, filename="MAP.KMZ")
    assert analysis.landmark_candidates[0].name == "Primary"
    assert (
        next(
            item
            for item in analysis.warnings
            if item.code == "ADDITIONAL_KML_DOCUMENTS"
        ).count
        == 1
    )
    assert (
        compile_gis_layer_bytes(source, filename="MAP.KMZ").display_geojson
        == analysis.display_geojson
    )


def test_ambiguous_archive_is_not_silently_classified() -> None:
    source = _archive({"one.kml": _document(""), "two.kml": _document("")})
    with pytest.raises(GISLayerProcessingError) as error:
        analyze_kml_kmz_bytes(source, filename="ambiguous.kmz")
    assert error.value.code == ProcessingErrorCode.ZIP_AMBIGUOUS_MAIN_KML


@pytest.mark.parametrize(
    "name", ["../doc.kml", "/doc.kml", "folder/../../doc.kml", "nested.kmz"]
)
def test_unsafe_archive_members_are_rejected(name: str) -> None:
    source = _archive({"doc.kml": _document(_placemark(POINT)), name: b"data"})
    with pytest.raises(GISLayerProcessingError) as error:
        analyze_kml_kmz_bytes(source, filename="unsafe.kmz")
    assert error.value.code == ProcessingErrorCode.ZIP_UNSAFE_ENTRY


@pytest.mark.parametrize("encoding", ["utf-8", "utf-16", "utf-32"])
def test_entity_declarations_are_rejected_for_every_xml_encoding(encoding: str) -> None:
    source = (
        '<!DOCTYPE kml [<!ENTITY secret SYSTEM "file:///etc/passwd">]>'
        '<kml xmlns="http://www.opengis.net/kml/2.2"/>'
    ).encode(encoding)
    with pytest.raises(GISLayerProcessingError) as error:
        analyze_kml_kmz_bytes(source, filename="unsafe.kml")
    assert error.value.code == ProcessingErrorCode.XML_UNSAFE


@pytest.mark.parametrize(
    ("setting", "limit", "contents", "code"),
    [
        ("MAX_XML_DEPTH", 4, _placemark(POINT), ProcessingErrorCode.XML_DEPTH_LIMIT),
        (
            "MAX_KML_PLACEMARKS",
            1,
            _placemark(POINT) * 2,
            ProcessingErrorCode.KML_FEATURE_LIMIT,
        ),
        (
            "MAX_KML_COORDINATES",
            1,
            _placemark(LINE),
            ProcessingErrorCode.KML_COORDINATE_LIMIT,
        ),
    ],
)
def test_parser_limits_apply_during_scan(
    monkeypatch: pytest.MonkeyPatch,
    setting: str,
    limit: int,
    contents: str,
    code: ProcessingErrorCode,
) -> None:
    monkeypatch.setattr(limits, setting, limit)
    with pytest.raises(GISLayerProcessingError) as error:
        _analyze(contents)
    assert error.value.code == code


def test_exact_geometry_limits_are_inclusive(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(limits, "MAX_XML_DEPTH", 5)
    monkeypatch.setattr(limits, "MAX_KML_PLACEMARKS", 1)
    monkeypatch.setattr(limits, "MAX_KML_COORDINATES", 1)
    analysis = _analyze(_placemark(POINT))
    assert len(analysis.landmark_candidates) == 1


def test_archive_member_count_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(limits, "MAX_KMZ_MEMBERS", 1)
    source = _archive({"doc.kml": _document(_placemark(POINT)), "image.png": b"image"})
    with pytest.raises(GISLayerProcessingError) as error:
        analyze_kml_kmz_bytes(source, filename="large.kmz")
    assert error.value.code == ProcessingErrorCode.ZIP_ENTRY_LIMIT


@pytest.mark.parametrize("zip64", [False, True])
def test_actual_member_limit_precedes_zipinfo_allocation_even_if_counts_lie(
    monkeypatch: pytest.MonkeyPatch,
    zip64: bool,
) -> None:
    if zip64:
        monkeypatch.setattr(zipfile, "ZIP_FILECOUNT_LIMIT", 0)
    source = bytearray(
        _archive(
            {
                "doc.kml": _document(_placemark(POINT)),
                "image.png": b"image",
            }
        )
    )
    if zip64:
        offset = source.index(b"PK\x06\x06") + ZIP64_END_RECORD_COUNTS_OFFSET
        struct.pack_into("<QQ", source, offset, 1, 1)
    else:
        offset = len(source) - ZIP_END_RECORD_SIZE + ZIP_END_RECORD_COUNTS_OFFSET
        struct.pack_into("<HH", source, offset, 1, 1)
    monkeypatch.setattr(limits, "MAX_KMZ_MEMBERS", 1)

    def forbid_eager_allocation(*args: Any, **kwargs: Any) -> None:
        pytest.fail("ZipFile must not allocate ZipInfo before the directory limit.")

    monkeypatch.setattr(zipfile, "ZipFile", forbid_eager_allocation)
    with pytest.raises(GISLayerProcessingError) as error:
        analyze_kml_kmz_bytes(bytes(source), filename="many.kmz")
    assert error.value.code == ProcessingErrorCode.ZIP_ENTRY_LIMIT


@pytest.mark.parametrize("zip64", [False, True])
def test_small_standard_and_zip64_archives_remain_supported(
    monkeypatch: pytest.MonkeyPatch,
    zip64: bool,
) -> None:
    if zip64:
        monkeypatch.setattr(zipfile, "ZIP_FILECOUNT_LIMIT", 0)
    source = _archive({"doc.kml": _document(_placemark(POINT, "Retained"))})
    monkeypatch.setattr(limits, "MAX_KMZ_MEMBERS", 1)
    analysis = analyze_kml_kmz_bytes(source, filename="valid.kmz")
    assert analysis.landmark_candidates[0].name == "Retained"


@pytest.mark.parametrize("damage", ["truncated_end", "truncated_fields", "wrong_count"])
def test_malformed_directory_records_have_structured_errors(damage: str) -> None:
    source = bytearray(_archive({"doc.kml": _document(_placemark(POINT))}))
    if damage == "truncated_end":
        source = source[:-1]
    elif damage == "truncated_fields":
        offset = source.index(b"PK\x01\x02") + ZIP_DIRECTORY_FILENAME_LENGTH_OFFSET
        struct.pack_into("<H", source, offset, 65535)
    else:
        offset = len(source) - ZIP_END_RECORD_SIZE + ZIP_END_RECORD_COUNTS_OFFSET
        struct.pack_into("<HH", source, offset, 0, 0)
    with pytest.raises(GISLayerProcessingError) as error:
        analyze_kml_kmz_bytes(bytes(source), filename="corrupt.kmz")
    assert error.value.code == ProcessingErrorCode.ZIP_INVALID


def test_source_streaming_limit_and_file_position_reset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = io.BytesIO(_document(_placemark(POINT)))
    source.seek(10)
    monkeypatch.setattr(limits, "source_bytes_limit", lambda: 100)
    with pytest.raises(GISLayerProcessingError) as error:
        analyze_kml_kmz(source, filename="large.kml")
    assert error.value.code == ProcessingErrorCode.SOURCE_TOO_LARGE
    assert source.tell() == 0


def test_publication_also_bounds_file_reads(monkeypatch: pytest.MonkeyPatch) -> None:
    source = io.BytesIO(_document(_placemark(POINT)))
    monkeypatch.setattr(limits, "source_bytes_limit", lambda: 100)
    with pytest.raises(GISLayerProcessingError) as error:
        compile_gis_layer(source, filename="large.kml")
    assert error.value.code == ProcessingErrorCode.SOURCE_TOO_LARGE
    assert source.tell() == 0


def test_expanded_kmz_size_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    source = _archive({"doc.kml": _document(" " * 5000 + _placemark(POINT))})
    monkeypatch.setattr(limits, "source_bytes_limit", lambda: 1000)
    with pytest.raises(GISLayerProcessingError) as error:
        analyze_kml_kmz_bytes(source, filename="compressed.kmz")
    assert error.value.code == ProcessingErrorCode.SOURCE_TOO_LARGE


def test_geojson_output_is_bounded_before_accumulation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(limits, "source_bytes_limit", lambda: 100)
    data: dict[str, Any] = {
        "type": "FeatureCollection",
        "features": [{"name": "x" * 200}],
    }
    with pytest.raises(GISLayerProcessingError) as error:
        _encode_geojson(data)
    assert error.value.code == ProcessingErrorCode.GEOJSON_TOO_LARGE


@pytest.mark.parametrize(
    ("relative_path", "source_count", "point_count", "polygon_count"),
    [
        ("sample.kml", 736, 736, 0),
        ("gis_layers/us_states/us_states_5m.kmz", 52, 0, 288),
        (
            "gis_layers/mx_protected_areas/Áreas Naturales Protegidas 2018.kmz",
            547,
            366,
            781,
        ),
    ],
)
def test_real_files_keep_source_and_geometry_counts_distinct(
    relative_path: str, source_count: int, point_count: int, polygon_count: int
) -> None:
    path = ARTIFACTS / relative_path
    analysis = analyze_kml_kmz_bytes(path.read_bytes(), filename=path.name)
    assert analysis.source_placemarks == source_count
    assert analysis.point_parts == point_count
    assert analysis.polygon_parts == polygon_count
    assert analysis.overlay_placemarks == source_count
    assert len(analysis.landmark_candidates) == point_count
    assert len(orjson.dumps(analysis.inspection())) < MAX_INSPECTION_BYTES
