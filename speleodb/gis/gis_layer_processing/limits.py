"""Central resource budgets for server-side KML/KMZ ingestion."""

from __future__ import annotations

from typing import IO

from django.conf import settings

from speleodb.gis.gis_layer_processing.errors import GISLayerProcessingError
from speleodb.gis.gis_layer_processing.errors import ProcessingErrorCode

MAX_KMZ_MEMBERS = 10_000
MAX_XML_DEPTH = 128
MAX_KML_PLACEMARKS = 100_000
MAX_KML_COORDINATES = 2_000_000
LANDMARK_NAME_MAX_LENGTH = 100
READ_CHUNK_BYTES = 1024 * 1024


def source_bytes_limit() -> int:
    return int(settings.DJANGO_UPLOAD_INDIVIDUAL_FILESIZE_MB_LIMIT) * 1024 * 1024


def check_source_size(size: int) -> None:
    if size > source_bytes_limit():
        raise GISLayerProcessingError(
            ProcessingErrorCode.SOURCE_TOO_LARGE,
            "The uploaded file or expanded KML exceeds the import size limit.",
            details={"limit_bytes": source_bytes_limit()},
        )


def read_bounded_source(source: IO[bytes]) -> bytes:
    """Bound actual streamed bytes, including a KMZ member's expansion."""
    chunks: list[bytes] = []
    total = 0
    while chunk := source.read(min(READ_CHUNK_BYTES, source_bytes_limit() - total + 1)):
        total += len(chunk)
        check_source_size(total)
        chunks.append(chunk)
    return b"".join(chunks)
