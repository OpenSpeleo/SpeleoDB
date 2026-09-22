# -*- coding: utf-8 -*-

from __future__ import annotations

import io
import math
import re
from collections import Counter
from dataclasses import dataclass
from dataclasses import field
from typing import Any

from django.core.exceptions import ValidationError
from django.core.validators import MinLengthValidator
from lxml import etree  # type: ignore[attr-defined]

from speleodb.gis.gis_layer_processing import limits
from speleodb.gis.gis_layer_processing.base import BaseGISLayerProcessor
from speleodb.gis.gis_layer_processing.common import calculate_bbox
from speleodb.gis.gis_layer_processing.common import deterministic_json
from speleodb.gis.gis_layer_processing.common import explode_geometry_collections
from speleodb.gis.gis_layer_processing.common import iter_coordinate_positions
from speleodb.gis.gis_layer_processing.common import validate_position
from speleodb.gis.gis_layer_processing.errors import GISLayerProcessingError
from speleodb.gis.gis_layer_processing.errors import ProcessingErrorCode
from speleodb.gis.gis_layer_processing.types import CompilationResult
from speleodb.gis.gis_layer_processing.types import KMLAnalysis
from speleodb.gis.gis_layer_processing.types import KMLWarning
from speleodb.gis.gis_layer_processing.types import LandmarkCandidate
from speleodb.gis.models.gis_layer import GISLayerSourceFormat
from speleodb.utils.sanitize import sanitize_field_name

_CANONICAL_XSI_NAMESPACE = "http://www.w3.org/2001/XMLSchema-instance"
_KML_NAMESPACES = {
    "",
    "http://earth.google.com/kml/2.0",
    "http://earth.google.com/kml/2.1",
    "http://www.opengis.net/kml/2.2",
}
_ROOT_KML_PATTERN = re.compile(rb"<(?:[A-Za-z_][\w.-]*:)?kml(?:\s|>)")
_XML_PROLOG_PATTERN = re.compile(rb"\A(?:\s+|<\?.*?\?>|<!--.*?-->)*", re.DOTALL)
_XML_ATTRIBUTE_PATTERN = re.compile(
    rb"\s+(?P<name>[\w:.-]+)\s*=\s*(?P<quote>['\"])(?P<value>.*?)(?P=quote)",
    re.DOTALL,
)
_XML_HEADER_BYTES = 64 * 1024
_XML_ERROR_LINE_CHARS = 240
_GEOMETRY_NAMES = {"Point", "LineString", "Polygon", "MultiGeometry"}
_GX_NAMESPACE = "http://www.google.com/kml/ext/2.2"
_METADATA_NAMESPACES = {
    "http://www.w3.org/2005/Atom",
    "urn:oasis:names:tc:ciq:xsdschema:xAL:2.0",
}
_GX_FEATURE_PROPERTIES = {"balloonVisibility", "TimeStamp", "TimeSpan"}
_FEATURE_PROPERTIES = {
    "name",
    "visibility",
    "open",
    "address",
    "phoneNumber",
    "Snippet",
    "snippet",
    "description",
    "LookAt",
    "Camera",
    "TimeStamp",
    "TimeSpan",
    "styleUrl",
    "Style",
    "StyleMap",
    "Region",
    "Metadata",
    "ExtendedData",
}
_UNSUPPORTED_CONSTRUCTS = {
    "NetworkLink": "Linked map content is not fetched or imported.",
    "GroundOverlay": "Ground images are not imported.",
    "ScreenOverlay": "Screen images are not imported.",
    "PhotoOverlay": "Photo overlays are not imported.",
    "Model": "3D models are not imported.",
    "Track": "KML animated tracks are not imported.",
    "MultiTrack": "KML animated tracks are not imported.",
    "Tour": "Google Earth tours are not imported.",
    "Update": "Linked-document updates are not applied during import.",
}


@dataclass(slots=True)
class _ScanResult:
    styles: dict[str, dict[str, Any]] = field(default_factory=dict)
    style_maps: dict[str, str] = field(default_factory=dict)
    hierarchy_ids: Counter[str] = field(default_factory=Counter)
    source_placemarks: int = 0
    coordinate_count: int = 0
    warnings: Counter[str] = field(default_factory=Counter)


@dataclass(slots=True)
class _FeatureAnalysis:
    features: list[dict[str, Any]] = field(default_factory=list)
    candidates: list[LandmarkCandidate] = field(default_factory=list)
    eligible_placemarks: int = 0
    shortened_names: int = 0
    three_dimensional: int = 0
    parts: Counter[str] = field(default_factory=Counter)


@dataclass(slots=True)
class _FolderContext:
    kind: str
    stable_id: str
    name: str = ""
    visibility: bool = True


def compile_kml(source: bytes) -> dict[str, Any]:
    return _require_overlay(analyze_kml(source)).feature_collection


def analyze_kml(source: bytes, *, warnings: tuple[KMLWarning, ...] = ()) -> KMLAnalysis:
    limits.check_source_size(len(source))
    _reject_unsafe_xml(source)

    parse_source = _repair_duplicated_kml_namespace(source)
    try:
        scan = _scan_document(parse_source, diagnostic_source=source)
    except etree.XMLSyntaxError as strict_error:
        repaired = (
            _repair_missing_xsi_namespace(parse_source)
            if strict_error.code == etree.ErrorTypes.NS_ERR_UNDEFINED_NAMESPACE
            and strict_error.msg.startswith("Namespace prefix xsi ")
            else None
        )
        if repaired is None:
            raise _xml_error(source, strict_error.position) from strict_error
        try:
            scan = _scan_document(repaired, diagnostic_source=source)
        except etree.XMLSyntaxError as repaired_error:
            # The inserted namespace changes columns on its line, not line numbers.
            raise _xml_error(
                source, (repaired_error.position[0], 0)
            ) from repaired_error
        parse_source = repaired
        scan.warnings["NAMESPACE_REPAIRED"] += 1

    result = _compile_features(parse_source, scan)
    features = explode_geometry_collections(result.features)
    feature_ids = [feature["id"] for feature in features]
    if len(feature_ids) != len(set(feature_ids)):
        raise GISLayerProcessingError(
            ProcessingErrorCode.XML_INVALID,
            "The KML document contains duplicate feature identities.",
        )
    positions = (
        position
        for feature in features
        for position in iter_coordinate_positions(feature["geometry"])
    )
    bbox = calculate_bbox(positions)
    feature_collection: dict[str, Any] = {
        "type": "FeatureCollection",
        "features": features,
    }
    if bbox is not None:
        feature_collection["bbox"] = bbox
    display_geojson = _encode_geojson(feature_collection)
    return KMLAnalysis(
        feature_collection=feature_collection,
        display_geojson=display_geojson,
        landmark_candidates=tuple(result.candidates),
        source_placemarks=scan.source_placemarks,
        eligible_placemarks=result.eligible_placemarks,
        overlay_placemarks=len(result.features),
        point_parts=result.parts["Point"],
        line_parts=result.parts["LineString"],
        polygon_parts=result.parts["Polygon"],
        warnings=(*warnings, *_analysis_warnings(scan, result)),
    )


def _require_overlay(analysis: KMLAnalysis) -> KMLAnalysis:
    if not analysis.feature_collection["features"]:
        raise GISLayerProcessingError(
            ProcessingErrorCode.KML_NO_RENDERABLE_GEOMETRY,
            "This file does not contain supported map geometry.",
            details=analysis.inspection(),
        )
    return analysis


def _encode_geojson(feature_collection: dict[str, Any]) -> bytes:
    """Serialize per feature so the output cap applies before accumulation."""
    output = io.BytesIO()

    def write(chunk: bytes) -> None:
        if output.tell() + len(chunk) > limits.source_bytes_limit():
            raise GISLayerProcessingError(
                ProcessingErrorCode.GEOJSON_TOO_LARGE,
                "The converted map exceeds the import size limit.",
                details={"limit_bytes": limits.source_bytes_limit()},
            )
        output.write(chunk)

    write(b"{")
    if "bbox" in feature_collection:
        write(b'"bbox":' + deterministic_json(feature_collection["bbox"]) + b",")
    write(b'"features":[')
    for index, feature in enumerate(feature_collection["features"]):
        if index:
            write(b",")
        write(deterministic_json(feature))
    write(b'],"type":"FeatureCollection"}')
    return output.getvalue()


def _analysis_warnings(scan: _ScanResult, result: _FeatureAnalysis) -> list[KMLWarning]:
    warnings: list[KMLWarning] = []
    for name, message in _UNSUPPORTED_CONSTRUCTS.items():
        if count := scan.warnings[name]:
            warnings.append(KMLWarning(f"UNSUPPORTED_{name.upper()}", message, count))
    for key, message, modes in (
        (
            "NAMESPACE_REPAIRED",
            "A missing XML namespace was repaired.",
            ("places", "overlay"),
        ),
        (
            "Time",
            "Time-based visibility and animation are not retained.",
            ("places", "overlay"),
        ),
        ("Icon", "Custom icon images are not retained.", ("places", "overlay")),
        ("ExternalStyle", "External styles are not fetched or imported.", ("overlay",)),
        (
            "LAYER_APPEARANCE",
            "Colors and line styles use the layer appearance in SpeleoDB.",
            ("overlay",),
        ),
        (
            "HIDDEN_ITEMS_INCLUDED",
            "Items hidden in the file are included in the import.",
            ("places", "overlay"),
        ),
        (
            "UnsupportedExtension",
            "Unrecognized geometry or feature extensions are not imported.",
            ("places", "overlay"),
        ),
        (
            "LinearRing",
            "Standalone linear rings are not imported.",
            ("places", "overlay"),
        ),
    ):
        if count := scan.warnings[key]:
            warnings.append(KMLWarning(key.upper(), message, count, modes))
    if skipped := scan.source_placemarks - result.eligible_placemarks:
        warnings.append(
            KMLWarning(
                "PLACEMARKS_NOT_IMPORTED",
                "Only placemarks made entirely of points become editable places.",
                skipped,
                ("places",),
            )
        )
    if result.shortened_names:
        warnings.append(
            KMLWarning(
                "LANDMARK_NAMES_SHORTENED",
                "Place names longer than 100 characters are shortened.",
                result.shortened_names,
                ("places",),
            )
        )
    if result.three_dimensional:
        warnings.append(
            KMLWarning(
                "GEOMETRY_DISPLAYED_IN_2D",
                "Altitude and extrusion are displayed in 2D.",
                result.three_dimensional,
            )
        )
    return warnings


def _reject_unsafe_xml(source: bytes) -> None:
    # Removing NUL bytes also detects declarations in UTF-16/UTF-32 XML.
    upper_source = source.replace(b"\x00", b"").upper()
    if b"<!DOCTYPE" in upper_source or b"<!ENTITY" in upper_source:
        raise GISLayerProcessingError(
            ProcessingErrorCode.XML_UNSAFE,
            "KML documents containing DTD or entity declarations are not accepted.",
        )
    has_xinclude_namespace = b"HTTP://WWW.W3.ORG/2001/XINCLUDE" in upper_source
    if has_xinclude_namespace or b"<XI:INCLUDE" in upper_source:
        raise GISLayerProcessingError(
            ProcessingErrorCode.XML_UNSAFE,
            "KML documents containing XInclude are not accepted.",
        )


def _repair_missing_xsi_namespace(source: bytes) -> bytes | None:
    if b"xsi:" not in source:
        return None
    root_match = _root_kml_match(source)
    if root_match is None:
        return None
    tag_end = _find_xml_tag_end(source, root_match.start())
    if tag_end < 0 or tag_end >= _XML_HEADER_BYTES:
        return None
    root_tag = source[root_match.start() : tag_end]
    if b"xmlns:xsi" in root_tag:
        return None
    namespace = f' xmlns:xsi="{_CANONICAL_XSI_NAMESPACE}"'.encode()
    return source[:tag_end] + namespace + source[tag_end:]


def _root_kml_match(source: bytes) -> re.Match[bytes] | None:
    header = source[:_XML_HEADER_BYTES]
    start = 3 if header.startswith(b"\xef\xbb\xbf") else 0
    prolog = _XML_PROLOG_PATTERN.match(header[start:])
    assert prolog is not None
    return _ROOT_KML_PATTERN.match(header, start + prolog.end())


def _repair_duplicated_kml_namespace(source: bytes) -> bytes:
    """Repair one known exporter typo, never arbitrary XML or namespace URIs."""
    root_match = _root_kml_match(source)
    if root_match is None:
        return source
    tag_end = _find_xml_tag_end(source, root_match.start())
    if tag_end < 0:
        return source
    root_tag = source[root_match.start() : tag_end]
    # Match each attribute once. Searching again at every whitespace offset
    # makes a valid root with a long trailing whitespace run quadratic.
    attribute_start = root_match.end() - root_match.start() - 1
    while attribute := _XML_ATTRIBUTE_PATTERN.match(root_tag, attribute_start):
        attribute_start = attribute.end()
        name = attribute["name"]
        if name != b"xmlns" and not name.startswith(b"xmlns:"):
            continue
        value = attribute["value"]
        if not value.startswith((b"xmlns='", b'xmlns="')) or value[-1:] != value[6:7]:
            continue
        namespace = value[7:-1]
        if namespace.decode("ascii", errors="replace") not in _KML_NAMESPACES - {""}:
            continue
        # Pad after the attribute so original line/column locations stay valid.
        start = root_match.start() + attribute.start("value")
        end = root_match.start() + attribute.end()
        replacement = (
            namespace + attribute["quote"] + b" " * (len(value) - len(namespace))
        )
        return source[:start] + replacement + source[end:]
    return source


def _xml_error(
    source: bytes,
    position: tuple[int, int],
    message: str = "The KML document is not well-formed XML.",
) -> GISLayerProcessingError:
    line, column = position
    details: dict[str, Any] = {}
    if line > 0:
        details["line"] = line
        if column > 0:
            details["column"] = column
        details["source_line"] = _xml_source_line(source, line)
    return GISLayerProcessingError(
        ProcessingErrorCode.XML_INVALID, message, details=details
    )


def _xml_source_line(source: bytes, line: int) -> str:
    """Read only as far as the diagnostic, with bounded memory even for one-line XML."""
    encoding = "utf-8-sig"
    if source.startswith((b"\xff\xfe\x00\x00", b"\x00\x00\xfe\xff")):
        encoding = "utf-32"
    elif source.startswith((b"\xff\xfe", b"\xfe\xff")):
        encoding = "utf-16"
    elif source.startswith(b"\x00\x00\x00<"):
        encoding = "utf-32-be"
    elif source.startswith(b"<\x00\x00\x00"):
        encoding = "utf-32-le"
    elif source.startswith(b"\x00<"):
        encoding = "utf-16-be"
    elif source.startswith(b"<\x00"):
        encoding = "utf-16-le"
    else:
        declaration = re.match(
            rb"<\?xml\s[^?]*encoding\s*=\s*['\"]([\w.-]+)['\"]", source[:256]
        )
        if declaration is not None:
            encoding = declaration[1].decode("ascii")
    try:
        reader = io.TextIOWrapper(
            io.BytesIO(source), encoding=encoding, errors="replace"
        )
    except LookupError:
        return ""
    try:
        with reader:
            current_line = 1
            while current_line < line:
                chunk = reader.readline(4096)
                if not chunk:
                    return ""
                current_line += chunk.endswith("\n")
            excerpt = reader.readline(_XML_ERROR_LINE_CHARS + 1).rstrip("\r\n")
    except UnicodeError:
        # A lying encoding declaration must not turn an XML rejection into a 500.
        return ""
    if len(excerpt) > _XML_ERROR_LINE_CHARS:
        return excerpt[: _XML_ERROR_LINE_CHARS - 1] + "…"
    return excerpt


def _find_xml_tag_end(source: bytes, start: int) -> int:
    quote: int | None = None
    for index in range(start, min(len(source), _XML_HEADER_BYTES)):
        character = source[index]
        if quote is None and character in {ord('"'), ord("'")}:
            quote = character
        elif quote == character:
            quote = None
        elif quote is None and character == ord(">"):
            return index
    return -1


def _scan_document(source: bytes, *, diagnostic_source: bytes) -> _ScanResult:
    scan = _ScanResult()
    depth = 0
    protected_depth: int | None = None
    root_name: str | None = None
    root_namespace: str | None = None
    unsupported_depth: int | None = None
    context = etree.iterparse(
        io.BytesIO(source),
        events=("start", "end"),
        resolve_entities=False,
        no_network=True,
        huge_tree=True,
    )
    for event, element in context:
        # libxml can record namespace errors but postpone raising until EOF.
        # Inspect the current chunk before doing any Python feature processing.
        error = context.error_log.last_error
        if error is not None and error.level >= etree.ErrorLevels.ERROR:
            raise etree.XMLSyntaxError(
                error.message, error.type, error.line, error.column
            )
        local_name = _local_name(element)
        if event == "start":
            depth += 1
            if depth > limits.MAX_XML_DEPTH:
                raise GISLayerProcessingError(
                    ProcessingErrorCode.XML_DEPTH_LIMIT,
                    "The KML document is nested too deeply.",
                    details={"limit": limits.MAX_XML_DEPTH},
                )
            if _is_kml(element, "Placemark") and _is_document_feature(element):
                scan.source_placemarks += 1
                if scan.source_placemarks > limits.MAX_KML_PLACEMARKS:
                    raise GISLayerProcessingError(
                        ProcessingErrorCode.KML_FEATURE_LIMIT,
                        "The KML document contains too many placemarks.",
                        details={"limit": limits.MAX_KML_PLACEMARKS},
                    )
            if unsupported_depth is None:
                if local_name in _UNSUPPORTED_CONSTRUCTS and (
                    _is_kml(element) or _namespace(element) == _GX_NAMESPACE
                ):
                    scan.warnings[local_name] += 1
                    unsupported_depth = depth
                elif _is_kml(element) and local_name in {"TimeStamp", "TimeSpan"}:
                    scan.warnings["Time"] += 1
                elif _is_kml(element, "Icon"):
                    scan.warnings["Icon"] += 1
                elif (
                    _is_kml(element, "LinearRing")
                    and element.getparent() is not None
                    and _local_name(element.getparent())
                    in {"Placemark", "MultiGeometry"}
                ):
                    scan.warnings["LinearRing"] += 1
                elif _is_unrecognized_feature_child(element):
                    scan.warnings["UnsupportedExtension"] += 1
                    unsupported_depth = depth
            if root_name is None:
                root_name = local_name
                root_namespace = _namespace(element)
                if root_name != "kml" or root_namespace not in _KML_NAMESPACES:
                    raise _xml_error(
                        diagnostic_source,
                        (element.sourceline or 1, 0),
                        "The XML source is not a KML document.",
                    )
            source_id = element.get("id")
            if (
                source_id
                and _is_kml(element)
                and _is_document_feature(element)
                and local_name
                in {
                    "Document",
                    "Folder",
                }
            ):
                scan.hierarchy_ids[source_id] += 1
            if (
                protected_depth is None
                and _is_kml(element)
                and local_name in {"Style", "StyleMap"}
            ):
                protected_depth = depth
            continue

        if _is_kml(element, "coordinates"):
            for _ in re.finditer(r"\S+", element.text or ""):
                scan.coordinate_count += 1
                if scan.coordinate_count > limits.MAX_KML_COORDINATES:
                    raise GISLayerProcessingError(
                        ProcessingErrorCode.KML_COORDINATE_LIMIT,
                        "The KML document contains too many coordinate positions.",
                        details={"limit": limits.MAX_KML_COORDINATES},
                    )
        elif _is_kml(element, "styleUrl"):
            style_url = (element.text or "").strip()
            if style_url and not style_url.startswith("#"):
                scan.warnings["ExternalStyle"] += 1
        elif (
            unsupported_depth is None
            and _is_kml(element, "visibility")
            and (element.text or "").strip() == "0"
            and element.getparent() is not None
            and _is_document_feature(element.getparent())
        ):
            scan.warnings["HIDDEN_ITEMS_INCLUDED"] += 1
        if unsupported_depth == depth:
            unsupported_depth = None
        if protected_depth == depth:
            if unsupported_depth is None:
                scan.warnings["LAYER_APPEARANCE"] += sum(
                    1
                    for child in element.iter()
                    if _is_kml(child, "Style") and _parse_style(child)
                )
            source_id = element.get("id")
            if source_id and _is_kml(element, "Style"):
                scan.styles[source_id] = _parse_style(element)
            elif source_id and _is_kml(element, "StyleMap"):
                normal_style = _normal_style_url(element)
                if normal_style:
                    scan.style_maps[source_id] = normal_style
            protected_depth = None
        if protected_depth is None:
            _clear_element(element)
        depth -= 1

    return scan


def _compile_features(
    source: bytes,
    scan: _ScanResult,
) -> _FeatureAnalysis:
    result = _FeatureAnalysis()
    contexts: list[_FolderContext] = []
    depth = 0
    placemark_depth: int | None = None
    source_placemarks = 0
    hierarchy_index = 0
    context = etree.iterparse(
        io.BytesIO(source),
        events=("start", "end"),
        resolve_entities=False,
        no_network=True,
        huge_tree=True,
    )
    for event, element in context:
        local_name = _local_name(element)
        is_kml_element = _is_kml(element)
        if event == "start":
            depth += 1
            if (
                placemark_depth is None
                and is_kml_element
                and local_name in {"Document", "Folder"}
                and _is_document_feature(element)
            ):
                hierarchy_index += 1
                source_id = element.get("id")
                contexts.append(
                    _FolderContext(
                        kind=local_name,
                        stable_id=(
                            _stable_kml_id(
                                "kml-node-id",
                                source_id,
                                hierarchy_index,
                                scan.hierarchy_ids[source_id],
                            )
                            if source_id
                            else f"kml-node-pos:{hierarchy_index:08d}"
                        ),
                    )
                )
            if (
                is_kml_element
                and local_name == "Placemark"
                and _is_document_feature(element)
            ):
                if placemark_depth is not None:
                    raise GISLayerProcessingError(
                        ProcessingErrorCode.XML_INVALID,
                        "Placemarks cannot contain other placemarks.",
                    )
                placemark_depth = depth
            continue

        if (
            local_name == "name"
            and is_kml_element
            and placemark_depth is None
            and contexts
            and element.getparent() is not None
            and _local_name(element.getparent()) == contexts[-1].kind
            and _is_document_feature(element.getparent())
        ):
            contexts[-1].name = _plain_text(element.text or "")
        if (
            local_name == "visibility"
            and is_kml_element
            and placemark_depth is None
            and contexts
            and element.getparent() is not None
            and _local_name(element.getparent()) == contexts[-1].kind
            and _is_document_feature(element.getparent())
        ):
            contexts[-1].visibility = (element.text or "").strip() != "0"

        if is_kml_element and local_name == "Placemark" and placemark_depth == depth:
            source_placemarks += 1
            feature = _compile_placemark(
                element,
                source_placemarks,
                tuple(contexts),
                scan,
            )
            if feature is not None:
                result.features.append(feature)
                _analyze_placemark(element, feature, result)
            placemark_depth = None
            _clear_element(element)
        elif (
            is_kml_element
            and local_name in {"Document", "Folder"}
            and placemark_depth is None
            and _is_document_feature(element)
        ):
            contexts.pop()
            _clear_element(element)
        elif placemark_depth is None:
            _clear_element(element)
        depth -= 1
    return result


def _is_document_feature(element: etree._Element) -> bool:
    """Only container children are features; metadata and updates are payloads."""
    for parent in element.iterancestors():
        if not _is_kml(parent):
            return False
        name = _local_name(parent)
        if name == "kml":
            return parent.getparent() is None
        if name not in {"Document", "Folder"}:
            return False
    return False


def _analyze_placemark(
    element: etree._Element, feature: dict[str, Any], result: _FeatureAnalysis
) -> None:
    geometry = feature["geometry"]
    geometries = geometry.get("geometries", [geometry])
    for part in geometries:
        kind = part["type"]
        if kind.startswith("Multi"):
            result.parts[kind.removeprefix("Multi")] += len(part["coordinates"])
        else:
            result.parts[kind] += 1
    metadata = feature["properties"].get("kml_geometry_metadata", {})
    if (
        any(
            position[2:] and position[2] != 0
            for position in iter_coordinate_positions(geometry)
        )
        or "1" in metadata.get("extrude", [])
        or any(mode != "clampToGround" for mode in metadata.get("altitude_mode", []))
    ):
        result.three_dimensional += 1
    if not _point_only_placemark(element):
        return
    result.eligible_placemarks += 1
    properties = feature["properties"]
    name = properties["name"]
    if len(name) > limits.LANDMARK_NAME_MAX_LENGTH:
        result.shortened_names += 1
    for position in iter_coordinate_positions(geometry):
        result.candidates.append(
            LandmarkCandidate(
                name=name[: limits.LANDMARK_NAME_MAX_LENGTH],
                description=properties.get("description", ""),
                longitude=position[0],
                latitude=position[1],
            )
        )


def _point_only_placemark(element: etree._Element) -> bool:
    geometry_roots: list[etree._Element] = []
    for child in element:
        if not isinstance(child.tag, str):
            continue
        local_name = _local_name(child)
        if _is_kml(child) and local_name in _FEATURE_PROPERTIES:
            continue
        if _namespace(child) in _METADATA_NAMESPACES:
            continue
        if _namespace(child) == _GX_NAMESPACE and local_name in _GX_FEATURE_PROPERTIES:
            continue
        geometry_roots.append(child)
    return bool(geometry_roots) and all(
        _point_only_geometry(child) for child in geometry_roots
    )


def _is_unrecognized_feature_child(element: etree._Element) -> bool:
    parent = element.getparent()
    if parent is None or not _is_kml(parent):
        return False
    parent_name = _local_name(parent)
    if parent_name not in {"Placemark", "MultiGeometry"}:
        return False
    name = _local_name(element)
    if _is_kml(element) and name in _GEOMETRY_NAMES | {"LinearRing", "Model"}:
        return False
    if _namespace(element) == _GX_NAMESPACE and name in {"Track", "MultiTrack"}:
        return False
    if parent_name == "Placemark":
        if _is_kml(element) and name in _FEATURE_PROPERTIES:
            return False
        if _namespace(element) in _METADATA_NAMESPACES:
            return False
        if _namespace(element) == _GX_NAMESPACE and name in _GX_FEATURE_PROPERTIES:
            return False
    return True


def _point_only_geometry(element: etree._Element) -> bool:
    if _is_kml(element, "Point"):
        return True
    if not _is_kml(element, "MultiGeometry"):
        return False
    children = [child for child in element if isinstance(child.tag, str)]
    return bool(children) and all(_point_only_geometry(child) for child in children)


def _compile_placemark(
    element: etree._Element,
    index: int,
    contexts: tuple[_FolderContext, ...],
    scan: _ScanResult,
) -> dict[str, Any] | None:
    source_id = element.get("id")
    stable_id = f"kml-feature:{index:08d}"
    geometry_elements = [
        child
        for child in element
        if _is_kml(child) and _local_name(child) in _GEOMETRY_NAMES
    ]
    geometries: list[dict[str, Any]] = []
    for geometry_element in geometry_elements:
        geometries.extend(_compile_geometry(geometry_element, stable_id))

    if not geometries:
        return None
    geometry = _combine_geometries(geometries)

    name = _direct_text(element, "name")
    description = _direct_text(element, "description")
    source_visibility = _direct_text(element, "visibility").strip() != "0"
    properties: dict[str, Any] = {
        "name": _plain_text(name),
        "folder_path": [context.name for context in contexts if context.name],
        "folder_ids": [context.stable_id for context in contexts],
        "source_visibility": source_visibility,
        "initial_visibility": source_visibility
        and all(context.visibility for context in contexts),
    }
    if description:
        properties["description"] = _plain_text(description)
    extended_data = _extended_data(element)
    if extended_data:
        properties["extended_data"] = extended_data
    geometry_metadata = _geometry_metadata(element)
    if geometry_metadata:
        properties["kml_geometry_metadata"] = geometry_metadata

    style = _resolved_style(element, scan)
    if style:
        properties.update(_render_properties(properties["name"], style))
    elif properties["name"]:
        properties["render_label"] = properties["name"]
    feature = {
        "type": "Feature",
        "id": stable_id,
        "geometry": geometry,
        "properties": properties,
    }
    if source_id:
        feature["source_id"] = source_id
    return feature


def _compile_geometry(
    element: etree._Element,
    feature_id: str,
) -> list[dict[str, Any]]:
    local_name = _local_name(element)
    if local_name == "MultiGeometry":
        geometries: list[dict[str, Any]] = []
        for child in element:
            if _is_kml(child) and _local_name(child) in _GEOMETRY_NAMES:
                geometries.extend(_compile_geometry(child, feature_id))
        return geometries
    if local_name == "Point":
        coordinates = _coordinate_text(element, feature_id)
        positions = _parse_kml_coordinates(coordinates, feature_id)
        if len(positions) != 1:
            raise _invalid_kml_geometry(feature_id, "Point must have one position")
        return [{"type": "Point", "coordinates": positions[0]}]
    if local_name == "LineString":
        coordinates = _coordinate_text(element, feature_id)
        positions = _parse_kml_coordinates(coordinates, feature_id)
        try:
            MinLengthValidator(2)(positions)
        except ValidationError as exc:
            raise _invalid_kml_geometry(
                feature_id,
                "LineString is too short",
            ) from exc
        return [{"type": "LineString", "coordinates": positions}]
    if local_name == "Polygon":
        outer_boundaries = _boundary_rings(element, "outerBoundaryIs")
        if len(outer_boundaries) != 1:
            raise _invalid_kml_geometry(
                feature_id,
                "Polygon must have exactly one outer boundary",
            )
        outer_ring = _parse_ring(outer_boundaries[0], feature_id)
        inner_rings = [
            _parse_ring(ring, feature_id)
            for ring in _boundary_rings(element, "innerBoundaryIs")
        ]
        return [{"type": "Polygon", "coordinates": [outer_ring, *inner_rings]}]
    return []


def _boundary_rings(
    polygon: etree._Element,
    boundary_name: str,
) -> list[etree._Element]:
    rings: list[etree._Element] = []
    for boundary in polygon:
        if not _is_kml(boundary, boundary_name):
            continue
        rings.extend(
            descendant
            for descendant in boundary.iter()
            if _is_kml(descendant, "LinearRing")
        )
    return rings


def _parse_ring(
    ring: etree._Element,
    feature_id: str,
) -> list[list[float]]:
    positions = _parse_kml_coordinates(
        _coordinate_text(ring, feature_id),
        feature_id,
    )
    try:
        MinLengthValidator(4)(positions)
    except ValidationError as exc:
        raise _invalid_kml_geometry(
            feature_id,
            "LinearRing must be closed and contain at least four positions",
        ) from exc
    if positions[0] != positions[-1]:
        raise _invalid_kml_geometry(feature_id, "LinearRing must be closed")
    return positions


def _coordinate_text(element: etree._Element, feature_id: str) -> str:
    for descendant in element.iter():
        if _is_kml(descendant, "coordinates") and descendant.text:
            return str(descendant.text)
    raise _invalid_kml_geometry(feature_id, "Geometry has no coordinates")


def _parse_kml_coordinates(
    value: str,
    feature_id: str,
) -> list[list[float]]:
    positions: list[list[float]] = []
    for match in re.finditer(r"\S+", value):
        token = match.group()
        components = token.split(",")
        try:
            position = [float(component) for component in components]
        except ValueError as exc:
            raise _invalid_kml_geometry(
                feature_id,
                "Non-numeric coordinate tuple",
            ) from exc
        try:
            positions.append(
                validate_position(position, context=f"KML feature {feature_id}")
            )
        except GISLayerProcessingError as exc:
            raise _invalid_kml_geometry(feature_id, exc.user_message) from exc
    return positions


def _combine_geometries(geometries: list[dict[str, Any]]) -> dict[str, Any]:
    if len(geometries) == 1:
        return geometries[0]
    geometry_types = {geometry["type"] for geometry in geometries}
    multi_names = {
        "Point": "MultiPoint",
        "LineString": "MultiLineString",
        "Polygon": "MultiPolygon",
    }
    if len(geometry_types) == 1:
        geometry_type = str(geometries[0]["type"])
        return {
            "type": multi_names[geometry_type],
            "coordinates": [geometry["coordinates"] for geometry in geometries],
        }
    return {"type": "GeometryCollection", "geometries": geometries}


def _parse_style(element: etree._Element) -> dict[str, Any]:
    style: dict[str, Any] = {}
    for component in element:
        component_name = _local_name(component)
        if not _is_kml(component) or component_name not in {
            "IconStyle",
            "LabelStyle",
            "LineStyle",
            "PolyStyle",
        }:
            continue
        values: dict[str, Any] = {}
        for child in component.iterchildren():
            if not _is_kml(child):
                continue
            child_name = _local_name(child)
            text = (child.text or "").strip()
            if child_name == "color" and text:
                converted_color = _kml_color(text)
                if converted_color:
                    values["color"] = converted_color
            elif child_name in {"scale", "width"}:
                try:
                    number = float(text)
                except ValueError:
                    continue
                if math.isfinite(number):
                    values[child_name] = number
            elif child_name in {"fill", "outline"}:
                values[child_name] = text != "0"
            elif child_name == "Icon":
                href = _descendant_text(child, "href")
                if href and not href.lower().startswith(("http:", "https:")):
                    values["icon_href"] = href
        if values:
            style[component_name] = values
    return style


def _resolved_style(
    placemark: etree._Element,
    scan: _ScanResult,
) -> dict[str, Any]:
    resolved: dict[str, Any] = {}
    style_url = _direct_text(placemark, "styleUrl").lstrip("#")
    if style_url:
        style_url = scan.style_maps.get(style_url, style_url).lstrip("#")
        resolved.update(scan.styles.get(style_url, {}))
    for child in placemark:
        if _is_kml(child, "Style"):
            resolved.update(_parse_style(child))
    return resolved


def _normal_style_url(style_map: etree._Element) -> str:
    for pair in style_map:
        if not _is_kml(pair, "Pair"):
            continue
        if _direct_text(pair, "key") == "normal":
            return _direct_text(pair, "styleUrl")
    return ""


def _kml_color(value: str) -> str | None:
    normalized = value.strip().lower()
    if not re.fullmatch(r"[0-9a-f]{8}", normalized):
        return None
    alpha, blue, green, red = (
        normalized[0:2],
        normalized[2:4],
        normalized[4:6],
        normalized[6:8],
    )
    return f"#{red}{green}{blue}{alpha}"


def _extended_data(placemark: etree._Element) -> dict[str, str]:
    values: dict[str, str] = {}
    for descendant in placemark.iter():
        if _is_kml(descendant, "Data"):
            name = descendant.get("name")
            if name:
                values[_plain_text(name)] = _plain_text(
                    _descendant_text(descendant, "value")
                )
        elif _is_kml(descendant, "SimpleData"):
            name = descendant.get("name")
            if name:
                values[_plain_text(name)] = _plain_text(descendant.text or "")
    return dict(sorted(values.items()))


def _render_properties(name: str, style: dict[str, Any]) -> dict[str, Any]:
    rendered: dict[str, Any] = {}
    color: str | None = None
    for component_name in ("PolyStyle", "LineStyle", "IconStyle", "LabelStyle"):
        component = style.get(component_name, {})
        if component.get("color"):
            color = str(component["color"])
            break
    if color:
        rendered["render_color"] = color[:7]
    poly_style = style.get("PolyStyle", {})
    if poly_style:
        alpha = int(str(poly_style.get("color", "#000000ff"))[7:9], 16) / 255
        rendered["render_fill_opacity"] = (
            round(alpha, 6) if poly_style.get("fill", True) else 0.0
        )
        if not poly_style.get("outline", True):
            rendered["render_outline_opacity"] = 0.0
    line_style = style.get("LineStyle", {})
    if "width" in line_style:
        rendered["render_line_width"] = max(0.0, min(float(line_style["width"]), 20.0))
    if name:
        rendered["render_label"] = name
    return rendered


def _geometry_metadata(placemark: etree._Element) -> dict[str, list[str]]:
    values: dict[str, set[str]] = {
        "altitude_mode": set(),
        "extrude": set(),
        "tessellate": set(),
    }
    names = {
        "altitudeMode": "altitude_mode",
        "extrude": "extrude",
        "tessellate": "tessellate",
    }
    for descendant in placemark.iter():
        key = names.get(_local_name(descendant))
        if key and _is_kml(descendant) and descendant.text:
            values[key].add(_plain_text(descendant.text))
    return {key: sorted(items) for key, items in values.items() if items}


def _plain_text(value: str) -> str:
    return sanitize_field_name(value)


def _direct_text(element: etree._Element, child_name: str) -> str:
    for child in element:
        if _is_kml(child, child_name):
            return child.text or ""
    return ""


def _descendant_text(element: etree._Element, child_name: str) -> str:
    for descendant in element.iter():
        if _is_kml(descendant, child_name):
            return descendant.text or ""
    return ""


def _local_name(element: etree._Element) -> str:
    if not isinstance(element.tag, str):
        return ""
    return str(etree.QName(element.tag).localname)


def _namespace(element: etree._Element) -> str:
    if not isinstance(element.tag, str):
        return ""
    return etree.QName(element.tag).namespace or ""


def _is_kml(element: etree._Element, local_name: str | None = None) -> bool:
    if not isinstance(element.tag, str):
        return False
    if _namespace(element) not in _KML_NAMESPACES:
        return False
    return local_name is None or _local_name(element) == local_name


def _clear_element(element: etree._Element) -> None:
    element.clear()
    parent = element.getparent()
    if parent is not None:
        while element.getprevious() is not None:
            del parent[0]


def _invalid_kml_geometry(feature_id: str, reason: str) -> GISLayerProcessingError:
    return GISLayerProcessingError(
        ProcessingErrorCode.KML_INVALID_GEOMETRY,
        "The KML document contains invalid geometry.",
        details={"feature_id": feature_id, "reason": reason},
    )


def _stable_kml_id(
    prefix: str,
    source_id: str,
    position: int,
    occurrence_count: int,
) -> str:
    base = f"{prefix}:{source_id}"
    if occurrence_count <= 1:
        return base
    return f"{base}:pos:{position:08d}"


class KMLProcessor(BaseGISLayerProcessor):
    source_format = GISLayerSourceFormat.KML

    def process(self, source: bytes) -> CompilationResult:
        analysis = _require_overlay(analyze_kml(source))
        return CompilationResult(display_geojson=analysis.display_geojson)

    def build_feature_collection(
        self,
        source: bytes,
    ) -> dict[str, Any]:
        return compile_kml(source)
