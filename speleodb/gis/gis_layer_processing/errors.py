# -*- coding: utf-8 -*-

from __future__ import annotations

from enum import StrEnum
from typing import Any


class ProcessingErrorCode(StrEnum):
    """Stable error codes safe to expose through the GIS Layer API."""

    FORMAT_UNSUPPORTED = "FORMAT_UNSUPPORTED"
    FORMAT_MISMATCH = "FORMAT_MISMATCH"
    JSON_INVALID = "JSON_INVALID"
    GEOJSON_INVALID = "GEOJSON_INVALID"
    ZIP_INVALID = "ZIP_INVALID"
    ZIP_UNSAFE_ENTRY = "ZIP_UNSAFE_ENTRY"
    ZIP_AMBIGUOUS_MAIN_KML = "ZIP_AMBIGUOUS_MAIN_KML"
    XML_INVALID = "XML_INVALID"
    XML_UNSAFE = "XML_UNSAFE"
    KML_INVALID_GEOMETRY = "KML_INVALID_GEOMETRY"
    TOPOJSON_INVALID = "TOPOJSON_INVALID"
    SHAPEFILE_INVALID = "SHAPEFILE_INVALID"
    SHAPEFILE_CRS_INVALID = "SHAPEFILE_CRS_INVALID"


class GISLayerProcessingError(ValueError):
    """Expected ingestion failure with a stable public code and safe message."""

    def __init__(
        self,
        code: ProcessingErrorCode,
        user_message: str,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(user_message)
        self.code = code
        self.user_message = user_message
        self.details = details or {}
