# -*- coding: utf-8 -*-

from __future__ import annotations

import io
from pathlib import Path
from typing import TYPE_CHECKING

from speleodb.gis.gis_layer_processing.common import read_source
from speleodb.gis.gis_layer_processing.errors import GISLayerProcessingError
from speleodb.gis.gis_layer_processing.errors import ProcessingErrorCode
from speleodb.gis.gis_layer_processing.kml import KMLProcessor
from speleodb.gis.gis_layer_processing.kmz import KMZProcessor
from speleodb.gis.gis_layer_processing.shapefile import ShapefileProcessor
from speleodb.gis.gis_layer_processing.topojson import TopoJSONProcessor
from speleodb.gis.models.gis_layer import GISLayerSourceFormat

if TYPE_CHECKING:
    from typing import BinaryIO

    from speleodb.gis.gis_layer_processing.base import BaseGISLayerProcessor
    from speleodb.gis.gis_layer_processing.types import CompilationResult


def compile_gis_layer(
    file_obj: BinaryIO,
    *,
    filename: str,
    declared_format: GISLayerSourceFormat | str | None = None,
) -> CompilationResult:
    """Convert one supported non-GeoJSON source into renderable GeoJSON."""
    processor = processor_for_filename(filename)
    if declared_format is not None:
        try:
            declared = GISLayerSourceFormat(declared_format)
        except ValueError as exc:
            raise _unsupported_format() from exc
        if declared != processor.source_format:
            raise GISLayerProcessingError(
                ProcessingErrorCode.FORMAT_MISMATCH,
                "The selected file extension does not match its declared format.",
            )
    return processor.process(read_source(file_obj))


def compile_gis_layer_bytes(
    source: bytes,
    *,
    filename: str,
    declared_format: GISLayerSourceFormat | str | None = None,
) -> CompilationResult:
    return compile_gis_layer(
        io.BytesIO(source),
        filename=filename,
        declared_format=declared_format,
    )


def processor_for_filename(
    filename: str,
) -> BaseGISLayerProcessor:
    suffix = Path(filename).suffix.lower()
    match suffix:
        case ".kml":
            return KMLProcessor()
        case ".kmz":
            return KMZProcessor()
        case ".topojson":
            return TopoJSONProcessor()
        case ".zip":
            return ShapefileProcessor()
        case ".geojson" | ".json":
            raise GISLayerProcessingError(
                ProcessingErrorCode.FORMAT_UNSUPPORTED,
                "GeoJSON is uploaded directly and does not require conversion.",
            )
        case _:
            raise _unsupported_format()


def _unsupported_format() -> GISLayerProcessingError:
    return GISLayerProcessingError(
        ProcessingErrorCode.FORMAT_UNSUPPORTED,
        (
            "This file format is not supported. Upload GeoJSON, KML, KMZ, "
            "TopoJSON, or a Shapefile packaged as a ZIP."
        ),
    )
