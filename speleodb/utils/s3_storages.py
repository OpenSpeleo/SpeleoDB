# -*- coding: utf-8 -*-

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any
from typing import cast

from django.conf import settings
from storages.backends.s3 import S3Storage
from storages.utils import clean_name

# ---------------------------------------------------------------------------
# CloudFront signed-URL support
# ---------------------------------------------------------------------------
# In production the CloudFront signing keys are present, so private storage
# classes keep the custom domain and let django-storages generate CloudFront
# signed URLs.  In local dev (S3 bucket) there are no CloudFront keys, so private
# storage classes disable the custom domain to fall back to S3 presigned URLs.
_CLOUDFRONT_SIGNING_ENABLED: bool = bool(
    getattr(settings, "AWS_CLOUDFRONT_KEY", None)
    and getattr(settings, "AWS_CLOUDFRONT_KEY_ID", None)
)

# Custom domain to use for private storage classes that need signed URLs.
#   Production (CloudFront configured) → CloudFront domain → CloudFront signed URLs
#   Local dev  (no CloudFront)         → False             → S3 presigned URLs
_PRIVATE_CUSTOM_DOMAIN = (
    settings.AWS_S3_CUSTOM_DOMAIN
    if _CLOUDFRONT_SIGNING_ENABLED
    or not getattr(settings, "AWS_QUERYSTRING_AUTH", True)
    else False
)
_PRIVATE_VECTOR_OBJECT_PARAMETERS = {"CacheControl": "private, no-store"}


class BrowserFacingS3Storage(S3Storage):
    """Use a separate endpoint only when signing URLs for a local browser."""

    bucket_name: str
    client_config: Any
    custom_domain: str | bool | None
    querystring_auth: bool
    querystring_expire: int
    region_name: str | None
    use_ssl: bool
    verify: Any

    def url(
        self,
        name: str | None,
        parameters: dict[str, Any] | None = None,
        expire: int | None = None,
        http_method: str | None = None,
    ) -> str:
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


class BaseS3Storage(BrowserFacingS3Storage):
    """Base class for S3 storage configurations."""

    bucket_name = settings.AWS_STORAGE_BUCKET_NAME
    custom_domain = settings.AWS_S3_CUSTOM_DOMAIN  # Use Cloudfront/S3 Domain
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


class S3MediaStorage(BaseS3Storage):
    """Custom S3 storage for media files."""

    location = "media/default"  # Base location for media files
    default_acl = "private"
    # Use CloudFront signed URLs (production) or S3 presigned URLs (local dev)
    custom_domain = _PRIVATE_CUSTOM_DOMAIN


class PersonPhotoStorage(BaseS3Storage):
    """
    Custom S3 storage for person photos.

    Note: Requires S3 bucket policy to allow public read access to media/people/* path.
    """

    location = "media/people/photos"
    default_acl: str | None = None  # No ACL - bucket policy handles public access
    querystring_auth = False  # No signed URLs - relies on bucket policy


class AttachmentStorage(BrowserFacingS3Storage):
    """Private S3 storage for Station Resources uploads.

    Files are stored under the "attachments/" prefix; the model's
    upload_to callable should place them into "project.id/station.id/" subfolder.
    """

    """Custom S3 storage specifically for attachments."""

    bucket_name = BaseS3Storage.bucket_name
    file_overwrite = BaseS3Storage.file_overwrite

    # Cache control for performance
    object_parameters = BaseS3Storage.object_parameters

    location = "attachments"
    default_acl = "private"  # Keep files private for security

    # Use CloudFront signed URLs (production) or S3 presigned URLs (local dev)
    custom_domain = _PRIVATE_CUSTOM_DOMAIN


class BaseGeoJSONStorage(BrowserFacingS3Storage):
    """Private S3 storage for GeoJSON uploads."""

    # NOTE: This class can **not** inherit from BaseS3Storage because it uses a
    # different `get_available_name()` that generates a path based on the project ID
    # and commit SHA.

    bucket_name = BaseS3Storage.bucket_name
    file_overwrite = BaseS3Storage.file_overwrite

    # Cache control for performance
    object_parameters = BaseS3Storage.object_parameters

    default_acl = "private"

    # Use CloudFront signed URLs (production) or S3 presigned URLs (local dev)
    custom_domain = _PRIVATE_CUSTOM_DOMAIN


class GeoJSONStorage(BrowserFacingS3Storage):
    """
    Files are stored under the "geojson/" prefix; the model's upload_to
    callable should place them into "project.id/commit.sha/" subfolder.
    """

    bucket_name = BaseS3Storage.bucket_name
    file_overwrite = BaseS3Storage.file_overwrite
    object_parameters = BaseS3Storage.object_parameters

    location = "geojson"
    default_acl = "private"

    # Use CloudFront signed URLs (production) or S3 presigned URLs (local dev)
    custom_domain = _PRIVATE_CUSTOM_DOMAIN


class GPSTrackStorage(BrowserFacingS3Storage):
    """
    Files are stored under the "gps_tracks/" prefix; the model's upload_to
    callable should place them directly into the folder.
    """

    bucket_name = BaseS3Storage.bucket_name
    file_overwrite = BaseS3Storage.file_overwrite
    object_parameters = _PRIVATE_VECTOR_OBJECT_PARAMETERS

    location = "gps_tracks"
    default_acl = "private"

    # Use CloudFront signed URLs (production) or S3 presigned URLs (local dev)
    custom_domain = _PRIVATE_CUSTOM_DOMAIN


class GISLayerStorage(BrowserFacingS3Storage):
    """
    Files are stored under the "gis_layers/" prefix; the model's upload_to
    callable should place them directly into the folder.
    """

    bucket_name = BaseS3Storage.bucket_name
    file_overwrite = BaseS3Storage.file_overwrite
    object_parameters = _PRIVATE_VECTOR_OBJECT_PARAMETERS

    location = "gis_layers"
    default_acl = "private"

    # Use CloudFront signed URLs (production) or S3 presigned URLs (local dev)
    custom_domain = _PRIVATE_CUSTOM_DOMAIN


class S3StaticStorage(S3Storage):
    """Public S3 storage for static files with long cache and URL timestamp."""

    querystring_auth = False

    # Prefix for all static assets in the bucket
    location = "staticfiles"

    # 2min caching for static assets
    object_parameters = {"CacheControl": "public, max-age=120"}
