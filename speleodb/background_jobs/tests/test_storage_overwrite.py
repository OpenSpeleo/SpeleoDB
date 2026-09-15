"""Writing an existing export key replaces its content without renaming it."""

from __future__ import annotations

import hashlib
import uuid
from http import HTTPStatus
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

import requests
from django.conf import settings
from django.core.files.base import ContentFile

from speleodb.background_jobs.storage import delete_archive
from speleodb.background_jobs.storage import signed_archive_url
from speleodb.background_jobs.storage import upload_archive
from speleodb.utils.s3_storages import ExportStorage

if TYPE_CHECKING:
    from pathlib import Path


def test_save_and_streaming_upload_overwrite_the_same_key(tmp_path: Path) -> None:
    assert settings.AWS_STORAGE_BUCKET_NAME == "speleodb-user-artifacts-test"
    assert urlsplit(settings.AWS_S3_ENDPOINT_URL).hostname in {
        "localhost",
        "127.0.0.1",
        "rustfs",
    }
    storage: ExportStorage = ExportStorage()
    name: str = f"overwrite-{uuid.uuid4()}.zip"
    key: str = storage.object_key(name)
    neighbor_name: str = f"{name}.other"
    neighbor_key: str = storage.object_key(neighbor_name)
    try:
        assert storage.save(name, ContentFile(b"first contents")) == name
        assert storage.save(neighbor_name, ContentFile(b"unrelated")) == neighbor_name
        assert storage.save(name, ContentFile(b"replacement")) == name
        url: str = signed_archive_url(key=key, expires=60)
        response: requests.Response = requests.get(url, timeout=10)
        assert response.status_code == HTTPStatus.OK
        assert response.content == b"replacement"

        path: Path = tmp_path / name
        payload: bytes = b"streamed replacement"
        path.write_bytes(payload)
        upload_archive(
            path,
            key=key,
            filename=name,
            sha256=hashlib.sha256(payload).hexdigest(),
        )
        response = requests.get(url, timeout=10)
        assert response.status_code == HTTPStatus.OK
        assert response.content == payload
        assert (
            response.headers["Content-Disposition"] == f'attachment; filename="{name}"'
        )
        assert response.headers["Cache-Control"] == "private, no-store"
        # Inspect only this test's names; other test files may coexist.
        names: list[str] = [
            stored_name for stored_name in storage.listdir("")[1] if name in stored_name
        ]
        assert set(names) == {name, neighbor_name}

        delete_archive(key=key)
        delete_archive(key=key)
        assert not storage.exists(name)
        with storage.open(neighbor_name) as neighbor:
            assert neighbor.read() == b"unrelated"
    finally:
        delete_archive(key=key)
        delete_archive(key=neighbor_key)
