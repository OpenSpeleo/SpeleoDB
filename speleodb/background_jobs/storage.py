"""Export-specific metadata on the shared private S3 storage backend."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.utils.http import content_disposition_header

from speleodb.utils.s3_storages import ExportStorage

if TYPE_CHECKING:
    from pathlib import Path


def _archive_name(key: str) -> str:
    prefix: str = f"{ExportStorage.location}/"
    if not key.startswith(prefix) or key == prefix:
        raise ValueError("An object key inside the exports prefix is required.")
    return key.removeprefix(prefix)


def upload_archive(path: Path, *, key: str, filename: str, sha256: str) -> None:
    ExportStorage().upload_file(
        _archive_name(key),
        path,
        parameters={
            "ContentType": "application/zip",
            "ContentDisposition": content_disposition_header(
                as_attachment=True, filename=filename
            )
            or "attachment",
            "Metadata": {"sha256": sha256},
        },
    )


def delete_archive(*, key: str) -> None:
    ExportStorage().delete_file(_archive_name(key))


def signed_archive_url(*, key: str, expires: int) -> str:
    return ExportStorage().url(_archive_name(key), expire=expires)
