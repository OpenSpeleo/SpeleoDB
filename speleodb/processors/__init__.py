# -*- coding: utf-8 -*-

from __future__ import annotations

# ruff: noqa: I001

# Top Level Imports are necessary to allow auto discovery using __subclasses__()

from speleodb.processors.base import BaseFileProcessor
from speleodb.processors.auto_selector import AutoSelector

# Download as ZIP Processor
from speleodb.processors._impl.dump import DumpProcessor

# Survey File Processors
from speleodb.processors._impl.ariane import ArianeAGRFileProcessor
from speleodb.processors._impl.ariane import ArianeTMLFileProcessor
from speleodb.processors._impl.ariane import ArianeTMLUFileProcessor
from speleodb.processors._impl.compass import CompassZIPFileProcessor
from speleodb.processors._impl.compass import CompassManualFileProcessor

# Generic File Formats
from speleodb.processors._impl.database import DatabaseFileProcessor
from speleodb.processors._impl.geodata import GeoDataFileProcessor
from speleodb.processors._impl.image import ImageFileProcessor
from speleodb.processors._impl.spreadsheet import SpreadsheetFileProcessor
from speleodb.processors._impl.text import TextFileProcessor

__all__ = [
    "ArianeAGRFileProcessor",
    "ArianeTMLFileProcessor",
    "ArianeTMLUFileProcessor",
    "AutoSelector",
    "BaseFileProcessor",
    "CompassManualFileProcessor",
    "CompassZIPFileProcessor",
    "DatabaseFileProcessor",
    "DumpProcessor",
    "GeoDataFileProcessor",
    "ImageFileProcessor",
    "SpreadsheetFileProcessor",
    "TextFileProcessor",
]
