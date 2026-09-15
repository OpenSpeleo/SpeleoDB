# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import uuid
from http import HTTPStatus
from http.client import HTTPConnection
from http.client import HTTPSConnection
from io import StringIO
from typing import TYPE_CHECKING
from unittest.mock import MagicMock
from unittest.mock import call
from unittest.mock import patch
from urllib.parse import parse_qs
from urllib.parse import urlsplit

import boto3
import pytest
from botocore.config import Config
from botocore.exceptions import ClientError
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.test import override_settings

from speleodb.background_jobs.storage import signed_archive_url
from speleodb.common.management.commands.create_s3_local_buckets import (
    LOCAL_CORS_CONFIGURATION,
)
from speleodb.utils.s3_storages import ExportStorage
from speleodb.utils.s3_storages import PersonPhotoStorage

if TYPE_CHECKING:
    from typing import Any
    from typing import Literal


TEST_SECRET_KEY = "not-a-secret"  # noqa: S105
EXPORT_RETENTION_RULE = {
    "ID": "SpeleoDBExportsRetention",
    "Status": "Enabled",
    "Filter": {"Prefix": "exports/"},
    "Expiration": {"Days": 2},
    "AbortIncompleteMultipartUpload": {"DaysAfterInitiation": 2},
}


def _client_error(code: str, operation_name: str) -> ClientError:
    return ClientError(
        {"Error": {"Code": code, "Message": "test error"}},
        operation_name,
    )


def _request_presigned_http_url(
    url: str,
    method: Literal["GET", "HEAD"],
) -> tuple[int, bytes, str | None, str | None]:
    parsed_url = urlsplit(url)
    if parsed_url.hostname is None:
        raise ValueError("Presigned URL must include a hostname.")

    connection: HTTPConnection
    if parsed_url.scheme == "http":
        connection = HTTPConnection(
            parsed_url.hostname,
            port=parsed_url.port,
            timeout=5,
        )
    elif parsed_url.scheme == "https":
        connection = HTTPSConnection(
            parsed_url.hostname,
            port=parsed_url.port,
            timeout=5,
        )
    else:
        raise ValueError("Presigned URL must use HTTP or HTTPS.")

    request_target = parsed_url.path or "/"
    if parsed_url.query:
        request_target = f"{request_target}?{parsed_url.query}"

    try:
        connection.request(
            method,
            request_target,
            headers={"Origin": "http://localhost:8000"},
        )
        response = connection.getresponse()
        return (
            response.status,
            response.read(),
            response.getheader("Access-Control-Allow-Origin"),
            response.getheader("Content-Length"),
        )
    finally:
        connection.close()


class TestPresignedHTTPURLValidation(TestCase):
    def test_non_http_scheme_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="must use HTTP or HTTPS"):
            _request_presigned_http_url("ftp://example.com/object", "GET")

    def test_missing_hostname_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="must include a hostname"):
            _request_presigned_http_url("http:///object", "HEAD")


@override_settings(
    AWS_S3_ENDPOINT_URL="http://localhost:9000",
    AWS_ACCESS_KEY_ID="access_key",
    AWS_SECRET_ACCESS_KEY=TEST_SECRET_KEY,
    AWS_STORAGE_BUCKET_NAME="unexpected-runtime-bucket",
    AWS_S3_REGION_NAME="us-east-1",
    AWS_S3_USE_SSL=False,
    AWS_S3_VERIFY=False,
)
class TestCreateS3LocalBucketsCommand(TestCase):
    def setUp(self) -> None:
        self.s3 = MagicMock()
        self.s3.get_bucket_lifecycle_configuration.return_value = {}
        self.client_patcher = patch(
            "speleodb.common.management.commands.create_s3_local_buckets.boto3.client"
        )
        self.client_factory: MagicMock = self.client_patcher.start()
        self.client_factory.return_value = self.s3

    def tearDown(self) -> None:
        self.client_patcher.stop()

    def test_static_buckets_receive_exact_policy_and_cors_rules(self) -> None:
        output = StringIO()

        call_command("create_s3_local_buckets", stdout=output)

        expected_buckets = [
            "speleodb-user-artifacts-dev",
            "speleodb-user-artifacts-test",
        ]
        assert self.s3.head_bucket.call_args_list == [
            call(Bucket=bucket_name) for bucket_name in expected_buckets
        ]
        self.s3.create_bucket.assert_not_called()
        assert self.s3.put_bucket_cors.call_args_list == [
            call(
                Bucket=bucket_name,
                CORSConfiguration=LOCAL_CORS_CONFIGURATION,
            )
            for bucket_name in expected_buckets
        ]

        assert self.s3.put_bucket_policy.call_count == len(expected_buckets)
        for bucket_name, policy_call in zip(
            expected_buckets,
            self.s3.put_bucket_policy.call_args_list,
            strict=True,
        ):
            assert policy_call.kwargs["Bucket"] == bucket_name
            policy = json.loads(policy_call.kwargs["Policy"])
            assert policy == {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Sid": "AllowPublicReadForPersonPhotos",
                        "Effect": "Allow",
                        "Principal": "*",
                        "Action": "s3:GetObject",
                        "Resource": (
                            f"arn:aws:s3:::{bucket_name}/media/people/photos/*"
                        ),
                    }
                ],
            }

        self.client_factory.assert_called_once_with(
            "s3",
            endpoint_url="http://localhost:9000",
            aws_access_key_id="access_key",
            aws_secret_access_key=TEST_SECRET_KEY,
            region_name="us-east-1",
            use_ssl=False,
            verify=False,
        )

    def test_missing_bucket_is_created(self) -> None:
        self.s3.head_bucket.side_effect = [
            _client_error("404", "HeadBucket"),
            None,
        ]

        call_command("create_s3_local_buckets")

        self.s3.create_bucket.assert_called_once_with(
            Bucket="speleodb-user-artifacts-dev"
        )

    def test_non_missing_head_error_is_reported_without_creating_bucket(self) -> None:
        self.s3.head_bucket.side_effect = _client_error("403", "HeadBucket")

        with pytest.raises(
            CommandError,
            match="Failed to inspect bucket 'speleodb-user-artifacts-dev'",
        ):
            call_command("create_s3_local_buckets")

        self.s3.create_bucket.assert_not_called()
        self.s3.put_bucket_policy.assert_not_called()
        self.s3.put_bucket_cors.assert_not_called()

    @override_settings(AWS_S3_ENDPOINT_URL=None)
    def test_missing_custom_endpoint_is_rejected_before_client_creation(self) -> None:
        with pytest.raises(
            CommandError,
            match="AWS_S3_ENDPOINT_URL must be configured",
        ):
            call_command("create_s3_local_buckets")

        self.client_factory.assert_not_called()

    def test_policy_error_names_the_affected_bucket(self) -> None:
        self.s3.put_bucket_policy.side_effect = _client_error(
            "AccessDenied",
            "PutBucketPolicy",
        )

        with pytest.raises(
            CommandError,
            match="Failed to apply policy to bucket 'speleodb-user-artifacts-dev'",
        ):
            call_command("create_s3_local_buckets")

        self.s3.put_bucket_cors.assert_not_called()

    def test_cors_error_names_the_affected_bucket(self) -> None:
        self.s3.put_bucket_cors.side_effect = _client_error(
            "NotImplemented",
            "PutBucketCors",
        )

        with pytest.raises(
            CommandError,
            match=(
                "Failed to apply CORS rules to bucket 'speleodb-user-artifacts-dev'"
            ),
        ):
            call_command("create_s3_local_buckets")

    def test_missing_lifecycle_installs_export_retention(
        self,
    ) -> None:
        self.s3.get_bucket_lifecycle_configuration.side_effect = _client_error(
            "NoSuchLifecycleConfiguration", "GetBucketLifecycleConfiguration"
        )

        call_command("create_s3_local_buckets")

        assert self.s3.put_bucket_lifecycle_configuration.call_args_list == [
            call(
                Bucket=bucket,
                LifecycleConfiguration={"Rules": [EXPORT_RETENTION_RULE]},
            )
            for bucket in [
                "speleodb-user-artifacts-dev",
                "speleodb-user-artifacts-test",
            ]
        ]

    def test_lifecycle_preserves_unrelated_rules_and_transition_minimum(self) -> None:
        unrelated: dict[str, Any] = {
            "ID": "OtherRetention",
            "Status": "Enabled",
            "Filter": {"Prefix": "unrelated/"},
            "Expiration": {"Days": 30},
        }
        existing: dict[str, Any] = {
            "Rules": [unrelated],
            "TransitionDefaultMinimumObjectSize": "varies_by_storage_class",
            "ResponseMetadata": {"HTTPStatusCode": 200},
        }
        original: str = json.dumps(existing)
        self.s3.get_bucket_lifecycle_configuration.return_value = existing

        call_command("create_s3_local_buckets")

        for lifecycle_call in self.s3.put_bucket_lifecycle_configuration.call_args_list:
            assert lifecycle_call.kwargs["LifecycleConfiguration"] == {
                "Rules": [unrelated, EXPORT_RETENTION_RULE]
            }
            assert (
                lifecycle_call.kwargs["TransitionDefaultMinimumObjectSize"]
                == "varies_by_storage_class"
            )
        assert json.dumps(existing) == original

    def test_lifecycle_removes_old_export_version_retention(self) -> None:
        previous_rule: dict[str, Any] = {
            **EXPORT_RETENTION_RULE,
            "NoncurrentVersionExpiration": {"NoncurrentDays": 2},
        }
        self.s3.get_bucket_lifecycle_configuration.return_value = {
            "Rules": [previous_rule]
        }

        call_command("create_s3_local_buckets")

        for lifecycle_call in self.s3.put_bucket_lifecycle_configuration.call_args_list:
            assert lifecycle_call.kwargs["LifecycleConfiguration"] == {
                "Rules": [EXPORT_RETENTION_RULE]
            }
        assert self.s3.put_bucket_lifecycle_configuration.called

    def test_repeated_setup_does_not_rewrite_unchanged_lifecycle(self) -> None:
        call_command("create_s3_local_buckets")
        initial_writes: int = self.s3.put_bucket_lifecycle_configuration.call_count
        assert initial_writes > 0
        self.s3.get_bucket_lifecycle_configuration.return_value = {
            "Rules": [EXPORT_RETENTION_RULE]
        }

        call_command("create_s3_local_buckets")

        assert self.s3.put_bucket_lifecycle_configuration.call_count == initial_writes

    def test_lifecycle_inspection_error_names_the_affected_bucket(self) -> None:
        self.s3.get_bucket_lifecycle_configuration.side_effect = _client_error(
            "AccessDenied", "GetBucketLifecycleConfiguration"
        )

        with pytest.raises(
            CommandError,
            match=(
                "Failed to inspect lifecycle rules for bucket "
                "'speleodb-user-artifacts-dev'"
            ),
        ):
            call_command("create_s3_local_buckets")

        self.s3.put_bucket_lifecycle_configuration.assert_not_called()

    def test_lifecycle_write_error_names_the_affected_bucket(self) -> None:
        self.s3.put_bucket_lifecycle_configuration.side_effect = _client_error(
            "NotImplemented", "PutBucketLifecycleConfiguration"
        )

        with pytest.raises(
            CommandError,
            match=(
                "Failed to apply lifecycle rules to bucket "
                "'speleodb-user-artifacts-dev'"
            ),
        ):
            call_command("create_s3_local_buckets")

    def test_lifecycle_rejects_export_rule_id_used_outside_exports(self) -> None:
        self.s3.get_bucket_lifecycle_configuration.return_value = {
            "Rules": [{**EXPORT_RETENTION_RULE, "Filter": {"Prefix": "unrelated/"}}]
        }

        with pytest.raises(CommandError, match="outside the exports prefix"):
            call_command("create_s3_local_buckets")

        self.s3.put_bucket_lifecycle_configuration.assert_not_called()


@pytest.mark.skip_if_lighttest
class TestRustFSCORSIntegration(TestCase):
    def test_setup_keeps_exports_private_and_person_photos_public(self) -> None:
        call_command("create_s3_local_buckets")
        export_storage: ExportStorage = ExportStorage()
        photo_storage: PersonPhotoStorage = PersonPhotoStorage()
        export_name: str = f"setup-access-{uuid.uuid4()}.zip"
        photo_name: str = f"setup-access-{uuid.uuid4()}.jpg"
        private_payload: bytes = b"private export contents"
        public_payload: bytes = b"public photo contents"
        saved_export: str = ""
        saved_photo: str = ""
        try:
            saved_export = export_storage.save(
                export_name, ContentFile(private_payload)
            )
            saved_photo = photo_storage.save(photo_name, ContentFile(public_payload))
            signed_url: str = signed_archive_url(
                key=export_storage.object_key(saved_export),
                expires=60,
            )
            signed_status, signed_body, allow_origin, _ = _request_presigned_http_url(
                signed_url, "GET"
            )
            assert signed_status == HTTPStatus.OK
            assert signed_body == private_payload
            assert allow_origin == "*"
            unsigned_url: str = urlsplit(signed_url)._replace(query="").geturl()
            unsigned_status, _, _, _ = _request_presigned_http_url(unsigned_url, "GET")
            assert unsigned_status == HTTPStatus.FORBIDDEN
            photo_url: str = photo_storage.url(saved_photo)
            assert not urlsplit(photo_url).query
            photo_status, photo_body, _, _ = _request_presigned_http_url(
                photo_url, "GET"
            )
            assert photo_status == HTTPStatus.OK
            assert photo_body == public_payload
        finally:
            if saved_export:
                export_storage.delete_file(saved_export)
            if saved_photo:
                photo_storage.delete_file(saved_photo)

    def test_presigned_get_and_head_responses_allow_browser_origin(self) -> None:
        call_command("create_s3_local_buckets")
        s3: Any = boto3.client(
            "s3",
            endpoint_url=settings.AWS_S3_ENDPOINT_URL,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_S3_REGION_NAME,
            use_ssl=settings.AWS_S3_USE_SSL,
            verify=settings.AWS_S3_VERIFY,
            config=Config(
                signature_version=settings.AWS_S3_SIGNATURE_VERSION,
                s3={"addressing_style": settings.AWS_S3_ADDRESSING_STYLE},
            ),
        )
        object_key = f"integration-tests/{uuid.uuid4()}.geojson"
        payload = b'{"type":"FeatureCollection","features":[]}'
        uploaded = False

        try:
            s3.put_object(
                Bucket=settings.AWS_STORAGE_BUCKET_NAME,
                Key=object_key,
                Body=payload,
                ContentType="application/geo+json",
            )
            uploaded = True

            get_url: str = s3.generate_presigned_url(
                "get_object",
                Params={
                    "Bucket": settings.AWS_STORAGE_BUCKET_NAME,
                    "Key": object_key,
                },
                ExpiresIn=60,
            )
            assert parse_qs(urlsplit(get_url).query)["X-Amz-Algorithm"] == [
                "AWS4-HMAC-SHA256"
            ]
            get_status, get_body, get_allow_origin, _ = _request_presigned_http_url(
                get_url,
                "GET",
            )
            assert get_status == HTTPStatus.OK
            assert get_body == payload
            assert get_allow_origin == "*"

            head_url: str = s3.generate_presigned_url(
                "head_object",
                Params={
                    "Bucket": settings.AWS_STORAGE_BUCKET_NAME,
                    "Key": object_key,
                },
                ExpiresIn=60,
            )
            (
                head_status,
                head_body,
                head_allow_origin,
                head_content_length,
            ) = _request_presigned_http_url(
                head_url,
                "HEAD",
            )
            assert head_status == HTTPStatus.OK
            assert head_body == b""
            assert head_allow_origin == "*"
            assert head_content_length is not None
            assert int(head_content_length) == len(payload)
        finally:
            if uploaded:
                s3.delete_object(
                    Bucket=settings.AWS_STORAGE_BUCKET_NAME,
                    Key=object_key,
                )
