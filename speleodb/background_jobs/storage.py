"""Private export objects always use S3 directly, bypassing CloudFront."""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any
from typing import cast

import boto3
from boto3.s3.transfer import TransferConfig
from botocore.config import Config
from botocore.exceptions import ClientError
from django.conf import settings
from django.utils.http import content_disposition_header

if TYPE_CHECKING:
    from pathlib import Path


def export_s3_client(*, browser: bool = False) -> Any:
    endpoint = getattr(settings, "AWS_S3_ENDPOINT_URL", None)
    if browser:
        endpoint = getattr(settings, "AWS_S3_BROWSER_ENDPOINT_URL", None) or endpoint
    return boto3.client(  # type: ignore[no-untyped-call]
        "s3",
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        aws_session_token=getattr(settings, "AWS_SESSION_TOKEN", None),
        region_name=getattr(settings, "AWS_S3_REGION_NAME", None),
        endpoint_url=endpoint,
        config=Config(  # type: ignore[no-untyped-call]
            signature_version="s3v4",
            connect_timeout=5,
            read_timeout=60,
            retries={"max_attempts": 3, "mode": "standard"},
            s3={
                "addressing_style": getattr(settings, "AWS_S3_ADDRESSING_STYLE", "auto")
            },
        ),
    )


def upload_archive(path: Path, *, key: str, filename: str, sha256: str) -> str:
    client = export_s3_client()
    parameters: dict[str, Any] = {
        "ContentType": "application/zip",
        "ContentDisposition": content_disposition_header(
            as_attachment=True, filename=filename
        )
        or "attachment",
        "CacheControl": "private, no-store",
        "Metadata": {"sha256": sha256},
    }
    client.upload_file(
        str(path),
        settings.AWS_STORAGE_BUCKET_NAME,
        key,
        ExtraArgs=parameters,
        Config=TransferConfig(  # type: ignore[no-untyped-call]
            max_concurrency=2, multipart_chunksize=16 * 1024 * 1024
        ),
    )
    metadata: dict[str, Any] = client.head_object(
        Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=key
    )
    if metadata["ContentLength"] != path.stat().st_size:
        msg = "Uploaded archive size does not match the generated archive."
        raise OSError(msg)
    return str(metadata.get("VersionId", ""))


def delete_archive(*, key: str, version: str = "") -> None:
    if not key.startswith("exports/"):
        msg = "Refusing to delete an object outside the exports prefix."
        raise ValueError(msg)
    client = export_s3_client()
    parameters: dict[str, str] = {
        "Bucket": settings.AWS_STORAGE_BUCKET_NAME,
        "Key": key,
    }
    # An interrupted upload has no object version yet. Attempts own unique keys,
    # and callers only clean up expired artifacts or attempts past their deadline.
    uploads = client.get_paginator("list_multipart_uploads")
    for page in uploads.paginate(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Prefix=key):
        for upload in page.get("Uploads", []):
            if upload["Key"] != key:
                continue
            try:
                client.abort_multipart_upload(**parameters, UploadId=upload["UploadId"])
            except ClientError as error:
                if error.response.get("Error", {}).get("Code") != "NoSuchUpload":
                    raise
    if version:
        parameters["VersionId"] = version
        client.delete_object(**parameters)
        return
    # A process can die after multipart completion but before recording VersionId.
    # Keys are unique to one attempt, so remove every exact-key version safely.
    paginator = client.get_paginator("list_object_versions")
    for page in paginator.paginate(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Prefix=key):
        for record in [*page.get("Versions", []), *page.get("DeleteMarkers", [])]:
            if record["Key"] == key:
                client.delete_object(**parameters, VersionId=record["VersionId"])
    # Listing is strongly consistent on S3 and includes unversioned objects as
    # the null version. A final key-only delete would create a new delete marker.


def signed_archive_url(*, key: str, version: str, expires: int, filename: str) -> str:
    parameters: dict[str, str] = {
        "Bucket": settings.AWS_STORAGE_BUCKET_NAME,
        "Key": key,
        "ResponseContentDisposition": content_disposition_header(
            as_attachment=True, filename=filename
        )
        or "attachment",
        "ResponseCacheControl": "private, no-store",
    }
    if version:
        parameters["VersionId"] = version
    return cast(
        "str",
        export_s3_client(browser=True).generate_presigned_url(
            "get_object",
            Params=parameters,
            ExpiresIn=expires,
        ),
    )
