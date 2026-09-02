# -*- coding: utf-8 -*-

from __future__ import annotations

import io
import stat
import zipfile
from datetime import date
from datetime import datetime
from pathlib import PurePosixPath
from typing import Any

import shapefile
from django.core.exceptions import ValidationError
from django.core.validators import MinLengthValidator
from pyproj import CRS
from pyproj import Transformer
from pyproj.exceptions import CRSError
from pyproj.exceptions import ProjError

from speleodb.gis.gis_layer_processing.base import BaseGISLayerProcessor
from speleodb.gis.gis_layer_processing.common import validate_position
from speleodb.gis.gis_layer_processing.errors import GISLayerProcessingError
from speleodb.gis.gis_layer_processing.errors import ProcessingErrorCode
from speleodb.gis.models.gis_layer import GISLayerSourceFormat

_ALLOWED_COMPRESSION_METHODS = {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}
_REQUIRED_EXTENSIONS = {".shp", ".shx", ".dbf", ".prj"}


class ShapefileProcessor(BaseGISLayerProcessor):
    source_format = GISLayerSourceFormat.SHAPEFILE

    def build_feature_collection(
        self,
        source: bytes,
    ) -> dict[str, Any]:
        members = self._read_archive(source)
        dataset = self._select_dataset(members)
        encoding = self._encoding(members.get(f"{dataset}.cpg"))
        transformer = self._transformer(members[f"{dataset}.prj"])

        try:
            reader = shapefile.Reader(
                shp=io.BytesIO(members[f"{dataset}.shp"]),
                shx=io.BytesIO(members[f"{dataset}.shx"]),
                dbf=io.BytesIO(members[f"{dataset}.dbf"]),
                encoding=encoding,
            )
        except (OSError, UnicodeError, shapefile.ShapefileException) as exc:
            raise _invalid(
                "The ZIP does not contain a readable Shapefile dataset."
            ) from exc

        features: list[dict[str, Any]] = []
        try:
            for index, shape_record in enumerate(reader.iterShapeRecords()):
                shape = shape_record.shape
                record = shape_record.record
                if shape is None or record is None:
                    raise _invalid("The Shapefile contains an incomplete record.")
                if shape.shapeType == shapefile.NULL:
                    continue
                geometry = dict(shape.__geo_interface__)
                converted_geometry = self._transform_geometry(geometry, transformer)
                properties = {
                    str(key): _json_value(value)
                    for key, value in record.as_dict().items()
                }
                features.append(
                    {
                        "type": "Feature",
                        "id": f"shapefile:{index}",
                        "geometry": converted_geometry,
                        "properties": properties,
                    }
                )
        except GISLayerProcessingError:
            raise
        except (
            OSError,
            UnicodeError,
            ValueError,
            ProjError,
            shapefile.ShapefileException,
        ) as exc:
            raise _invalid(
                "The Shapefile contains invalid records or geometry."
            ) from exc
        finally:
            reader.close()

        return {"type": "FeatureCollection", "features": features}

    def _read_archive(self, source: bytes) -> dict[str, bytes]:
        try:
            archive = zipfile.ZipFile(io.BytesIO(source), mode="r")
        except (OSError, zipfile.BadZipFile) as exc:
            raise _invalid("The Shapefile upload is not a valid ZIP archive.") from exc

        members: dict[str, bytes] = {}
        with archive:
            entries = archive.infolist()
            if not entries:
                raise _invalid("The Shapefile ZIP archive is empty.")
            for entry in entries:
                if entry.is_dir():
                    continue
                name = _safe_member_name(entry)
                lower_name = name.casefold()
                if _is_archive_metadata(lower_name):
                    continue
                if lower_name.endswith((".zip", ".kmz")):
                    raise _invalid(
                        "Nested archives are not allowed in a Shapefile ZIP."
                    )
                if lower_name in members:
                    raise _invalid(
                        "The Shapefile ZIP contains duplicate or case-colliding paths."
                    )
                try:
                    payload = archive.read(entry)
                except (OSError, RuntimeError, zipfile.BadZipFile) as exc:
                    raise _invalid("A Shapefile ZIP member failed validation.") from exc
                if len(payload) != entry.file_size:
                    raise _invalid("A Shapefile ZIP member has an invalid size.")
                if payload.startswith((b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")):
                    raise _invalid(
                        "Nested archives are not allowed in a Shapefile ZIP."
                    )
                members[lower_name] = payload
        return members

    @staticmethod
    def _select_dataset(members: dict[str, bytes]) -> str:
        extensions_by_dataset: dict[str, set[str]] = {}
        for name in members:
            path = PurePosixPath(name)
            extensions_by_dataset.setdefault(
                path.with_suffix("").as_posix(),
                set(),
            ).add(path.suffix)
        candidates = [
            dataset
            for dataset, extensions in extensions_by_dataset.items()
            if extensions >= _REQUIRED_EXTENSIONS
        ]
        if not candidates:
            raise _invalid(
                "The ZIP must contain matching .shp, .shx, .dbf, and .prj files."
            )
        if len(candidates) > 1:
            raise _invalid("Upload one Shapefile dataset per ZIP archive.")
        return candidates[0]

    @staticmethod
    def _encoding(cpg: bytes | None) -> str:
        if cpg is None:
            return "utf-8"
        try:
            encoding = cpg.decode("utf-8-sig").strip()
        except UnicodeDecodeError as exc:
            raise _invalid(
                "The Shapefile .cpg encoding declaration is invalid."
            ) from exc
        if encoding.isdecimal():
            encoding = f"cp{encoding}"
        return encoding or "utf-8"

    @staticmethod
    def _transformer(prj: bytes) -> Transformer:
        try:
            source_crs = CRS.from_wkt(prj.decode("utf-8-sig"))
            return Transformer.from_crs(
                source_crs,
                CRS.from_epsg(4326),
                always_xy=True,
            )
        except (CRSError, UnicodeDecodeError, ValueError) as exc:
            raise GISLayerProcessingError(
                ProcessingErrorCode.SHAPEFILE_CRS_INVALID,
                "The Shapefile .prj coordinate system is invalid or unsupported.",
            ) from exc

    @classmethod
    def _transform_geometry(
        cls,
        geometry: dict[str, Any],
        transformer: Transformer,
    ) -> dict[str, Any]:
        geometry_type = geometry.get("type")
        if geometry_type not in {
            "Point",
            "MultiPoint",
            "LineString",
            "MultiLineString",
            "Polygon",
            "MultiPolygon",
        }:
            raise _invalid(f"Shapefile geometry type {geometry_type!r} is unsupported.")
        return {
            "type": geometry_type,
            "coordinates": cls._transform_coordinates(
                geometry.get("coordinates"),
                transformer,
            ),
        }

    @classmethod
    def _transform_coordinates(cls, value: Any, transformer: Transformer) -> Any:
        if (
            isinstance(value, tuple | list)
            and value
            and isinstance(value[0], int | float)
        ):
            try:
                MinLengthValidator(2)(value)
            except ValidationError as exc:
                raise _invalid("The Shapefile contains an invalid coordinate.") from exc
            longitude, latitude = transformer.transform(
                float(value[0]),
                float(value[1]),
                errcheck=True,
            )
            return validate_position(
                [longitude, latitude, *[float(item) for item in value[2:3]]],
                context="Shapefile coordinate",
            )
        if isinstance(value, tuple | list):
            return [cls._transform_coordinates(item, transformer) for item in value]
        raise _invalid("The Shapefile contains invalid coordinates.")


def _safe_member_name(entry: zipfile.ZipInfo) -> str:
    name = entry.filename
    if (
        not name
        or "\x00" in name
        or "\\" in name
        or name.startswith("/")
        or any(part in {"", ".", ".."} for part in name.split("/"))
    ):
        raise _invalid("The Shapefile ZIP contains an unsafe path.")
    unix_mode = entry.external_attr >> 16
    file_type = stat.S_IFMT(unix_mode)
    if file_type and not stat.S_ISREG(unix_mode):
        raise _invalid("The Shapefile ZIP contains an unsupported special entry.")
    if entry.flag_bits & 0x1 or entry.compress_type not in _ALLOWED_COMPRESSION_METHODS:
        raise _invalid("The Shapefile ZIP uses unsupported encryption or compression.")
    return PurePosixPath(name).as_posix()


def _is_archive_metadata(name: str) -> bool:
    path = PurePosixPath(name)
    return (
        "__macosx" in path.parts
        or path.name.startswith("._")
        or path.name == ".ds_store"
    )


def _json_value(value: Any) -> Any:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, date | datetime):
        return value.isoformat()
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _invalid(message: str) -> GISLayerProcessingError:
    return GISLayerProcessingError(ProcessingErrorCode.SHAPEFILE_INVALID, message)
