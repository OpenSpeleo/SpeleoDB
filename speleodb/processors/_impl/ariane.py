import hashlib
from pathlib import Path

from django.core.files.uploadedfile import InMemoryUploadedFile
from django.core.files.uploadedfile import TemporaryUploadedFile
from django.utils.timezone import localtime

from speleodb.processors.artifact import Artifact
from speleodb.processors.base import BaseFileProcessor
from speleodb.surveys.models import Format


def calculate_sha1(
    file_path: str | Path | None = None,
    file_obj: InMemoryUploadedFile | TemporaryUploadedFile | None = None,
    buffer_size=65536,
) -> str:
    """
    Calculate SHA-1 hash of a file in a memory-efficient way.

    :param file_path: Path to the file
    :param file_obj: A file object (InMemoryUploadedFile or TemporaryUploadedFile)
    :param buffer_size: Size of the buffer to read chunks of the file (default: 64 KiB)
    :return: SHA-1 hash as a hexadecimal string
    """

    if (file_path is None) is (file_obj is None):
        raise ValueError(
            "`file_path` and `file_obj` are mutually exclusive. "
            f"Only one should be not None: {file_path=} && {file_obj=}"
        )

    sha1 = hashlib.sha1()  # noqa: S324

    if file_path is not None:
        if not isinstance(file_path, Path):
            file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"Can't find file: `{file_path}`.")

        with file_path.open(mode="rb") as f:
            # Read and update hash in chunks
            while chunk := f.read(buffer_size):
                sha1.update(chunk)

    else:
        # Ensure the file pointer is at the beginning
        file_obj.seek(0)

        # Read and update hash in chunks
        while chunk := file_obj.read(buffer_size):
            sha1.update(chunk)

        # Optionally reset the file pointer after hashing
        file_obj.seek(0)

    return sha1.hexdigest()


class AGRFileProcessor(BaseFileProcessor):
    ALLOWED_EXTENSIONS = [".agr"]
    ALLOWED_MIMETYPES = ["application/octet-stream", "text/plain"]
    ASSOC_FILEFORMAT = Format.FileFormat.ARIANE_AGR

    TARGET_FOLDER = None
    TARGET_SAVE_FILENAME = "project.agr"
    TARGET_DOWNLOAD_FILENAME = "{project_name}__{timestamp}.agr"


class DMPFileProcessor(BaseFileProcessor):
    ALLOWED_EXTENSIONS = [".dmp"]
    ALLOWED_MIMETYPES = ["application/octet-stream", "text/plain"]
    ASSOC_FILEFORMAT = Format.FileFormat.OTHER

    TARGET_FOLDER = "mnemo_DMPs"
    TARGET_SAVE_FILENAME = None
    TARGET_DOWNLOAD_FILENAME = None

    def _get_storage_name(self, folder: Path, artifact: Artifact) -> str:
        # 1. Calculate the new file sha1 hash
        filehash = calculate_sha1(file_obj=artifact.file)

        # 2. Look for a collision with pre-existing files
        # - if found raises `FileExistsError`
        for existing_f in folder.rglob("*.dmp"):
            if existing_f.is_file():  # Skip directories and other non-files
                if filehash == calculate_sha1(file_path=existing_f):
                    raise FileExistsError(
                        f"This file already exist at path: `{existing_f}`."
                    )

        # 3. Build the new filename and return it
        return f"mnemo_{localtime().strftime(self.DATETIME_FORMAT)}__{filehash[:8]}.dmp"


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
