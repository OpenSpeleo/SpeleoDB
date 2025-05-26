# ruff: noqa: F401, I001

# Top Level Imports are necessary to allow auto discovery using __subclasses__()

from speleodb.processors.base import BaseFileProcessor
from speleodb.processors.auto_selector import AutoSelector

# Download as ZIP Processor
from speleodb.processors._impl.dump import DumpProcessor

# Survey File Processors
from speleodb.processors._impl.ariane import AGRFileProcessor
from speleodb.processors._impl.ariane import TMLFileProcessor
from speleodb.processors._impl.ariane import TMLUFileProcessor
from speleodb.processors._impl.compass import DATFileProcessor
from speleodb.processors._impl.compass import MAKFileProcessor

# Generic File Formats
from speleodb.processors._impl.database import DatabaseFileProcessor
from speleodb.processors._impl.geodata import GeoDataFileProcessor
from speleodb.processors._impl.image import ImageFileProcessor
from speleodb.processors._impl.spreadsheet import SpreadsheetFileProcessor
from speleodb.processors._impl.text import TextFileProcessor

__all__ = [
    "AGRFileProcessor",
    "AutoSelector",
    "BaseFileProcessor",
    "DATFileProcessor",
    "DatabaseFileProcessor",
    "DumpProcessor",
    "GeoDataFileProcessor",
    "ImageFileProcessor",
    "MAKFileProcessor",
    "SpreadsheetFileProcessor",
    "TMLFileProcessor",
    "TMLUFileProcessor",
    "TextFileProcessor",
]
