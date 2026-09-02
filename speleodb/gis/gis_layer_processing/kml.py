# -*- coding: utf-8 -*-

from __future__ import annotations

import html
import io
import math
import re
from collections import Counter
from dataclasses import dataclass
from dataclasses import field
from typing import Any

import nh3
from django.core.exceptions import ValidationError
from django.core.validators import MinLengthValidator
from lxml import etree  # type: ignore[attr-defined]

from speleodb.gis.gis_layer_processing.base import BaseGISLayerProcessor
from speleodb.gis.gis_layer_processing.common import calculate_bbox
from speleodb.gis.gis_layer_processing.common import explode_geometry_collections
from speleodb.gis.gis_layer_processing.common import iter_coordinate_positions
from speleodb.gis.gis_layer_processing.common import validate_position
from speleodb.gis.gis_layer_processing.errors import GISLayerProcessingError
from speleodb.gis.gis_layer_processing.errors import ProcessingErrorCode
from speleodb.gis.models.gis_layer import GISLayerSourceFormat

_CANONICAL_XSI_NAMESPACE = "http://www.w3.org/2001/XMLSchema-instance"
_KML_NAMESPACES = {
    "",
    "http://earth.google.com/kml/2.0",
    "http://earth.google.com/kml/2.1",
    "http://www.opengis.net/kml/2.2",
}
_ROOT_KML_PATTERN = re.compile(rb"<(?:[A-Za-z_][\w.-]*:)?kml(?:\s|>)")
_GEOMETRY_NAMES = {"Point", "LineString", "Polygon", "MultiGeometry"}


@dataclass(slots=True)
class _ScanResult:
    styles: dict[str, dict[str, Any]] = field(default_factory=dict)
    style_maps: dict[str, str] = field(default_factory=dict)
    hierarchy_ids: Counter[str] = field(default_factory=Counter)


@dataclass(slots=True)
class _FolderContext:
    kind: str
    stable_id: str
    name: str = ""
    visibility: bool = True


def compile_kml(source: bytes) -> dict[str, Any]:
    _reject_unsafe_xml(source)

    parse_source = source
    try:
        scan = _scan_document(parse_source)
    except etree.XMLSyntaxError as strict_error:
        repaired = _repair_missing_xsi_namespace(parse_source)
        if repaired is None:
            raise GISLayerProcessingError(
                ProcessingErrorCode.XML_INVALID,
                "The KML document is not well-formed XML.",
            ) from strict_error
        try:
            scan = _scan_document(repaired)
        except etree.XMLSyntaxError as repaired_error:
            raise GISLayerProcessingError(
                ProcessingErrorCode.XML_INVALID,
                "The KML document is not well-formed XML.",
            ) from repaired_error
        parse_source = repaired

    features = _compile_features(parse_source, scan)
    features = explode_geometry_collections(features)
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
    return feature_collection


def _reject_unsafe_xml(source: bytes) -> None:
    upper_source = source.upper()
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
    root_match = _ROOT_KML_PATTERN.search(source[: 64 * 1024])
    if root_match is None:
        return None
    tag_end = _find_xml_tag_end(source, root_match.start())
    if tag_end < 0 or tag_end >= 64 * 1024:
        return None
    root_tag = source[root_match.start() : tag_end]
    if b"xmlns:xsi" in root_tag:
        return None
    namespace = f' xmlns:xsi="{_CANONICAL_XSI_NAMESPACE}"'.encode()
    return source[:tag_end] + namespace + source[tag_end:]


def _find_xml_tag_end(source: bytes, start: int) -> int:
    quote: int | None = None
    for index in range(start, min(len(source), 64 * 1024)):
        character = source[index]
        if quote is None and character in {ord('"'), ord("'")}:
            quote = character
        elif quote == character:
            quote = None
        elif quote is None and character == ord(">"):
            return index
    return -1


def _scan_document(source: bytes) -> _ScanResult:
    scan = _ScanResult()
    depth = 0
    protected_depth: int | None = None
    root_name: str | None = None
    root_namespace: str | None = None
    context = etree.iterparse(
        io.BytesIO(source),
        events=("start", "end"),
        resolve_entities=False,
        no_network=True,
        huge_tree=True,
    )
    for event, element in context:
        local_name = _local_name(element)
        if event == "start":
            depth += 1
            if root_name is None:
                root_name = local_name
                root_namespace = _namespace(element)
            source_id = element.get("id")
            if (
                source_id
                and _is_kml(element)
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

        if protected_depth == depth:
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

    if root_name != "kml" or root_namespace not in _KML_NAMESPACES:
        raise GISLayerProcessingError(
            ProcessingErrorCode.XML_INVALID,
            "The XML source is not a KML document.",
        )
    return scan


def _compile_features(
    source: bytes,
    scan: _ScanResult,
) -> list[dict[str, Any]]:
    features: list[dict[str, Any]] = []
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
            if is_kml_element and local_name == "Placemark":
                placemark_depth = depth
            continue

        if (
            local_name == "name"
            and is_kml_element
            and placemark_depth is None
            and contexts
            and element.getparent() is not None
            and _local_name(element.getparent()) == contexts[-1].kind
        ):
            contexts[-1].name = _plain_text(element.text or "")
        if (
            local_name == "visibility"
            and is_kml_element
            and placemark_depth is None
            and contexts
            and element.getparent() is not None
            and _local_name(element.getparent()) == contexts[-1].kind
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
                features.append(feature)
            placemark_depth = None
            _clear_element(element)
        elif (
            is_kml_element
            and local_name in {"Document", "Folder"}
            and placemark_depth is None
        ):
            contexts.pop()
            _clear_element(element)
        elif placemark_depth is None:
            _clear_element(element)
        depth -= 1
    return features


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
    for token in value.split():
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
    return html.unescape(nh3.clean(value, tags=set(), attributes={})).strip()


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
    return str(etree.QName(element.tag).localname)


def _namespace(element: etree._Element) -> str:
    return etree.QName(element.tag).namespace or ""


def _is_kml(element: etree._Element, local_name: str | None = None) -> bool:
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

    def build_feature_collection(
        self,
        source: bytes,
    ) -> dict[str, Any]:
        return compile_kml(source)
