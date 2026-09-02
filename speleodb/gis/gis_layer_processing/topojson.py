# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import Any

import orjson
from django.core.exceptions import ValidationError
from django.core.validators import MaxLengthValidator
from django.core.validators import MinLengthValidator

from speleodb.gis.gis_layer_processing.base import BaseGISLayerProcessor
from speleodb.gis.gis_layer_processing.common import validate_position
from speleodb.gis.gis_layer_processing.errors import GISLayerProcessingError
from speleodb.gis.gis_layer_processing.errors import ProcessingErrorCode
from speleodb.gis.models.gis_layer import GISLayerSourceFormat


class TopoJSONProcessor(BaseGISLayerProcessor):
    source_format = GISLayerSourceFormat.TOPOJSON

    def build_feature_collection(
        self,
        source: bytes,
    ) -> dict[str, Any]:
        try:
            topology = orjson.loads(source)
        except orjson.JSONDecodeError as exc:
            raise _invalid("The TopoJSON file is not valid JSON.") from exc
        if not isinstance(topology, dict) or topology.get("type") != "Topology":
            raise _invalid("The uploaded file is not a TopoJSON topology.")

        objects = topology.get("objects")
        arcs = topology.get("arcs")
        if not isinstance(objects, dict) or not isinstance(arcs, list):
            raise _invalid("The TopoJSON file must contain objects and arcs.")

        decoder = _TopologyDecoder(arcs, topology.get("transform"))
        features: list[dict[str, Any]] = []
        for object_name, geometry in objects.items():
            if not isinstance(object_name, str) or not isinstance(geometry, dict):
                raise _invalid("The TopoJSON objects collection is invalid.")
            features.extend(decoder.features(object_name, geometry))

        return {"type": "FeatureCollection", "features": features}


class _TopologyDecoder:
    def __init__(self, arcs: list[Any], transform: Any) -> None:
        self.scale, self.translate = self._parse_transform(transform)
        self.arcs = [self._decode_arc(arc, index) for index, arc in enumerate(arcs)]

    def features(
        self,
        object_name: str,
        geometry: dict[str, Any],
    ) -> list[dict[str, Any]]:
        return self._features(object_name, geometry, "0")

    def _features(
        self,
        object_name: str,
        geometry: dict[str, Any],
        position: str,
    ) -> list[dict[str, Any]]:
        if geometry.get("type") == "GeometryCollection":
            geometries = geometry.get("geometries")
            if not isinstance(geometries, list):
                raise _invalid("A TopoJSON GeometryCollection is invalid.")
            features: list[dict[str, Any]] = []
            for index, child in enumerate(geometries):
                if not isinstance(child, dict):
                    raise _invalid("A TopoJSON GeometryCollection is invalid.")
                features.extend(
                    self._features(object_name, child, f"{position}:{index}")
                )
            return features
        return [self._feature(object_name, geometry, position)]

    def _feature(
        self,
        object_name: str,
        geometry: dict[str, Any],
        position: str,
    ) -> dict[str, Any]:
        properties = geometry.get("properties", {})
        if not isinstance(properties, dict):
            raise _invalid("TopoJSON feature properties must be an object.")
        source_id = geometry.get("id")
        feature_id = (
            source_id
            if not isinstance(source_id, bool) and isinstance(source_id, str | int)
            else None
        )
        feature: dict[str, Any] = {
            "type": "Feature",
            "id": feature_id if feature_id is not None else f"{object_name}:{position}",
            "properties": dict(properties),
            "geometry": self._geometry(geometry),
        }
        return feature

    def _geometry(self, geometry: dict[str, Any]) -> dict[str, Any]:
        geometry_type = geometry.get("type")
        match geometry_type:
            case "Point":
                return {
                    "type": "Point",
                    "coordinates": self._point(geometry.get("coordinates")),
                }
            case "MultiPoint":
                coordinates = geometry.get("coordinates")
                if not isinstance(coordinates, list):
                    raise _invalid("A TopoJSON MultiPoint is invalid.")
                return {
                    "type": "MultiPoint",
                    "coordinates": [self._point(point) for point in coordinates],
                }
            case "LineString":
                return {
                    "type": "LineString",
                    "coordinates": self._line(geometry.get("arcs")),
                }
            case "MultiLineString":
                lines = geometry.get("arcs")
                if not isinstance(lines, list):
                    raise _invalid("A TopoJSON MultiLineString is invalid.")
                return {
                    "type": "MultiLineString",
                    "coordinates": [self._line(line) for line in lines],
                }
            case "Polygon":
                return {
                    "type": "Polygon",
                    "coordinates": self._polygon(geometry.get("arcs")),
                }
            case "MultiPolygon":
                polygons = geometry.get("arcs")
                if not isinstance(polygons, list):
                    raise _invalid("A TopoJSON MultiPolygon is invalid.")
                return {
                    "type": "MultiPolygon",
                    "coordinates": [self._polygon(polygon) for polygon in polygons],
                }
            case _:
                raise _invalid(
                    f"TopoJSON geometry type {geometry_type!r} is unsupported."
                )

    def _line(self, arc_indexes: Any) -> list[list[float]]:
        if not isinstance(arc_indexes, list) or not arc_indexes:
            raise _invalid("A TopoJSON line has no arcs.")
        line: list[list[float]] = []
        for raw_index in arc_indexes:
            if isinstance(raw_index, bool) or not isinstance(raw_index, int):
                raise _invalid("A TopoJSON arc reference is invalid.")
            arc_index = raw_index if raw_index >= 0 else ~raw_index
            if arc_index >= len(self.arcs):
                raise _invalid("A TopoJSON arc reference is out of range.")
            arc = self.arcs[arc_index]
            if raw_index < 0:
                arc = list(reversed(arc))
            line.extend(arc if not line else arc[1:])
        try:
            MinLengthValidator(2)(line)
        except ValidationError as exc:
            raise _invalid(
                "A TopoJSON line contains fewer than two positions."
            ) from exc
        return line

    def _polygon(self, rings: Any) -> list[list[list[float]]]:
        if not isinstance(rings, list) or not rings:
            raise _invalid("A TopoJSON polygon has no rings.")
        polygon = [self._line(ring) for ring in rings]
        for ring in polygon:
            try:
                MinLengthValidator(4)(ring)
            except ValidationError as exc:
                raise _invalid(
                    "A TopoJSON polygon contains an open or incomplete ring."
                ) from exc
            if ring[0] != ring[-1]:
                raise _invalid(
                    "A TopoJSON polygon contains an open or incomplete ring."
                )
        return polygon

    def _decode_arc(self, arc: Any, index: int) -> list[list[float]]:
        if not isinstance(arc, list):
            raise _invalid("The TopoJSON arcs collection is invalid.")
        decoded: list[list[float]] = []
        x = 0.0
        y = 0.0
        for position in arc:
            position_x, position_y = _xy(
                position,
                f"TopoJSON arc {index} contains an invalid position.",
            )
            if self.scale is None:
                x = position_x
                y = position_y
            else:
                x += position_x
                y += position_y
            decoded.append(self._transform(x, y))
        return decoded

    def _point(self, position: Any) -> list[float]:
        x, y = _xy(position, "A TopoJSON point is invalid.")
        return self._transform(x, y)

    def _transform(self, x: float, y: float) -> list[float]:
        if self.scale is None or self.translate is None:
            position = [x, y]
        else:
            position = [
                x * self.scale[0] + self.translate[0],
                y * self.scale[1] + self.translate[1],
            ]
        return validate_position(position, context="TopoJSON coordinate")

    @staticmethod
    def _parse_transform(
        transform: Any,
    ) -> tuple[list[float] | None, list[float] | None]:
        if transform is None:
            return None, None
        if not isinstance(transform, dict):
            raise _invalid("The TopoJSON transform is invalid.")
        scale = transform.get("scale")
        translate = transform.get("translate")
        if not isinstance(scale, list) or not isinstance(translate, list):
            raise _invalid("The TopoJSON transform is invalid.")
        try:
            MinLengthValidator(2)(scale)
            MaxLengthValidator(2)(scale)
            MinLengthValidator(2)(translate)
            MaxLengthValidator(2)(translate)
        except ValidationError as exc:
            raise _invalid("The TopoJSON transform is invalid.") from exc
        if any(
            isinstance(value, bool) or not isinstance(value, int | float)
            for value in [*scale, *translate]
        ):
            raise _invalid("The TopoJSON transform is invalid.")
        return [float(value) for value in scale], [float(value) for value in translate]


def _xy(position: Any, error_message: str) -> tuple[float, float]:
    if not isinstance(position, list):
        raise _invalid(error_message)
    try:
        MinLengthValidator(2)(position)
    except ValidationError as exc:
        raise _invalid(error_message) from exc
    x, y = position[:2]
    if (
        isinstance(x, bool)
        or isinstance(y, bool)
        or not isinstance(x, int | float)
        or not isinstance(y, int | float)
    ):
        raise _invalid(error_message)
    return float(x), float(y)


def _invalid(message: str) -> GISLayerProcessingError:
    return GISLayerProcessingError(ProcessingErrorCode.TOPOJSON_INVALID, message)
