"""Verify every backend against the local S3 provider, including public GETs."""

from __future__ import annotations

import json
import uuid
from http import HTTPStatus
from typing import TYPE_CHECKING
from typing import Any
from urllib.parse import parse_qs
from urllib.parse import urlsplit

import pytest
import requests
from django.conf import settings
from django.core.files.base import ContentFile
from django.utils.http import content_disposition_header

from speleodb.utils.s3_storages import AttachmentStorage
from speleodb.utils.s3_storages import BrowserFacingS3Storage
from speleodb.utils.s3_storages import ExportStorage
from speleodb.utils.s3_storages import GeoJSONStorage
from speleodb.utils.s3_storages import GISLayerStorage
from speleodb.utils.s3_storages import GPSTrackStorage
from speleodb.utils.s3_storages import PersonPhotoStorage
from speleodb.utils.s3_storages import S3MediaStorage
from speleodb.utils.s3_storages import S3StaticStorage

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

pytestmark = pytest.mark.skip_if_lighttest

BACKENDS: tuple[tuple[type[BrowserFacingS3Storage], str, bool], ...] = (
    (S3MediaStorage, "public, max-age=86400", False),
    (PersonPhotoStorage, "public, max-age=86400", True),
    (AttachmentStorage, "public, max-age=86400", False),
    (GeoJSONStorage, "public, max-age=86400", False),
    (GPSTrackStorage, "private, no-store", False),
    (GISLayerStorage, "private, no-store", False),
    (ExportStorage, "public, max-age=86400", False),
    (S3StaticStorage, "public, max-age=120", True),
)


@pytest.fixture(scope="module")
def backend_bucket() -> Iterator[str]:
    """Keep public static-file tests separate from the canonical private buckets."""
    assert settings.AWS_S3_ENDPOINT_URL
    client: Any = BrowserFacingS3Storage().connection.meta.client
    bucket: str = f"storage-backends-{uuid.uuid4().hex}"
    client.create_bucket(Bucket=bucket)
    try:
        client.put_bucket_policy(
            Bucket=bucket,
            Policy=json.dumps(
                {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Principal": "*",
                            "Action": "s3:GetObject",
                            "Resource": [
                                f"arn:aws:s3:::{bucket}/media/people/photos/*",
                                f"arn:aws:s3:::{bucket}/staticfiles/*",
                            ],
                        }
                    ],
                }
            ),
        )
        yield bucket
    finally:
        for page in client.get_paginator("list_objects_v2").paginate(Bucket=bucket):
            for item in page.get("Contents", []):
                client.delete_object(Bucket=bucket, Key=item["Key"])
        client.delete_bucket(Bucket=bucket)


@pytest.mark.parametrize(("backend", "cache_control", "public"), BACKENDS)
def test_all_backends_serve_stored_headers_and_share_exact_key_transfers(
    backend: type[BrowserFacingS3Storage],
    cache_control: str,
    *,
    public: bool,
    backend_bucket: str,
    tmp_path: Path,
) -> None:
    browser_endpoint: str = (
        getattr(settings, "AWS_S3_BROWSER_ENDPOINT_URL", None)
        or settings.AWS_S3_ENDPOINT_URL
    )
    storage: BrowserFacingS3Storage = backend(
        bucket_name=backend_bucket,
        custom_domain=f"{urlsplit(browser_endpoint).netloc}/{backend_bucket}",
    )
    disposition: str = (
        content_disposition_header(as_attachment=True, filename="survey résumé.dat")
        or "attachment"
    )
    storage.object_parameters = {
        **storage.object_parameters,
        "ContentDisposition": disposition,
        "ContentType": "application/octet-stream",
    }
    path: Path = tmp_path / "replacement.dat"
    path.write_bytes(b"streamed replacement")
    name: str = storage.save("headers.dat", ContentFile(b"original contents"))
    try:
        url: str = storage.url(name)
        query: dict[str, list[str]] = parse_qs(urlsplit(url).query)
        if public:
            assert not query
        else:
            assert query["X-Amz-Signature"]
            assert all(parameter.startswith("X-Amz-") for parameter in query)

        for expected in (b"original contents", b"streamed replacement"):
            if expected == b"streamed replacement":
                storage.upload_file(name, path)
            metadata: dict[str, Any] = storage.connection.meta.client.head_object(
                Bucket=backend_bucket, Key=storage.object_key(name)
            )
            response: requests.Response = requests.get(url, timeout=10)
            assert response.status_code == HTTPStatus.OK
            assert response.content == expected
            assert metadata["CacheControl"] == cache_control
            assert response.headers["Cache-Control"] == cache_control
            assert metadata["ContentDisposition"] == disposition
            assert response.headers["Content-Disposition"] == disposition
            assert response.headers["Content-Type"] == "application/octet-stream"

        unsigned: str = urlsplit(url)._replace(query="").geturl()
        assert requests.get(unsigned, timeout=10).status_code == (
            HTTPStatus.OK if public else HTTPStatus.FORBIDDEN
        )
        storage.delete_file(name)
        assert not storage.exists(name)
        storage.delete_file(name)
    finally:
        storage.delete_file(name)
