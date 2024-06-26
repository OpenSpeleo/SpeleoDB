from speleodb.processors.base import BaseFileProcessor
from speleodb.surveys.models import Format


class DATFileProcessor(BaseFileProcessor):
    ALLOWED_EXTENSIONS = [".dat"]
    ALLOWED_MIMETYPES = ["application/octet-stream", "text/plain"]
    TARGET_SAVE_FILENAME = "project.dat"
    TARGET_DOWNLOAD_FILENAME = "project_{timestamp}.dat"
    ASSOC_FILEFORMAT = Format.FileFormat.COMPASS_DAT


class MAKFileProcessor(BaseFileProcessor):
    ALLOWED_EXTENSIONS = [".mak"]
    ALLOWED_MIMETYPES = ["application/octet-stream", "text/plain"]
    TARGET_SAVE_FILENAME = "project.mak"
    TARGET_DOWNLOAD_FILENAME = "project_{timestamp}.mak"
    ASSOC_FILEFORMAT = Format.FileFormat.COMPASS_MAK
