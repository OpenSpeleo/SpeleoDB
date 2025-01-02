from speleodb.processors.base import BaseFileProcessor
from speleodb.surveys.models import Format


class TMLFileProcessor(BaseFileProcessor):
    ALLOWED_EXTENSIONS = [".tml"]
    ALLOWED_MIMETYPES = ["application/octet-stream", "application/zip"]
    ASSOC_FILEFORMAT = Format.FileFormat.ARIANE_TML

    TARGET_FOLDER = None
    TARGET_SAVE_FILENAME = "project.tml"
    TARGET_DOWNLOAD_FILENAME = "{project_name}__{timestamp}.tml"


class TMLUFileProcessor(BaseFileProcessor):
    ALLOWED_EXTENSIONS = [".tmlu"]
    ALLOWED_MIMETYPES = ["application/octet-stream", "text/plain"]
    ASSOC_FILEFORMAT = Format.FileFormat.ARIANE_TMLU

    TARGET_FOLDER = None
    TARGET_SAVE_FILENAME = "project.tmlu"
    TARGET_DOWNLOAD_FILENAME = "{project_name}__{timestamp}.tmlu"


class AGRFileProcessor(BaseFileProcessor):
    ALLOWED_EXTENSIONS = [".agr"]
    ALLOWED_MIMETYPES = ["application/octet-stream", "text/plain"]
    ASSOC_FILEFORMAT = Format.FileFormat.ARIANE_AGR

    TARGET_FOLDER = None
    TARGET_SAVE_FILENAME = "project.agr"
    TARGET_DOWNLOAD_FILENAME = "{project_name}__{timestamp}.agr"
