"""Real local uploads/downloads through the shared export storage backend."""

from __future__ import annotations

import hashlib
import uuid
from http import HTTPStatus
from typing import TYPE_CHECKING
from typing import Any
from urllib.parse import urlsplit

import pytest
import requests
from botocore.exceptions import ClientError
from django.conf import settings
from django.core.exceptions import SuspiciousOperation

from speleodb.background_jobs.storage import delete_archive
from speleodb.background_jobs.storage import signed_archive_url
from speleodb.background_jobs.storage import upload_archive
from speleodb.utils.s3_storages import ExportStorage

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.parametrize("legacy_path", [False, True])
def test_upload_download_and_delete_preserve_exact_key_and_metadata(
    tmp_path: Path, *, legacy_path: bool
) -> None:
    assert settings.AWS_STORAGE_BUCKET_NAME == "speleodb-user-artifacts-test"
    assert urlsplit(settings.AWS_S3_ENDPOINT_URL).hostname in {
        "localhost",
        "127.0.0.1",
        "rustfs",
    }
    filename: str = f"storage-test-{uuid.uuid4()}.zip"
    key: str = f"exports/{'3/job/attempt/' if legacy_path else ''}{filename}"
    path: Path = tmp_path / filename
    # Cross the multipart threshold using the same bounded transfer as exports.
    data: bytes = b"shared storage test\n" * (1024 * 1024)
    path.write_bytes(data)
    digest: str = hashlib.sha256(data).hexdigest()
    storage: ExportStorage = ExportStorage()
    client: Any = storage.connection.meta.client
    try:
        upload_archive(path, key=key, filename=filename, sha256=digest)
        metadata: dict[str, Any] = client.head_object(
            Bucket=storage.bucket_name, Key=key
        )
        assert metadata["Metadata"]["sha256"] == digest
        assert metadata["ContentLength"] == len(data)
        assert metadata["ContentType"] == "application/zip"
        assert metadata["CacheControl"] == "public, max-age=86400"
        assert metadata["ContentDisposition"] == f'attachment; filename="{filename}"'
        url: str = signed_archive_url(key=key, expires=180)
        response: requests.Response = requests.get(url, timeout=30)
        assert response.status_code == HTTPStatus.OK
        assert response.content == data
        assert response.headers["Cache-Control"] == "public, max-age=86400"
        assert response.headers["Content-Disposition"] == metadata["ContentDisposition"]
        delete_archive(key=key)
        with pytest.raises(ClientError) as missing:
            client.head_object(Bucket=storage.bucket_name, Key=key)
        assert missing.value.response["Error"]["Code"] in {"404", "NoSuchKey"}
    finally:
        delete_archive(key=key)


@pytest.mark.parametrize(
    "key", ["media/file.zip", "exports/", "exports/../media/file.zip"]
)
def test_export_operations_reject_keys_outside_the_export_prefix(
    tmp_path: Path, key: str
) -> None:
    path: Path = tmp_path / "source.zip"
    path.write_bytes(b"test")
    errors: tuple[type[Exception], ...] = (ValueError, SuspiciousOperation)
    with pytest.raises(errors):
        upload_archive(path, key=key, filename=path.name, sha256="test")
    with pytest.raises(errors):
        delete_archive(key=key)
    with pytest.raises(errors):
        signed_archive_url(key=key, expires=60)
