"""Mode-independent inspection backed by the same KML compiler as publication."""

from __future__ import annotations

import contextlib
from pathlib import PurePosixPath
from typing import TYPE_CHECKING
from typing import BinaryIO

from speleodb.gis.gis_layer_processing.errors import GISLayerProcessingError
from speleodb.gis.gis_layer_processing.errors import ProcessingErrorCode
from speleodb.gis.gis_layer_processing.kml import analyze_kml
from speleodb.gis.gis_layer_processing.kmz import read_kmz_document
from speleodb.gis.gis_layer_processing.limits import read_bounded_source

if TYPE_CHECKING:
    from speleodb.gis.gis_layer_processing.types import KMLAnalysis


def analyze_kml_kmz(file_obj: BinaryIO, *, filename: str) -> KMLAnalysis:
    with contextlib.suppress(OSError, ValueError):
        file_obj.seek(0)
    try:
        return analyze_kml_kmz_bytes(read_bounded_source(file_obj), filename=filename)
    finally:
        with contextlib.suppress(OSError, ValueError):
            file_obj.seek(0)


def analyze_kml_kmz_bytes(source: bytes, *, filename: str) -> KMLAnalysis:
    match PurePosixPath(filename).suffix.lower():
        case ".kml":
            return analyze_kml(source)
        case ".kmz":
            document = read_kmz_document(source)
            return analyze_kml(document.source, warnings=document.warnings)
        case _:
            raise GISLayerProcessingError(
                ProcessingErrorCode.FORMAT_UNSUPPORTED,
                "Choose a KML or KMZ file.",
            )
