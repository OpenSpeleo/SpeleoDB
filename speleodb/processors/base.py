import contextlib
import re
import shutil
import time
from datetime import UTC
from datetime import datetime
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.core.files.uploadedfile import TemporaryUploadedFile
from django.utils.text import slugify
from django.utils.timezone import get_default_timezone

from speleodb.surveys.models import Format
from speleodb.surveys.models import Project
from speleodb.utils.timing_ctx import timed_section


class Artifact:
    def __init__(self, file: InMemoryUploadedFile | TemporaryUploadedFile) -> None:
        if not isinstance(file, (InMemoryUploadedFile, TemporaryUploadedFile)):
            raise TypeError(
                "Expected `InMemoryUploadedFile` or `TemporaryUploadedFile`, received: "
                f"{type(file)}"
            )
        self._file = file
        self._path = None

    @property
    def file(self) -> InMemoryUploadedFile | TemporaryUploadedFile:
        return self._file

    @property
    def name(self) -> str:
        return self._file.name

    @property
    def path(self) -> Path:
        if self._path is None:
            raise RuntimeError(
                f"This {self.__class__.__name__} has not been saved to disk yet."
            )
        return self._path

    @property
    def extension(self) -> str:
        return Path(self.name).suffix.lower()

    @property
    def content_type(self) -> str | None:
        return self.file.content_type

    def read(self) -> str:
        return self.file.read()

    def write(self, path: Path) -> None:
        if self._path is not None:
            raise RuntimeError(f"This file as been already saved at: `{self.path}`.")

        with path.open(mode="wb") as f:
            f.write(self.read())

        self._path = path

    def assert_valid(self, allowed_mimetypes, allowed_extensions) -> None:
        if not isinstance(allowed_mimetypes, (list, tuple)):
            raise TypeError(f"Unexpected type: {type(allowed_mimetypes)=}")

        if not isinstance(allowed_extensions, (list, tuple)):
            raise TypeError(f"Unexpected type: {type(allowed_mimetypes)=}")

        if self.content_type not in allowed_mimetypes and "*" not in allowed_mimetypes:
            raise ValidationError(
                f"Invalid file type received: `{self.content_type}`, "
                f"expected one of: {allowed_mimetypes}"
            )

        if self.extension not in allowed_extensions and "*" not in allowed_extensions:
            raise ValidationError(
                f"Invalid file extension received: `{self.extension}`, "
                f"expected one of: {allowed_extensions}"
            )


class BaseFileProcessor:
    ALLOWED_EXTENSIONS = ["*"]
    ALLOWED_MIMETYPES = ["*"]
    TARGET_FOLDER = "misc"
    TARGET_SAVE_FILENAME = None
    TARGET_DOWNLOAD_FILENAME = None
    ASSOC_FILEFORMAT = Format.FileFormat.OTHER

    def __init__(self, project: Project, hexsha: str | None = None):
        if not isinstance(project, Project):
            raise TypeError(f"Invalid project type: {type(project)}")

        if hexsha is not None and not self.validate_hexsha(hexsha):
            raise ValueError(f"Invalid Git SHA value: `{hexsha}`")

        self._project = project
        self._hexsha = hexsha

    def validate_hexsha(self, hexsha: str) -> bool:
        """
        Verify if the provided hexsha is a valid Git SHA (could be a full or partial).
        A valid partial SHA-1 can be between 4 and 40 hexadecimal characters long.
        """
        # Regular expression for a valid partial or full Git SHA-1 hash
        git_sha_pattern = r"^[a-fA-F0-9]{4,40}$"

        # Return True if the hexsha matches the pattern, else False
        return bool(re.match(git_sha_pattern, hexsha))

    @property
    def project(self) -> Project:
        return self._project

    @property
    def hexsha(self) -> str | None:
        return self._hexsha

    def add_file_to_project(
        self, file: InMemoryUploadedFile | TemporaryUploadedFile
    ) -> Artifact:
        file = Artifact(file)
        file.assert_valid(
            allowed_extensions=self.ALLOWED_EXTENSIONS,
            allowed_mimetypes=self.ALLOWED_MIMETYPES,
        )

        filename = (
            self.TARGET_SAVE_FILENAME
            if self.TARGET_SAVE_FILENAME is not None
            else file.name
        )

        folder = self.project.git_repo.path
        if self.TARGET_FOLDER is not None:
            folder: Path = folder / self.TARGET_FOLDER
            folder.mkdir(parents=True, exist_ok=True)

        target_path = folder / filename

        with timed_section("File copy to project dir"):
            file.write(path=target_path)

        return file

    def preprocess_file_before_download(self, destination_f: Path) -> None:
        with contextlib.suppress(shutil.SameFileError):
            shutil.copy(src=self.source_f, dst=destination_f)

    @property
    def source_f(self) -> Path:
        source_f = self.project.git_repo.path / self.TARGET_SAVE_FILENAME
        if not source_f.is_file():
            raise ValidationError(f"Impossible to find the file: `{source_f}` ...")
        return source_f

    def get_file_for_download(self, target_f: Path) -> Path:
        if isinstance(target_f, str):
            target_f = Path(target_f)

        if not isinstance(target_f, Path):
            raise TypeError(f"Unexpected `target_f` type received: {type(target_f)}")

        # 1. Prepare the file for download
        try:
            self.preprocess_file_before_download(destination_f=target_f)

        except PermissionError as e:
            raise RuntimeError from e

        # 2. Generate the filename that will be seen in the browser
        if self.hexsha is not None:
            commit = self.project.git_repo.commit(self.hexsha)
        else:
            commit = self.project.git_repo.head.commit

        commit_date = time.gmtime(commit.committed_date)

        # 3. Convert `time.struct_time` to datetime to be "timezone-aware"
        naive_datetime = datetime(*commit_date[:6], tzinfo=UTC)
        tz_aware_datetime = naive_datetime.astimezone(tz=get_default_timezone())

        return (
            self.TARGET_DOWNLOAD_FILENAME.format(
                project_name=slugify(self.project.name, allow_unicode=False).lower(),
                timestamp=tz_aware_datetime.strftime("%Y-%m-%d_%Hh%M"),
            )
            if self.TARGET_DOWNLOAD_FILENAME is not None
            else target_f.name
        )
