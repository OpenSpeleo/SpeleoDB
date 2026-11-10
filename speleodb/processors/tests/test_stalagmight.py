"""Native SQLite validation and lossless source storage need no application DB."""

from __future__ import annotations

import contextlib
import io
import sqlite3
import zipfile
from typing import TYPE_CHECKING

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.files.uploadedfile import TemporaryUploadedFile

from speleodb.processors._impl.stalagmight import StalagmightFileProcessor
from speleodb.processors.auto_selector import AutoSelector
from speleodb.surveys.models import FileFormat
from speleodb.surveys.models import Project
from speleodb.testing.stalagmight import stalagmight_bytes
from speleodb.utils.exceptions import FileRejectedError

if TYPE_CHECKING:
    from pathlib import Path

INVALID_SQLITE_MESSAGE = "Invalid STALAGMIGHT file: expected a valid SQLite database."


@pytest.fixture
def processor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> StalagmightFileProcessor:
    # Isolate unrelated repository provisioning; validation and filesystem writes
    # remain real. API integration tests cover the actual Git-backed destination.
    monkeypatch.setattr(
        StalagmightFileProcessor, "storage_folder", property(lambda _: tmp_path)
    )
    return StalagmightFileProcessor(Project())


@pytest.fixture
def sqlite_bytes() -> bytes:
    with contextlib.closing(sqlite3.connect(":memory:")) as database:
        database.execute("CREATE TABLE survey (name TEXT)")
        database.execute("INSERT INTO survey VALUES ('Small survey')")
        database.commit()
        return database.serialize()


@pytest.mark.parametrize("temporary_upload", [False, True])
@pytest.mark.parametrize(
    "content_type",
    [
        "application/octet-stream",
        "application/vnd.sqlite3",
        "application/vnd.stalagmight.project",
    ],
)
def test_native_stalagmight_file_preserves_exact_bytes(
    processor: StalagmightFileProcessor,
    tmp_path: Path,
    temporary_upload: bool,
    content_type: str,
) -> None:
    payload = stalagmight_bytes()
    upload: SimpleUploadedFile | TemporaryUploadedFile
    if temporary_upload:
        upload = TemporaryUploadedFile(
            "different.STALX", content_type, len(payload), None
        )
        upload.write(payload)
        upload.seek(0)
    else:
        upload = SimpleUploadedFile("different.STALX", payload, content_type)

    with upload:
        paths = processor.add_to_project(upload)

    assert paths == [tmp_path / "stalagmight.stalx"]
    assert paths[0].read_bytes() == payload
    assert list(tmp_path.iterdir()) == paths


@pytest.mark.parametrize("fileformat", [FileFormat.AUTO, FileFormat.STALAGMIGHT])
def test_processor_selection_accepts_sqlite_without_stalagmight_schema(
    processor: StalagmightFileProcessor,
    sqlite_bytes: bytes,
    fileformat: FileFormat,
) -> None:
    upload = SimpleUploadedFile(
        "generic.stalx", sqlite_bytes, "application/octet-stream"
    )
    selected = AutoSelector.get_upload_processor(fileformat, upload, processor.project)

    paths = selected.add_to_project(upload)

    assert isinstance(selected, StalagmightFileProcessor)
    assert paths[0].read_bytes() == sqlite_bytes


@pytest.mark.parametrize(
    "invalid_kind", ["empty", "text", "zip", "header_only", "truncated", "corrupt_page"]
)
def test_invalid_sqlite_cannot_replace_existing_source(
    processor: StalagmightFileProcessor,
    tmp_path: Path,
    sqlite_bytes: bytes,
    invalid_kind: str,
) -> None:
    existing = tmp_path / "stalagmight.stalx"
    existing.write_bytes(sqlite_bytes)
    payload: bytes
    match invalid_kind:
        case "empty":
            payload = b""
        case "text":
            payload = b"not a SQLite database"
        case "zip":
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, "w") as archive:
                archive.writestr("survey.txt", "survey")
            payload = buffer.getvalue()
        case "header_only":
            payload = b"SQLite format 3\x00"
        case "truncated":
            payload = sqlite_bytes[:100]
        case "corrupt_page":
            # Preserve the entire header and schema page, corrupting the table's
            # b-tree page instead: header-only/schema-only checks miss this.
            database_bytes = bytearray(sqlite_bytes)
            page_size = int.from_bytes(database_bytes[16:18], "big")
            database_bytes[page_size] = 0xFF
            payload = bytes(database_bytes)
        case _:
            raise AssertionError(invalid_kind)
    upload = SimpleUploadedFile("invalid.stalx", payload, "application/octet-stream")

    with pytest.raises(ValidationError) as error:
        processor.add_to_project(upload)

    assert error.value.messages == [INVALID_SQLITE_MESSAGE]
    assert existing.read_bytes() == sqlite_bytes
    assert list(tmp_path.iterdir()) == [existing]


@pytest.mark.parametrize(
    ("filename", "content_type", "exception", "message"),
    [
        (
            "survey.sqlite",
            "application/octet-stream",
            ValidationError,
            "Invalid file extension",
        ),
        ("survey.stalx", "text/plain", ValidationError, "Invalid file type"),
        (
            "survey.sh",
            "application/octet-stream",
            FileRejectedError,
            "rejected for security reasons",
        ),
    ],
)
def test_native_upload_keeps_extension_and_mime_validation(  # noqa: PLR0917
    processor: StalagmightFileProcessor,
    tmp_path: Path,
    sqlite_bytes: bytes,
    filename: str,
    content_type: str,
    exception: type[Exception],
    message: str,
) -> None:
    upload = SimpleUploadedFile(filename, sqlite_bytes, content_type)

    with pytest.raises(exception, match=message):
        processor.add_to_project(upload)

    assert not list(tmp_path.iterdir())
