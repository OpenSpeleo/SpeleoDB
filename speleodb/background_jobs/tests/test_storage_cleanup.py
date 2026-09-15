"""Cleanup removes actual unfinished S3 uploads without touching neighboring keys."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from botocore.exceptions import ClientError
from django.conf import settings

from speleodb.background_jobs.storage import delete_archive
from speleodb.utils.s3_storages import ExportStorage


def test_delete_archive_aborts_only_exact_key_multipart_uploads() -> None:
    client = ExportStorage().connection.meta.client
    prefix: str = f"exports/test-multipart-{uuid.uuid4()}/"
    key: str = f"{prefix}archive.zip"
    neighbor: str = f"{key}.other"
    bucket: str = settings.AWS_STORAGE_BUCKET_NAME
    uploads: list[dict[str, str]] = []
    try:
        for upload_key in (key, neighbor):
            response: dict[str, Any] = client.create_multipart_upload(
                Bucket=bucket,
                Key=upload_key,
            )
            uploads.append(
                {"Bucket": bucket, "Key": upload_key, "UploadId": response["UploadId"]}
            )
            client.upload_part(
                Bucket=bucket,
                Key=upload_key,
                UploadId=response["UploadId"],
                PartNumber=1,
                Body=b"unfinished archive bytes",
            )
        delete_archive(key=key)
        remaining: list[str] = [
            upload["Key"]
            for page in client.get_paginator("list_multipart_uploads").paginate(
                Bucket=bucket, Prefix=key
            )
            for upload in page.get("Uploads", [])
        ]
        assert key not in remaining
        with pytest.raises(ClientError) as deleted_upload:
            client.list_parts(**uploads[0])
        assert deleted_upload.value.response["Error"]["Code"] == "NoSuchUpload"
        # Inspect the neighbor by its upload ID: RustFS currently treats a
        # multipart Prefix like an exact key instead of AWS's starts-with filter.
        neighbor_parts: dict[str, Any] = client.list_parts(**uploads[1])
        assert [part["PartNumber"] for part in neighbor_parts["Parts"]] == [1]
        # Repeated maintenance delivery must be harmless.
        delete_archive(key=key)
    finally:
        for upload in uploads:
            # Idempotent helper catches a racing/already removed upload.
            delete_archive(key=upload["Key"])
