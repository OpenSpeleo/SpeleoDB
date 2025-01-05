from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.core.files.uploadedfile import TemporaryUploadedFile

from speleodb.utils.exceptions import FileRejectedError


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

    def assert_valid(
        self,
        allowed_extensions: list[str],
        allowed_mimetypes: list[str],
        rejected_extensions: list[str],
    ) -> None:
        if not isinstance(allowed_extensions, (list, tuple)):
            raise TypeError(f"Unexpected type: {type(allowed_extensions)=}")

        if not isinstance(allowed_mimetypes, (list, tuple)):
            raise TypeError(f"Unexpected type: {type(allowed_mimetypes)=}")

        if not isinstance(rejected_extensions, (list, tuple)):
            raise TypeError(f"Unexpected type: {type(rejected_extensions)=}")

        if self.extension in rejected_extensions:
            raise FileRejectedError(
                f"Invalid file extension received: `{self.extension}`, "
                f"this extension is rejected for security reasons."
            )

        if self.extension not in allowed_extensions and "*" not in allowed_extensions:
            raise ValidationError(
                f"Invalid file extension received: `{self.extension}`, "
                f"expected one of: {allowed_extensions}"
            )

        if self.content_type not in allowed_mimetypes and "*" not in allowed_mimetypes:
            raise ValidationError(
                f"Invalid file type received: `{self.content_type}`, "
                f"expected one of: {allowed_mimetypes}"
            )
