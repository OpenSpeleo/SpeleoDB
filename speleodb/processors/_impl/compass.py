from __future__ import annotations

from speleodb.processors.base import BaseFileProcessor
from speleodb.surveys.models import Format


class DATFileProcessor(BaseFileProcessor):
    ALLOWED_EXTENSIONS = [".dat"]
    ALLOWED_MIMETYPES = ["application/octet-stream", "text/plain"]
    ASSOC_FILEFORMAT = Format.FileFormat.COMPASS_DAT

    TARGET_FOLDER = None
    TARGET_SAVE_FILENAME = "project.dat"
    TARGET_DOWNLOAD_FILENAME = "{project_name}__{timestamp}.dat"


class MAKFileProcessor(BaseFileProcessor):
    ALLOWED_EXTENSIONS = [".mak"]
    ALLOWED_MIMETYPES = ["application/octet-stream", "text/plain"]
    ASSOC_FILEFORMAT = Format.FileFormat.COMPASS_MAK

    TARGET_FOLDER = None
    TARGET_SAVE_FILENAME = "project.mak"
    TARGET_DOWNLOAD_FILENAME = "{project_name}__{timestamp}.mak"
