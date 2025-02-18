import hashlib
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.files.uploadedfile import InMemoryUploadedFile
from django.core.files.uploadedfile import TemporaryUploadedFile
from django.utils.timezone import localtime
from mnemo_lib.commands.split import split_dmp_into_sections
from mnemo_lib.models import DMPFile

from speleodb.processors.artifact import Artifact
from speleodb.processors.base import BaseFileProcessor
from speleodb.surveys.models import Format
from speleodb.utils.timing_ctx import timed_section


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

    def _get_storage_name(self, filepath: Path) -> str:
        # 1. Calculate the new file sha1 hash
        filehash = calculate_sha1(file_path=filepath)

        # 2. Look for a collision with pre-existing files
        # - if found raises `FileExistsError`
        for existing_f in self.folder.rglob("*.dmp"):
            if existing_f.is_file():  # Skip directories and other non-files
                if filehash == calculate_sha1(file_path=existing_f):
                    raise FileExistsError(
                        f"This file already exist at path: `{existing_f}`."
                    )
        dmp_model = DMPFile.from_dmp(filepath)

        # 3. Build the new filename and return it
        try:
            dmp_date = dmp_model.sections[0].date.strftime(self.DATETIME_FORMAT)
            dmp_name = dmp_model.sections[0].name
            return f"mnemo_{dmp_date}_{dmp_name}__{filehash[:8]}.dmp"

        except IndexError:
            return f"mnemo_{localtime().strftime(self.DATETIME_FORMAT)}__{filehash[:8]}.dmp"  # noqa: E501

    def _add_file_to_project(self, artifact: Artifact) -> list[Path]:
        with TemporaryDirectory() as tmp_dir:
            tmp_dir_path = Path(tmp_dir)

            with timed_section("File DMP pre-processing"):
                input_f = tmp_dir_path / "initial.dmp"
                artifact.write(input_f)

                out_dir_path = tmp_dir_path / "splitted"
                out_dir_path.mkdir()

                split_dmp_into_sections(
                    input_file=input_f, output_directory=out_dir_path
                )

            added_files = []
            with timed_section("File copy to project dir"):
                for dmp_f in sorted(out_dir_path.glob("*.dmp")):
                    try:
                        target_path = self.folder / self._get_storage_name(
                            filepath=dmp_f
                        )
                    except FileExistsError:
                        continue
                    shutil.copyfile(dmp_f, target_path)
                    added_files.append(target_path)

        return added_files


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
