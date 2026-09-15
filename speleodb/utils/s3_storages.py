# -*- coding: utf-8 -*-

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any
from typing import cast

from boto3.s3.transfer import TransferConfig
from botocore.config import Config
from botocore.exceptions import ClientError
from django.conf import settings
from storages.backends.s3 import S3Storage
from storages.utils import clean_name

_PRIVATE_VECTOR_OBJECT_PARAMETERS = {"CacheControl": "private, no-store"}
# Boto accepts API field names; CloudFront forwards S3's HTTP query names.
_S3_DOWNLOAD_QUERY_NAMES: dict[str, str] = {
    "VersionId": "versionId",
    "ResponseCacheControl": "response-cache-control",
    "ResponseContentDisposition": "response-content-disposition",
    "ResponseContentEncoding": "response-content-encoding",
    "ResponseContentLanguage": "response-content-language",
    "ResponseContentType": "response-content-type",
    "ResponseExpires": "response-expires",
}


class BrowserFacingS3Storage(S3Storage):
    """Shared S3 transfers and URLs for CloudFront or a local browser endpoint."""

    bucket_name: str
    client_config: Any
    custom_domain: str | bool | None
    querystring_auth: bool
    querystring_expire: int
    region_name: str | None
    use_ssl: bool
    verify: Any

    def object_key(self, name: str) -> str:
        """Resolve a storage-relative name without escaping this backend's prefix."""
        return cast(
            "str",
            self._normalize_name(clean_name(name)),  # type: ignore[no-untyped-call]
        )

    def upload_file(
        self,
        name: str,
        path: Path,
        *,
        parameters: dict[str, Any] | None = None,
    ) -> str:
        """Stream to an exact, caller-reserved name and return the stored version.

        Unlike save(), this preserves names already recorded in a durable job.
        Multipart transfer buffers use this storage's transfer configuration.
        """
        key: str = self.object_key(name)
        options: dict[str, Any] = self._get_write_parameters(key)  # type: ignore[no-untyped-call]
        options.update(parameters or {})
        client: Any = self.connection.meta.client
        client.upload_file(
            str(path),
            self.bucket_name,
            key,
            ExtraArgs=options,
            Config=self.transfer_config,
        )
        metadata: dict[str, Any] = client.head_object(Bucket=self.bucket_name, Key=key)
        if metadata["ContentLength"] != path.stat().st_size:
            raise OSError("Uploaded object size does not match the source file.")
        return str(metadata.get("VersionId", ""))

    def delete_versions(self, name: str, *, version: str = "") -> None:
        """Abort unfinished uploads and remove an exact version or all key versions.

        Ordinary S3 delete() can leave versions and delete markers behind. This
        operation permanently reclaims them, including an upload whose version
        was not recorded before a worker stopped. Neighboring keys are untouched.
        """
        key: str = self.object_key(name)
        client: Any = self.connection.meta.client
        parameters: dict[str, str] = {"Bucket": self.bucket_name, "Key": key}
        for page in client.get_paginator("list_multipart_uploads").paginate(
            Bucket=self.bucket_name, Prefix=key
        ):
            for upload in page.get("Uploads", []):
                if upload["Key"] != key:
                    continue
                try:
                    client.abort_multipart_upload(
                        **parameters, UploadId=upload["UploadId"]
                    )
                except ClientError as error:
                    if error.response.get("Error", {}).get("Code") != "NoSuchUpload":
                        raise
        if version:
            client.delete_object(**parameters, VersionId=version)
            return
        for page in client.get_paginator("list_object_versions").paginate(
            Bucket=self.bucket_name, Prefix=key
        ):
            for record in [*page.get("Versions", []), *page.get("DeleteMarkers", [])]:
                if record["Key"] == key:
                    client.delete_object(**parameters, VersionId=record["VersionId"])
        # A final key-only delete would create another marker on versioned S3.

    def url(
        self,
        name: str | None,
        parameters: dict[str, Any] | None = None,
        expire: int | None = None,
        http_method: str | None = None,
    ) -> str:
        if self.custom_domain and parameters:
            parameters = {
                _S3_DOWNLOAD_QUERY_NAMES.get(key, key): value
                for key, value in parameters.items()
            }
        browser_endpoint = getattr(settings, "AWS_S3_BROWSER_ENDPOINT_URL", None)
        if (
            name is None
            or not browser_endpoint
            or self.custom_domain
            or not self.querystring_auth
        ):
            return cast(
                "str",
                super().url(  # type: ignore[no-untyped-call]
                    name,
                    parameters=parameters,
                    expire=expire,
                    http_method=http_method,
                ),
            )

        normalized_name = self._normalize_name(  # type: ignore[no-untyped-call]
            clean_name(name)  # type: ignore[no-untyped-call]
        )
        params = parameters.copy() if parameters else {}
        params["Bucket"] = self.bucket_name
        params["Key"] = normalized_name
        if expire is None:
            expire = self.querystring_expire

        client = self._create_session().client(  # type: ignore[no-untyped-call]
            "s3",
            region_name=self.region_name,
            use_ssl=self.use_ssl,
            endpoint_url=browser_endpoint,
            config=self.client_config,
            verify=self.verify,
        )
        return cast(
            "str",
            client.generate_presigned_url(
                "get_object",
                Params=params,
                ExpiresIn=expire,
                HttpMethod=http_method,
            ),
        )


class PrivateS3Storage(BrowserFacingS3Storage):
    """Use configured CloudFront signing, otherwise private S3 presigned URLs."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)  # type: ignore[no-untyped-call]
        if self.querystring_auth and not self.cloudfront_signer:
            self.custom_domain = False


class BaseS3Storage(BrowserFacingS3Storage):
    """Base class for S3 storage configurations."""

    file_overwrite = False

    # Cache control for performance
    object_parameters = {
        "CacheControl": "public, max-age=86400",
    }

    def get_available_name(self, name: str, max_length: int | None = None) -> Any:
        """Generate unique filename to avoid conflicts."""
        # Generate unique filename
        path = Path(name)
        unique_name = f"{uuid.uuid4().hex}_{path.name}"
        return super().get_available_name(unique_name, max_length)  # type: ignore[no-untyped-call]

    if settings.DEBUG:

        def url(
            self,
            name: str | None,
            parameters: dict[str, Any] | None = None,
            expire: int | None = None,
            http_method: str | None = None,
        ) -> str:
            # Let the parent class build the URL
            url = super().url(
                name, parameters=parameters, expire=expire, http_method=http_method
            )

            # Force HTTP if using a non-SSL endpoint (useful for S3 local dev)
            if (
                isinstance(self.custom_domain, str)
                and "localhost" in self.custom_domain
            ):
                return url.replace("https://", "http://", 1)

            return url


class S3MediaStorage(BaseS3Storage, PrivateS3Storage):
    """Custom S3 storage for media files."""

    location = "media/default"  # Base location for media files
    default_acl = "private"


class PersonPhotoStorage(BaseS3Storage):
    """
    Custom S3 storage for person photos.

    Note: Requires S3 bucket policy to allow public read access to media/people/* path.
    """

    location = "media/people/photos"
    default_acl: str | None = None  # No ACL - bucket policy handles public access
    querystring_auth = False  # No signed URLs - relies on bucket policy


class AttachmentStorage(PrivateS3Storage):
    """Private S3 storage for Station Resources uploads.

    Files are stored under the "attachments/" prefix; the model's
    upload_to callable should place them into "project.id/station.id/" subfolder.
    """

    """Custom S3 storage specifically for attachments."""

    file_overwrite = BaseS3Storage.file_overwrite

    # Cache control for performance
    object_parameters = BaseS3Storage.object_parameters

    location = "attachments"
    default_acl = "private"  # Keep files private for security


class BaseGeoJSONStorage(PrivateS3Storage):
    """Private S3 storage for GeoJSON uploads."""

    # NOTE: This class can **not** inherit from BaseS3Storage because it uses a
    # different `get_available_name()` that generates a path based on the project ID
    # and commit SHA.

    file_overwrite = BaseS3Storage.file_overwrite

    # Cache control for performance
    object_parameters = BaseS3Storage.object_parameters

    default_acl = "private"


class GeoJSONStorage(PrivateS3Storage):
    """
    Files are stored under the "geojson/" prefix; the model's upload_to
    callable should place them into "project.id/commit.sha/" subfolder.
    """

    file_overwrite = BaseS3Storage.file_overwrite
    object_parameters = BaseS3Storage.object_parameters

    location = "geojson"
    default_acl = "private"


class GPSTrackStorage(PrivateS3Storage):
    """
    Files are stored under the "gps_tracks/" prefix; the model's upload_to
    callable should place them directly into the folder.
    """

    file_overwrite = BaseS3Storage.file_overwrite
    object_parameters = _PRIVATE_VECTOR_OBJECT_PARAMETERS

    location = "gps_tracks"
    default_acl = "private"


class GISLayerStorage(PrivateS3Storage):
    """
    Files are stored under the "gis_layers/" prefix; the model's upload_to
    callable should place them directly into the folder.
    """

    file_overwrite = BaseS3Storage.file_overwrite
    object_parameters = _PRIVATE_VECTOR_OBJECT_PARAMETERS

    location = "gis_layers"
    default_acl = "private"


class ExportStorage(PrivateS3Storage):
    """Private immutable export objects using the application's storage settings."""

    location = "exports"
    default_acl = None
    querystring_auth = True
    object_parameters = _PRIVATE_VECTOR_OBJECT_PARAMETERS

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.client_config = self.client_config.merge(
            Config(  # type: ignore[no-untyped-call]
                connect_timeout=5,
                read_timeout=60,
                retries={"max_attempts": 3, "mode": "standard"},
            )
        )
        self.transfer_config = TransferConfig(  # type: ignore[no-untyped-call]
            max_concurrency=2, multipart_chunksize=16 * 1024 * 1024
        )


class S3StaticStorage(S3Storage):
    """Public S3 storage for static files with long cache and URL timestamp."""

    querystring_auth = False

    # Prefix for all static assets in the bucket
    location = "staticfiles"

    # 2min caching for static assets
    object_parameters = {"CacheControl": "public, max-age=120"}
