"""Opt-in >4 GiB ZIP64 export through the actual configured S3 storage."""

from __future__ import annotations

import contextlib
import hashlib
import os
import resource
import shutil
import time
import uuid
from typing import TYPE_CHECKING
from zipfile import ZipFile

import orjson
import pytest
from django.conf import settings
from django.core.files.base import File

from speleodb.background_jobs.archive import build_archive
from speleodb.background_jobs.storage import delete_archive
from speleodb.background_jobs.storage import upload_archive
from speleodb.gis.models import GISLayer
from speleodb.gis.models import GISLayerUserPermission
from speleodb.utils.s3_storages import ExportStorage

if TYPE_CHECKING:
    from pathlib import Path

    from speleodb.users.models import User


MEMBER_BYTES: int = 4 * 1024**3 + 17
READ_CHUNK_BYTES: int = 1024 * 1024
MAX_ADDITIONAL_RSS_KIB: int = 512 * 1024
ZIP64_EXTRACT_VERSION: int = 45


@pytest.mark.django_db
@pytest.mark.skipif(
    os.environ.get("SPELEODB_TEST_LARGE_ARCHIVE") != "1",
    reason="Set SPELEODB_TEST_LARGE_ARCHIVE=1 inside Docker for the 4 GiB test.",
)
def test_actual_s3_zip64_archive_has_bounded_memory(user: User, tmp_path: Path) -> None:
    # S3 source, staged download, local ZIP and uploaded ZIP share Docker's disk.
    assert shutil.disk_usage(tmp_path).free > MEMBER_BYTES * 4
    source: Path = tmp_path / "large-source.zip"
    with source.open("wb") as output:
        output.truncate(MEMBER_BYTES)
    layer = GISLayer(name="Large ZIP64 fixture", created_by=user.email)
    storage = layer.source_f.storage
    source_key: str | None = None
    artifact_key: str = f"exports/large-test-{uuid.uuid4()}.zip"
    started: float = time.monotonic()
    initial_rss: int = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    try:
        with source.open("rb") as source_file:
            source_key = storage.save(
                f"{layer.id}/source.zip", File(source_file, name="source.zip")
            )
        source_uploaded: float = time.monotonic()
        layer.source_f = source_key
        layer.data_f = source_key
        layer.save()
        GISLayerUserPermission.objects.create(user=user, gis_layer=layer)
        destination: Path = tmp_path / "export.zip"
        result = build_archive(
            user=user, destination=destination, progress=lambda *_: None
        )
        built: float = time.monotonic()
        assert not result.partial
        member = result.manifest["resources"][0]["files"][0]
        digest = hashlib.sha256()
        byte_count: int = 0
        with ZipFile(destination) as archive:
            info = archive.getinfo(member["path"])
            assert info.file_size == MEMBER_BYTES
            assert info.extract_version >= ZIP64_EXTRACT_VERSION
            with archive.open(info) as exported:
                while chunk := exported.read(READ_CHUNK_BYTES):
                    assert chunk == b"\x00" * len(chunk)
                    digest.update(chunk)
                    byte_count += len(chunk)
        assert byte_count == MEMBER_BYTES
        assert digest.hexdigest() == member["sha256"]
        upload_archive(
            destination,
            key=artifact_key,
            filename="large-export.zip",
            sha256=result.sha256,
        )
        client = ExportStorage().connection.meta.client
        metadata = client.head_object(
            Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=artifact_key
        )
        assert metadata["ContentLength"] == result.size_bytes
        assert metadata["Metadata"]["sha256"] == result.sha256
        download_parameters: dict[str, str] = {
            "Bucket": settings.AWS_STORAGE_BUCKET_NAME,
            "Key": artifact_key,
        }
        downloaded_digest = hashlib.sha256()
        downloaded_bytes: int = 0
        with contextlib.closing(
            client.get_object(**download_parameters)["Body"]
        ) as downloaded:
            while chunk := downloaded.read(READ_CHUNK_BYTES):
                downloaded_digest.update(chunk)
                downloaded_bytes += len(chunk)
        assert downloaded_bytes == result.size_bytes
        assert downloaded_digest.hexdigest() == result.sha256
        peak_rss: int = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        assert peak_rss - initial_rss < MAX_ADDITIONAL_RSS_KIB
        print(  # noqa: T201
            orjson.dumps(
                {
                    "member_bytes": MEMBER_BYTES,
                    "archive_bytes": result.size_bytes,
                    "source_upload_seconds": round(source_uploaded - started, 2),
                    "build_seconds": round(built - source_uploaded, 2),
                    "total_seconds": round(time.monotonic() - started, 2),
                    "peak_rss_kib": peak_rss,
                    "additional_peak_rss_kib": peak_rss - initial_rss,
                }
            ).decode()
        )
    finally:
        delete_archive(key=artifact_key)
        if source_key is not None:
            storage.delete(source_key)
        source.unlink(missing_ok=True)
        (tmp_path / "export.zip").unlink(missing_ok=True)
