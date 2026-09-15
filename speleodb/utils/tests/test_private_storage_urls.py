"""Exercise real signing without contacting S3 or CloudFront."""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from importlib import import_module
from secrets import token_hex
from typing import TYPE_CHECKING
from typing import Any
from urllib.parse import parse_qs
from urllib.parse import quote
from urllib.parse import urlsplit
from urllib.parse import urlunsplit

import pytest
from django.test import override_settings
from django.utils import timezone

from speleodb.background_jobs.storage import signed_archive_url
from speleodb.utils.s3_storages import AttachmentStorage
from speleodb.utils.s3_storages import BaseGeoJSONStorage
from speleodb.utils.s3_storages import ExportStorage
from speleodb.utils.s3_storages import GeoJSONStorage
from speleodb.utils.s3_storages import GISLayerStorage
from speleodb.utils.s3_storages import GPSTrackStorage
from speleodb.utils.s3_storages import PersonPhotoStorage
from speleodb.utils.s3_storages import PrivateS3Storage
from speleodb.utils.s3_storages import PublicS3Storage
from speleodb.utils.s3_storages import S3MediaStorage
from speleodb.utils.s3_storages import S3StaticStorage

if TYPE_CHECKING:
    from collections.abc import Callable
    from collections.abc import Iterator
    from types import ModuleType
    from urllib.parse import SplitResult


TEST_BUCKET: str = "storage-url-tests"
CLOUDFRONT_DOMAIN: str = "static.speleodb.org"
CLOUDFRONT_KEY_ID: str = "storage-url-test-key"
URL_TTL: int = 173
PRIVATE_BACKENDS: tuple[tuple[type[PrivateS3Storage], str], ...] = (
    (PrivateS3Storage, ""),
    (S3MediaStorage, "media/default"),
    (AttachmentStorage, "attachments"),
    (BaseGeoJSONStorage, ""),
    (GeoJSONStorage, "geojson"),
    (GPSTrackStorage, "gps_tracks"),
    (GISLayerStorage, "gis_layers"),
    (ExportStorage, "exports"),
)
PUBLIC_BACKENDS: tuple[tuple[type[PublicS3Storage], str], ...] = (
    (PersonPhotoStorage, "media/people/photos"),
    (S3StaticStorage, "staticfiles"),
)
EXPORT_KEYS: tuple[str, ...] = (
    "exports/user/job/attempt/archive.zip",
    "exports/attempt.zip",
)


@dataclass(frozen=True)
class SigningKey:
    private_pem: str
    verify_signature: Callable[[bytes, bytes], None]


@pytest.fixture(scope="module")
def signing_key() -> SigningKey:
    # Local installs do not include the already-defined production crypto extra.
    # Keep local S3 tests active and verify real CloudFront signing when present.
    pytest.importorskip(
        "cryptography",
        reason="CloudFront signing requires the existing production dependency extra.",
        exc_type=ModuleNotFoundError,
    )
    rsa: ModuleType = import_module("cryptography.hazmat.primitives.asymmetric.rsa")
    serialization: ModuleType = import_module(
        "cryptography.hazmat.primitives.serialization"
    )
    padding: ModuleType = import_module(
        "cryptography.hazmat.primitives.asymmetric.padding"
    )
    hashes: ModuleType = import_module("cryptography.hazmat.primitives.hashes")
    key: Any = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem: str = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("ascii")

    def verify_signature(policy: bytes, signature: bytes) -> None:
        key.public_key().verify(
            signature,
            policy,
            padding.PKCS1v15(),
            hashes.SHA1(),
        )

    return SigningKey(private_pem=pem, verify_signature=verify_signature)


@pytest.fixture(autouse=True)
def _storage_url_settings() -> Iterator[None]:
    with override_settings(
        AWS_S3_ACCESS_KEY_ID="storage-url-tests",
        AWS_S3_SECRET_ACCESS_KEY=token_hex(32),
        AWS_SESSION_TOKEN=None,
        AWS_SECURITY_TOKEN=None,
        AWS_S3_SESSION_PROFILE=None,
        AWS_STORAGE_BUCKET_NAME=TEST_BUCKET,
        AWS_CLOUDFRONT_KEY=None,
        AWS_CLOUDFRONT_KEY_ID=None,
        AWS_S3_CUSTOM_DOMAIN=f"localhost:9000/{TEST_BUCKET}",
        AWS_S3_ENDPOINT_URL="http://rustfs:9000",
        AWS_S3_BROWSER_ENDPOINT_URL="http://localhost:9000",
        AWS_S3_ADDRESSING_STYLE="path",
        AWS_S3_SIGNATURE_VERSION="s3v4",
        AWS_S3_CLIENT_CONFIG=None,
        AWS_S3_REGION_NAME="us-east-1",
        AWS_S3_USE_SSL=False,
        AWS_S3_VERIFY=False,
        AWS_QUERYSTRING_AUTH=True,
        AWS_QUERYSTRING_EXPIRE=URL_TTL,
    ):
        yield


@pytest.fixture
def cloudfront_settings(signing_key: SigningKey) -> Iterator[None]:
    with override_settings(
        AWS_CLOUDFRONT_KEY=signing_key.private_pem,
        AWS_CLOUDFRONT_KEY_ID=CLOUDFRONT_KEY_ID,
        AWS_S3_CUSTOM_DOMAIN=CLOUDFRONT_DOMAIN,
        AWS_S3_ENDPOINT_URL=None,
        AWS_S3_BROWSER_ENDPOINT_URL=None,
        AWS_S3_USE_SSL=True,
        AWS_S3_VERIFY=True,
    ):
        yield


def assert_cloudfront_signature(
    url: str,
    signing_key: SigningKey,
    *,
    started_at: int,
    expires: int = URL_TTL,
) -> dict[str, list[str]]:
    """Verify the canned policy independently with the ephemeral public key."""
    parsed: SplitResult = urlsplit(url)
    query: dict[str, list[str]] = parse_qs(parsed.query)
    assert parsed.scheme == "https"
    assert parsed.netloc == CLOUDFRONT_DOMAIN
    assert query["Key-Pair-Id"] == [CLOUDFRONT_KEY_ID]
    assert "X-Amz-Signature" not in query
    expiry: int = int(query["Expires"][0])
    assert started_at + expires <= expiry <= int(timezone.now().timestamp()) + expires

    signing_fields: set[str] = {"Expires", "Signature", "Key-Pair-Id"}
    resource_query: str = "&".join(
        part
        for part in parsed.query.split("&")
        if part.split("=", maxsplit=1)[0] not in signing_fields
    )
    resource: str = urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path, resource_query, "")
    )
    policy: bytes = json.dumps(
        {
            "Statement": [
                {
                    "Resource": resource,
                    "Condition": {"DateLessThan": {"AWS:EpochTime": expiry}},
                }
            ]
        },
        separators=(",", ":"),
    ).encode("utf-8")
    signature: bytes = base64.b64decode(
        query["Signature"][0].translate(str.maketrans("-~_", "+/="))
    )
    signing_key.verify_signature(policy, signature)
    return query


@pytest.mark.usefixtures("cloudfront_settings")
@pytest.mark.parametrize(("backend", "prefix"), PRIVATE_BACKENDS)
def test_private_backends_use_verified_cloudfront_signatures(
    backend: type[PrivateS3Storage],
    prefix: str,
    signing_key: SigningKey,
) -> None:
    storage: PrivateS3Storage = backend()
    started_at: int = int(timezone.now().timestamp())
    url: str = storage.url("folder/élève map.zip", expire=URL_TTL)

    assert storage.bucket_name == TEST_BUCKET
    expected_key: str = "/".join(
        part for part in (prefix, "folder/élève map.zip") if part
    )
    assert urlsplit(url).path == f"/{quote(expected_key)}"
    assert_cloudfront_signature(url, signing_key, started_at=started_at)


@pytest.mark.parametrize(("backend", "prefix"), PRIVATE_BACKENDS)
@pytest.mark.parametrize("browser_endpoint", ["http://localhost:9000", None])
def test_private_backends_use_local_sigv4_with_the_correct_endpoint(
    backend: type[PrivateS3Storage], prefix: str, browser_endpoint: str | None
) -> None:
    with override_settings(AWS_S3_BROWSER_ENDPOINT_URL=browser_endpoint):
        storage: PrivateS3Storage = backend()
        url: str = storage.url("folder/archive.zip", expire=URL_TTL)

    parsed: SplitResult = urlsplit(url)
    query: dict[str, list[str]] = parse_qs(parsed.query)
    assert not storage.custom_domain
    assert storage.bucket_name == TEST_BUCKET
    assert parsed.scheme == "http"
    assert parsed.netloc == ("localhost:9000" if browser_endpoint else "rustfs:9000")
    expected_key: str = "/".join(
        part for part in (TEST_BUCKET, prefix, "folder/archive.zip") if part
    )
    assert parsed.path == f"/{expected_key}"
    assert query["X-Amz-Algorithm"] == ["AWS4-HMAC-SHA256"]
    assert query["X-Amz-Expires"] == [str(URL_TTL)]
    assert query["X-Amz-Signature"]
    assert "Key-Pair-Id" not in query


@pytest.mark.usefixtures("cloudfront_settings")
def test_cloudfront_translates_download_parameters_before_signing(
    signing_key: SigningKey,
) -> None:
    parameters: dict[str, str] = {
        "ResponseContentDisposition": 'attachment; filename="survey & notes.zip"',
        "ResponseCacheControl": "private, no-store",
    }
    original: dict[str, str] = parameters.copy()
    started_at: int = int(timezone.now().timestamp())
    url: str = ExportStorage().url("archive.zip", parameters=parameters)

    query: dict[str, list[str]] = assert_cloudfront_signature(
        url, signing_key, started_at=started_at
    )
    assert parameters == original
    assert query["response-content-disposition"] == [
        original["ResponseContentDisposition"]
    ]
    assert query["response-cache-control"] == [original["ResponseCacheControl"]]
    assert not set(parameters).intersection(query)


@pytest.mark.parametrize("browser_endpoint", ["http://localhost:9000", None])
def test_local_download_parameters_keep_boto_semantics_and_callers_values(
    browser_endpoint: str | None,
) -> None:
    parameters: dict[str, str] = {
        "ResponseContentDisposition": 'attachment; filename="survey & notes.zip"',
        "ResponseCacheControl": "private, no-store",
    }
    original: dict[str, str] = parameters.copy()
    with override_settings(AWS_S3_BROWSER_ENDPOINT_URL=browser_endpoint):
        url: str = ExportStorage().url("archive.zip", parameters=parameters)

    query: dict[str, list[str]] = parse_qs(urlsplit(url).query)
    assert parameters == original
    assert query["response-content-disposition"] == [
        original["ResponseContentDisposition"]
    ]
    assert query["response-cache-control"] == [original["ResponseCacheControl"]]
    assert query["X-Amz-Expires"] == [str(URL_TTL)]
    assert query["X-Amz-Signature"]


@pytest.mark.usefixtures("cloudfront_settings")
@pytest.mark.parametrize("key", EXPORT_KEYS)
def test_export_helper_uses_only_cloudfront_signature_parameters(
    key: str, signing_key: SigningKey
) -> None:
    started_at: int = int(timezone.now().timestamp())
    url: str = signed_archive_url(key=key, expires=URL_TTL)

    query: dict[str, list[str]] = assert_cloudfront_signature(
        url, signing_key, started_at=started_at
    )
    assert urlsplit(url).path == f"/{key}"
    assert set(query) == {"Expires", "Signature", "Key-Pair-Id"}


@pytest.mark.parametrize("key", EXPORT_KEYS)
def test_export_helper_uses_only_local_signature_parameters(key: str) -> None:
    url: str = signed_archive_url(key=key, expires=URL_TTL)

    parsed: SplitResult = urlsplit(url)
    query: dict[str, list[str]] = parse_qs(parsed.query)
    assert parsed.netloc == "localhost:9000"
    assert parsed.path == f"/{TEST_BUCKET}/{key}"
    assert all(parameter.startswith("X-Amz-") for parameter in query)
    assert query["X-Amz-Expires"] == [str(URL_TTL)]
    assert query["X-Amz-Signature"]


@pytest.mark.usefixtures("cloudfront_settings")
@pytest.mark.parametrize(("backend", "prefix"), PUBLIC_BACKENDS)
def test_public_backends_keep_unsigned_cloudfront_urls(
    backend: type[PublicS3Storage], prefix: str
) -> None:
    storage: PublicS3Storage = backend()
    url: str = storage.url("test.jpg")

    assert not storage.querystring_auth
    assert url == f"https://{CLOUDFRONT_DOMAIN}/{prefix}/test.jpg"


@pytest.mark.parametrize(("backend", "prefix"), PUBLIC_BACKENDS)
def test_public_backends_keep_unsigned_local_urls(
    backend: type[PublicS3Storage], prefix: str
) -> None:
    storage: PublicS3Storage = backend()
    parsed: SplitResult = urlsplit(storage.url("test.jpg"))

    assert not storage.querystring_auth
    assert parsed.scheme == "http"
    assert parsed.netloc == "localhost:9000"
    assert parsed.path == f"/{TEST_BUCKET}/{prefix}/test.jpg"
    assert not parsed.query


@pytest.mark.parametrize(("backend", "prefix"), PUBLIC_BACKENDS)
@pytest.mark.parametrize(
    "endpoint", ["http://127.0.0.1:9000", "https://storage.example.test:9443"]
)
@pytest.mark.parametrize("use_browser_endpoint", [False, True])
def test_public_urls_use_matching_endpoint_scheme(
    backend: type[PublicS3Storage],
    prefix: str,
    endpoint: str,
    *,
    use_browser_endpoint: bool,
) -> None:
    configured_endpoint: SplitResult = urlsplit(endpoint)
    with override_settings(
        DEBUG=False,
        AWS_S3_CUSTOM_DOMAIN=f"{configured_endpoint.netloc}/{TEST_BUCKET}",
        AWS_S3_BROWSER_ENDPOINT_URL=endpoint if use_browser_endpoint else None,
        AWS_S3_ENDPOINT_URL="http://rustfs:9000" if use_browser_endpoint else endpoint,
    ):
        storage: PublicS3Storage = backend()
        parsed: SplitResult = urlsplit(storage.url("test.jpg"))

    assert parsed.scheme == configured_endpoint.scheme
    assert parsed.netloc == configured_endpoint.netloc
    assert parsed.path == f"/{TEST_BUCKET}/{prefix}/test.jpg"
    assert not parsed.query


@pytest.mark.parametrize(("backend", "prefix"), PUBLIC_BACKENDS)
def test_local_browser_endpoint_does_not_change_cloudfront_protocol(
    backend: type[PublicS3Storage], prefix: str
) -> None:
    with override_settings(
        AWS_S3_CUSTOM_DOMAIN=CLOUDFRONT_DOMAIN,
        AWS_S3_BROWSER_ENDPOINT_URL="http://localhost:9000",
    ):
        storage: PublicS3Storage = backend()
        url: str = storage.url("test.jpg")

    assert url == f"https://{CLOUDFRONT_DOMAIN}/{prefix}/test.jpg"
