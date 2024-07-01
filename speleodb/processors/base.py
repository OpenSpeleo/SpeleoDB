import contextlib
import shutil
import time
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.core.files.uploadedfile import TemporaryUploadedFile

from speleodb.surveys.models import Format
from speleodb.surveys.models import Project
from speleodb.users.models import User
from speleodb.utils.exceptions import ProjectNotFound


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
    def file(self):
        return self._file

    @property
    def name(self):
        return self._file.name

    @property
    def path(self):
        if self._path is None:
            raise RuntimeError(
                f"This {self.__class__.__name__} has not been saved to disk yet."
            )
        return self._path

    @property
    def extension(self):
        return Path(self.name).suffix.lower()

    @property
    def content_type(self):
        return self.file.content_type

    def read(self):
        return self.file.read()

    def write(self, path: Path):
        if self._path is not None:
            raise RuntimeError(f"This file as been already saved at: `{self.path}`.")

        with path.open(mode="wb") as f:
            f.write(self.read())

        self._path = path

    def assert_valid(self, allowed_mimetypes, allowed_extensions):
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
    TARGET_SAVE_FILENAME = None
    TARGET_DOWNLOAD_FILENAME = None
    ASSOC_FILEFORMAT = Format.FileFormat.OTHER

    def __init__(self, project: Project, hexsha=None):
        self._project = project
        self._hexsha = hexsha
        self.checkout_commit_or_master()

    @property
    def project(self):
        return self._project

    @property
    def hexsha(self):
        return self._hexsha

    def commit_file(self, file, user: User, commit_msg: str):
        # Make sure the project is update to ToT (Top of Tree)
        self.project.git_repo.checkout_branch(branch_name="master")

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

        target_path = self.project.git_repo.path / filename
        file.write(path=target_path)

        return file, self.project.git_repo.commit_and_push_project(
            message=commit_msg, author_name=user.name, author_email=user.email
        )

    def checkout_commit_or_master(self):
        if not self.project.git_repo:
            raise ProjectNotFound("This project does not exist on gitlab or on drive")

        if self.hexsha is None:
            # Make sure the project is update to ToT (Top of Tree)
            self.project.git_repo.checkout_branch_or_commit(branch_name="master")
            self.project.git_repo.pull()

        else:
            self.project.git_repo.checkout_branch_or_commit(hexsha=self.hexsha)

    def postprocess_file_before_download(self, filepath: Path):
        with contextlib.suppress(shutil.SameFileError):
            return shutil.copy(src=self.source_f, dst=filepath)

    @property
    def source_f(self):
        source_f = self.project.git_repo.path / self.TARGET_SAVE_FILENAME
        if not source_f.is_file():
            raise ValidationError(f"Impossible to find the file: `{source_f}` ...")
        return source_f

    def get_file_for_download(self, target_f: Path):
        if not isinstance(target_f, Path):
            raise TypeError(f"Unexpected `target_f` type received: {type(target_f)}")

        commit_date = time.gmtime(self.project.git_repo.head.commit.committed_date)
        filename = (
            self.TARGET_DOWNLOAD_FILENAME.format(
                timestamp=time.strftime("%Y-%m-%d_%Hh%M", commit_date)
            )
            if self.TARGET_DOWNLOAD_FILENAME is not None
            else target_f.name
        )

        try:
            self.postprocess_file_before_download(target_f)

        except PermissionError as e:
            raise RuntimeError from e

        return filename
