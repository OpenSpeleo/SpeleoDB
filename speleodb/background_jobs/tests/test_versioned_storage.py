"""Exercise version-aware export cleanup against a disposable local S3 bucket."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING
from typing import Any
from urllib.parse import urlsplit

from speleodb.background_jobs.storage import delete_archive
from speleodb.background_jobs.storage import export_s3_client

if TYPE_CHECKING:
    from pytest_django.fixtures import Settings


def _versions(client: Any, bucket: str) -> list[dict[str, str]]:
    return [
        {"Key": item["Key"], "VersionId": item["VersionId"]}
        for page in client.get_paginator("list_object_versions").paginate(Bucket=bucket)
        for category in ("Versions", "DeleteMarkers")
        for item in page.get(category, [])
    ]


def test_cleanup_removes_exact_versions_and_markers(settings: Settings) -> None:
    assert urlsplit(settings.AWS_S3_ENDPOINT_URL).hostname in {
        "localhost",
        "127.0.0.1",
        "rustfs",
    }, "The disposable versioning test requires local object storage."
    assert settings.AWS_STORAGE_BUCKET_NAME == "speleodb-user-artifacts-test"
    bucket: str = f"export-versions-{uuid.uuid4().hex}"
    key: str = "exports/attempt.zip"
    neighbor: str = f"{key}.other"
    client = export_s3_client()
    client.create_bucket(Bucket=bucket)
    settings.AWS_STORAGE_BUCKET_NAME = bucket
    try:
        client.put_bucket_versioning(
            Bucket=bucket, VersioningConfiguration={"Status": "Enabled"}
        )
        first: str = client.put_object(Bucket=bucket, Key=key, Body=b"first")[
            "VersionId"
        ]
        second: str = client.put_object(Bucket=bucket, Key=key, Body=b"second")[
            "VersionId"
        ]
        neighboring: str = client.put_object(
            Bucket=bucket, Key=neighbor, Body=b"unrelated"
        )["VersionId"]
        assert first
        assert second
        assert first != second

        delete_archive(key=key, version=first)
        versions: list[dict[str, str]] = _versions(client, bucket)
        assert {"Key": key, "VersionId": first} not in versions
        assert {"Key": key, "VersionId": second} in versions
        assert {"Key": neighbor, "VersionId": neighboring} in versions

        marker: str = client.delete_object(Bucket=bucket, Key=key)["VersionId"]
        assert {"Key": key, "VersionId": marker} in _versions(client, bucket)
        delete_archive(key=key)
        assert _versions(client, bucket) == [
            {"Key": neighbor, "VersionId": neighboring}
        ]
        delete_archive(key=key)
        assert _versions(client, bucket) == [
            {"Key": neighbor, "VersionId": neighboring}
        ]
    finally:
        for version in _versions(client, bucket):
            client.delete_object(Bucket=bucket, **version)
        client.delete_bucket(Bucket=bucket)
