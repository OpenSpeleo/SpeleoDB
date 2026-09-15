"""Pure configuration builders preserve unrelated S3 policy and lifecycle data."""

from __future__ import annotations

import copy
from io import StringIO
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock
from unittest.mock import patch

import orjson
import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from speleodb.background_jobs.bucket_configuration import APPLICATION_ACTIONS
from speleodb.background_jobs.bucket_configuration import (
    APPLICATION_POLICY_STATEMENT_ID,
)
from speleodb.background_jobs.bucket_configuration import CLOUDFRONT_POLICY_STATEMENT_ID
from speleodb.background_jobs.bucket_configuration import LIFECYCLE_RULE_ID
from speleodb.background_jobs.bucket_configuration import POLICY_STATEMENT_ID
from speleodb.background_jobs.bucket_configuration import (
    SHARED_CLOUDFRONT_POLICY_STATEMENT_ID,
)
from speleodb.background_jobs.bucket_configuration import BucketConfiguration
from speleodb.background_jobs.bucket_configuration import BucketConfigurationError
from speleodb.background_jobs.bucket_configuration import build_bucket_configuration
from speleodb.background_jobs.bucket_configuration import build_export_lifecycle
from speleodb.background_jobs.bucket_configuration import validate_readers
from speleodb.background_jobs.management.commands.configure_export_bucket import (
    read_bucket_configuration,
)

READER: str = "arn:aws:iam::123456789012:role/speleodb-web"
DISTRIBUTION: str = "arn:aws:cloudfront::123456789012:distribution/E1EXAMPLE"


def _current() -> BucketConfiguration:
    return BucketConfiguration(
        policy={
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "PublicPhotos",
                    "Effect": "Allow",
                    "Principal": "*",
                    "Action": "s3:GetObject",
                    "Resource": "arn:aws:s3:::test-bucket/media/people/*",
                }
            ],
        },
        lifecycle={
            "Rules": [
                {
                    "ID": "Attachments",
                    "Status": "Enabled",
                    "Filter": {"Prefix": "attachments/"},
                    "Expiration": {"Days": 365},
                }
            ]
        },
        object_lock={},
        transition_default_minimum_object_size="all_storage_classes_128K",
    )


def _shared_current() -> BucketConfiguration:
    current: BucketConfiguration = _current()
    current.policy["Statement"] = [
        {
            "Sid": APPLICATION_POLICY_STATEMENT_ID,
            "Effect": "Allow",
            "Principal": {"AWS": READER},
            "Action": [
                "s3:PutObject",
                "s3:GetObjectAcl",
                "s3:GetObject",
                "s3:ListBucket",
                "s3:DeleteObject",
                "s3:PutObjectAcl",
            ],
            "Resource": ["arn:aws:s3:::test-bucket/*", "arn:aws:s3:::test-bucket"],
        },
        {
            "Sid": "DenyInsecureConnections",
            "Effect": "Deny",
            "Principal": "*",
            "Action": "s3:*",
            "Resource": ["arn:aws:s3:::test-bucket", "arn:aws:s3:::test-bucket/*"],
            "Condition": {"Bool": {"aws:SecureTransport": "false"}},
        },
        {
            "Sid": SHARED_CLOUDFRONT_POLICY_STATEMENT_ID,
            "Effect": "Allow",
            "Principal": {"Service": "cloudfront.amazonaws.com"},
            "Action": "s3:GetObject",
            "Resource": "arn:aws:s3:::test-bucket/*",
            "Condition": {"ArnLike": {"AWS:SourceArn": DISTRIBUTION}},
        },
    ]
    return current


def test_existing_three_shared_statements_are_extended_in_place() -> None:
    before: BucketConfiguration = _shared_current()
    snapshot: dict[str, Any] = copy.deepcopy(before.as_dict())
    expected: dict[str, Any] = copy.deepcopy(before.policy)
    expected["Statement"][0]["Action"].extend(
        [
            "s3:AbortMultipartUpload",
            "s3:ListBucketMultipartUploads",
        ]
    )
    after: BucketConfiguration = build_bucket_configuration(
        bucket="test-bucket",
        reader_arns=[READER],
        current=before,
        cloudfront_distribution_arn=DISTRIBUTION,
    )
    assert after.policy == expected
    assert before.as_dict() == snapshot
    repeated: BucketConfiguration = build_bucket_configuration(
        bucket="test-bucket",
        reader_arns=[READER],
        current=after,
        cloudfront_distribution_arn=DISTRIBUTION,
    )
    assert repeated.fingerprint == after.fingerprint


def test_shared_policy_removes_only_its_obsolete_version_permissions() -> None:
    before: BucketConfiguration = _shared_current()
    before.policy["Statement"][0]["Action"].extend(
        [
            "s3:GetObjectVersion",
            "s3:DeleteObjectVersion",
            "s3:ListBucketVersions",
            "s3:GetObjectTagging",
        ]
    )
    before.policy["Statement"][2]["Action"] = ["s3:GetObject", "s3:GetObjectVersion"]
    unrelated: dict[str, Any] = {
        "Sid": "OtherArchiveReader",
        "Effect": "Allow",
        "Principal": {"AWS": "arn:aws:iam::123456789012:role/archive-reader"},
        "Action": "s3:GetObjectVersion",
        "Resource": "arn:aws:s3:::test-bucket/archives/*",
    }
    before.policy["Statement"].append(unrelated)
    after: BucketConfiguration = build_bucket_configuration(
        bucket="test-bucket",
        reader_arns=[READER],
        current=before,
        cloudfront_distribution_arn=DISTRIBUTION,
    )
    assert after.policy["Statement"][0]["Action"] == [
        *APPLICATION_ACTIONS[:6],
        "s3:GetObjectTagging",
        "s3:AbortMultipartUpload",
        "s3:ListBucketMultipartUploads",
    ]
    assert after.policy["Statement"][2]["Action"] == "s3:GetObject"
    assert after.policy["Statement"][-1] == unrelated
    repeated: BucketConfiguration = build_bucket_configuration(
        bucket="test-bucket",
        reader_arns=[READER],
        current=after,
        cloudfront_distribution_arn=DISTRIBUTION,
    )
    assert repeated.fingerprint == after.fingerprint


def test_matching_shared_grants_keep_existing_ids_action_order_and_conditions() -> None:
    before: BucketConfiguration = _shared_current()
    before.policy["Statement"][0]["Sid"] = "ExistingApplication"
    before.policy["Statement"][0]["Principal"]["AWS"] = [READER]
    before.policy["Statement"][0]["Action"].append("s3:GetObjectTagging")
    before.policy["Statement"][2]["Sid"] = "ExistingCloudFront"
    before.policy["Statement"][2]["Condition"] = {
        "StringEquals": {"AWS:SourceArn": DISTRIBUTION}
    }
    after: BucketConfiguration = build_bucket_configuration(
        bucket="test-bucket",
        reader_arns=[READER],
        current=before,
        cloudfront_distribution_arn=DISTRIBUTION,
    )
    assert len(after.policy["Statement"]) == len(before.policy["Statement"])
    assert after.policy["Statement"][0]["Sid"] == "ExistingApplication"
    assert after.policy["Statement"][0]["Principal"] == {"AWS": [READER]}
    assert (
        after.policy["Statement"][0]["Action"][:7]
        == before.policy["Statement"][0]["Action"]
    )
    assert (
        after.policy["Statement"][2]["Condition"]
        == before.policy["Statement"][2]["Condition"]
    )


@pytest.mark.parametrize("field", ["Principal", "Resource", "Condition"])
def test_shared_grant_collisions_are_refused(field: str) -> None:
    before: BucketConfiguration = _shared_current()
    replacement: dict[str, Any] = {
        "Principal": {"AWS": "arn:aws:iam::123456789012:user/someone-else"},
        "Resource": "arn:aws:s3:::another-bucket/*",
        "Condition": {"StringEquals": {"aws:SourceVpce": "vpce-123"}},
    }
    before.policy["Statement"][0][field] = replacement[field]
    with pytest.raises(BucketConfigurationError, match="review"):
        build_bucket_configuration(
            bucket="test-bucket",
            reader_arns=[READER],
            current=before,
            cloudfront_distribution_arn=DISTRIBUTION,
        )


def test_conditioned_matching_grant_is_not_bypassed() -> None:
    before: BucketConfiguration = _shared_current()
    before.policy["Statement"][0]["Sid"] = "RestrictedApplication"
    before.policy["Statement"][0]["Condition"] = {
        "StringEquals": {"aws:SourceVpce": "vpce-123"}
    }
    with pytest.raises(BucketConfigurationError, match="different conditions"):
        build_bucket_configuration(
            bucket="test-bucket", reader_arns=[READER], current=before
        )


@pytest.mark.parametrize("allow_cloudfront", [False, True])
def test_recognized_legacy_export_policy_migrates_to_shared_access(
    *, allow_cloudfront: bool
) -> None:
    before: BucketConfiguration = _shared_current()
    before.policy["Statement"].extend(
        [
            {
                "Sid": POLICY_STATEMENT_ID,
                "Effect": "Deny",
                "Principal": "*",
                "Action": ["s3:GetObject", "s3:GetObjectVersion"],
                "Resource": "arn:aws:s3:::test-bucket/exports/*",
                "Condition": {"ArnNotEquals": {"aws:PrincipalArn": [READER]}},
            },
            {
                "Sid": CLOUDFRONT_POLICY_STATEMENT_ID,
                "Effect": "Allow",
                "Principal": {"Service": "cloudfront.amazonaws.com"},
                "Action": ["s3:GetObject", "s3:GetObjectVersion"],
                "Resource": "arn:aws:s3:::test-bucket/exports/*",
                "Condition": {"ArnEquals": {"AWS:SourceArn": DISTRIBUTION}},
            },
            {
                "Sid": "AllowSpeleoDBExportVersionAccess",
                "Effect": "Allow",
                "Principal": {"AWS": READER},
                "Action": [
                    "s3:GetObjectVersion",
                    "s3:DeleteObjectVersion",
                    "s3:AbortMultipartUpload",
                ],
                "Resource": "arn:aws:s3:::test-bucket/exports/*",
            },
            {
                "Sid": "AllowSpeleoDBExportVersionListing",
                "Effect": "Allow",
                "Principal": {"AWS": READER},
                "Action": "s3:ListBucketVersions",
                "Resource": "arn:aws:s3:::test-bucket",
                "Condition": {"StringLike": {"s3:prefix": "exports/*"}},
            },
            {
                "Sid": "AllowSpeleoDBExportMultipartListing",
                "Effect": "Allow",
                "Principal": {"AWS": READER},
                "Action": "s3:ListBucketMultipartUploads",
                "Resource": "arn:aws:s3:::test-bucket",
            },
        ]
    )
    if allow_cloudfront:
        before.policy["Statement"][3]["Condition"]["ArnNotEquals"]["AWS:SourceArn"] = (
            DISTRIBUTION
        )
    after: BucketConfiguration = build_bucket_configuration(
        bucket="test-bucket",
        reader_arns=[READER],
        current=before,
        cloudfront_distribution_arn=DISTRIBUTION,
    )
    expected: BucketConfiguration = build_bucket_configuration(
        bucket="test-bucket",
        reader_arns=[READER],
        current=_shared_current(),
        cloudfront_distribution_arn=DISTRIBUTION,
    )
    assert after.as_dict() == expected.as_dict()


def test_lifecycle_builder_preserves_inputs_and_unrelated_configuration() -> None:
    before: dict[str, Any] = _current().lifecycle
    snapshot: dict[str, Any] = copy.deepcopy(before)
    after: dict[str, Any] = build_export_lifecycle(before)
    assert before == snapshot
    assert after["Rules"][0] == before["Rules"][0]
    assert build_export_lifecycle(after) == after


def test_lifecycle_builder_removes_old_export_version_retention() -> None:
    current: dict[str, Any] = build_export_lifecycle(_current().lifecycle)
    current["Rules"][-1]["NoncurrentVersionExpiration"] = {"NoncurrentDays": 2}
    after: dict[str, Any] = build_export_lifecycle(current)
    assert after["Rules"] == [
        current["Rules"][0],
        {
            "ID": LIFECYCLE_RULE_ID,
            "Status": "Enabled",
            "Filter": {"Prefix": "exports/"},
            "Expiration": {"Days": 2},
            "AbortIncompleteMultipartUpload": {"DaysAfterInitiation": 2},
        },
    ]


def test_configuration_read_uses_only_policy_lifecycle_and_lock_apis() -> None:
    client: MagicMock = MagicMock()
    client.get_bucket_policy.return_value = {"Policy": '{"Statement": []}'}
    client.get_bucket_lifecycle_configuration.return_value = {"Rules": []}
    client.get_object_lock_configuration.return_value = {}
    configuration: BucketConfiguration = read_bucket_configuration(
        client, bucket="test-bucket"
    )
    assert configuration.policy == {"Statement": []}
    assert [api_call[0] for api_call in client.mock_calls] == [
        "get_bucket_policy",
        "get_bucket_lifecycle_configuration",
        "get_object_lock_configuration",
    ]


def test_production_policy_example_matches_the_original_policy_update() -> None:
    example: Path = (
        Path(__file__).resolve().parents[3]
        / "docs/examples/production-export-bucket-policy.json"
    )
    rendered: str = example.read_text()
    replacements: dict[str, str] = {
        "<APPLICATION_IAM_ARN>": READER,
        "<AWS_ACCOUNT_ID>": "123456789012",
        "<CLOUDFRONT_DISTRIBUTION_ID>": "E1EXAMPLE",
        "<S3_BUCKET_NAME>": "test-bucket",
    }
    for placeholder, value in replacements.items():
        assert placeholder in rendered
        rendered = rendered.replace(placeholder, value)
    expected: dict[str, Any] = orjson.loads(rendered)
    original: dict[str, Any] = copy.deepcopy(expected)
    assert [statement["Sid"] for statement in original["Statement"]] == [
        APPLICATION_POLICY_STATEMENT_ID,
        "DenyInsecureConnections",
        SHARED_CLOUDFRONT_POLICY_STATEMENT_ID,
    ]
    original["Statement"][0]["Action"] = APPLICATION_ACTIONS[:6]
    original["Statement"][2]["Action"] = "s3:GetObject"
    after: BucketConfiguration = build_bucket_configuration(
        bucket="test-bucket",
        reader_arns=[READER],
        current=BucketConfiguration(policy=original, lifecycle={}, object_lock={}),
        cloudfront_distribution_arn=DISTRIBUTION,
    )
    assert after.policy == expected


def test_configuration_preserves_unrelated_settings_without_mutating_input() -> None:
    before = _current()
    snapshot = copy.deepcopy(before.as_dict())
    after = build_bucket_configuration(
        bucket="test-bucket", reader_arns=[READER], current=before
    )
    assert before.as_dict() == snapshot
    assert after.policy["Statement"][0] == before.policy["Statement"][0]
    assert after.lifecycle["Rules"][0] == before.lifecycle["Rules"][0]
    assert (
        after.transition_default_minimum_object_size
        == before.transition_default_minimum_object_size
    )
    application = after.policy["Statement"][-1]
    assert application == {
        "Sid": APPLICATION_POLICY_STATEMENT_ID,
        "Effect": "Allow",
        "Principal": {"AWS": READER},
        "Action": APPLICATION_ACTIONS,
        "Resource": ["arn:aws:s3:::test-bucket/*", "arn:aws:s3:::test-bucket"],
    }
    rule = after.lifecycle["Rules"][-1]
    assert rule["Filter"] == {"Prefix": "exports/"}
    assert rule["Expiration"] == {"Days": 2}
    assert rule["AbortIncompleteMultipartUpload"] == {"DaysAfterInitiation": 2}


def test_configuration_is_idempotent_and_reader_order_is_stable() -> None:
    readers: list[str] = [
        READER,
        "arn:aws:iam::123456789012:user/export-service",
        READER,
    ]
    after = build_bucket_configuration(
        bucket="test-bucket", reader_arns=readers, current=_current()
    )
    repeated = build_bucket_configuration(
        bucket="test-bucket", reader_arns=list(reversed(readers)), current=after
    )
    assert repeated.as_dict() == after.as_dict()
    assert repeated.fingerprint == after.fingerprint


@pytest.mark.parametrize(
    "reader",
    [
        "*",
        "arn:aws:iam::123456789012:role/*",
        "arn:aws:iam::123456789012:root",
        "arn:aws:sts::123456789012:assumed-role/speleodb/session",
        "arn:aws:iam::123456789012:role/",
        "arn:aws:iam::123456789012:user/?",
        "arn:aws:iam::123456789012:user/valid\n",
    ],
)
def test_only_exact_iam_user_and_role_readers_are_accepted(reader: str) -> None:
    with pytest.raises(BucketConfigurationError, match="exact IAM"):
        validate_readers([reader])


def test_empty_readers_are_rejected() -> None:
    with pytest.raises(BucketConfigurationError, match="At least one"):
        validate_readers([])


def test_mixed_partitions_are_rejected() -> None:
    with pytest.raises(BucketConfigurationError, match="same AWS partition"):
        validate_readers([READER, "arn:aws-cn:iam::123456789012:role/export-service"])


def test_object_lock_is_refused_even_without_default_retention() -> None:
    current = BucketConfiguration(
        policy={},
        lifecycle={},
        object_lock={"ObjectLockEnabled": "Enabled"},
    )
    with pytest.raises(BucketConfigurationError, match="Object Lock"):
        build_bucket_configuration(
            bucket="test-bucket", reader_arns=[READER], current=current
        )


@pytest.mark.parametrize("collision", ["policy", "cloudfront_policy", "lifecycle"])
def test_reserved_identifier_collision_does_not_modify_another_prefix(
    collision: str,
) -> None:
    before = _current()
    if collision == "policy":
        before.policy["Statement"][0]["Sid"] = POLICY_STATEMENT_ID
    elif collision == "cloudfront_policy":
        before.policy["Statement"][0]["Sid"] = CLOUDFRONT_POLICY_STATEMENT_ID
    else:
        before.lifecycle["Rules"][0]["ID"] = LIFECYCLE_RULE_ID
    message: str = (
        "outside the exports prefix" if collision == "lifecycle" else "unexpected shape"
    )
    with pytest.raises(BucketConfigurationError, match=message):
        build_bucket_configuration(
            bucket="test-bucket", reader_arns=[READER], current=before
        )


def test_cloudfront_grants_shared_reads_to_only_the_configured_distribution() -> None:
    before = _current()
    snapshot = copy.deepcopy(before.as_dict())
    after = build_bucket_configuration(
        bucket="test-bucket",
        reader_arns=[READER],
        current=before,
        cloudfront_distribution_arn=DISTRIBUTION,
    )
    assert before.as_dict() == snapshot
    assert after.policy["Statement"][0] == before.policy["Statement"][0]
    assert after.policy["Statement"][-1] == {
        "Sid": SHARED_CLOUDFRONT_POLICY_STATEMENT_ID,
        "Effect": "Allow",
        "Principal": {"Service": "cloudfront.amazonaws.com"},
        "Action": "s3:GetObject",
        "Resource": "arn:aws:s3:::test-bucket/*",
        "Condition": {"ArnLike": {"AWS:SourceArn": DISTRIBUTION}},
    }
    repeated = build_bucket_configuration(
        bucket="test-bucket",
        reader_arns=[READER],
        current=after,
        cloudfront_distribution_arn=DISTRIBUTION,
    )
    assert repeated.fingerprint == after.fingerprint


def test_iam_only_configuration_preserves_existing_shared_cloudfront_access() -> None:
    before = _current()
    cloudfront = build_bucket_configuration(
        bucket="test-bucket",
        reader_arns=[READER],
        current=before,
        cloudfront_distribution_arn=DISTRIBUTION,
    )
    iam_only = build_bucket_configuration(
        bucket="test-bucket", reader_arns=[READER], current=cloudfront
    )
    assert iam_only.as_dict() == cloudfront.as_dict()


@pytest.mark.parametrize(
    "distribution",
    [
        "",
        "*",
        "arn:aws:cloudfront::123456789012:distribution/*",
        "arn:aws:cloudfront::123456789012:distribution/",
        "arn:aws:cloudfront::123456789012:distribution/E1EXAMPLE\n",
        "arn:aws:cloudfront::123456789012:key-group/E1EXAMPLE",
        "arn:aws:cloudfront:us-east-1:123456789012:distribution/E1EXAMPLE",
    ],
)
def test_cloudfront_requires_an_exact_distribution_arn(distribution: str) -> None:
    with pytest.raises(BucketConfigurationError, match="exact distribution ARN"):
        build_bucket_configuration(
            bucket="test-bucket",
            reader_arns=[READER],
            current=_current(),
            cloudfront_distribution_arn=distribution,
        )


def test_cloudfront_partition_must_match_readers() -> None:
    with pytest.raises(BucketConfigurationError, match="same AWS partition"):
        build_bucket_configuration(
            bucket="test-bucket",
            reader_arns=[READER],
            current=_current(),
            cloudfront_distribution_arn=DISTRIBUTION.replace("arn:aws:", "arn:aws-cn:"),
        )


def test_command_refuses_to_block_configured_cloudfront_downloads() -> None:
    storage = MagicMock()
    storage.custom_domain = "static.example.org"
    storage.querystring_auth = True
    with (
        patch(
            "speleodb.background_jobs.management.commands.configure_export_bucket.ExportStorage",
            return_value=storage,
        ),
        pytest.raises(CommandError, match="--cloudfront-distribution-arn"),
    ):
        call_command("configure_export_bucket", reader_arn=[READER])
    assert storage.connection.meta.client.mock_calls == []


@pytest.mark.parametrize("distribution", [None, DISTRIBUTION])
def test_command_preview_uses_shared_storage_and_does_not_write(
    distribution: str | None,
) -> None:
    before = _current()
    storage = MagicMock()
    storage.bucket_name = "test-bucket"
    storage.custom_domain = "static.example.org" if distribution else False
    output = StringIO()
    with (
        patch(
            "speleodb.background_jobs.management.commands.configure_export_bucket.ExportStorage",
            return_value=storage,
        ),
        patch(
            "speleodb.background_jobs.management.commands.configure_export_bucket.read_bucket_configuration",
            return_value=before,
        ) as read_configuration,
    ):
        call_command(
            "configure_export_bucket",
            reader_arn=[READER],
            cloudfront_distribution_arn=distribution,
            stdout=output,
        )
    read_configuration.assert_called_once_with(
        storage.connection.meta.client, bucket="test-bucket"
    )
    preview = orjson.loads(output.getvalue())
    assert preview["mode"] == "preview"
    assert (
        preview["after"]
        == build_bucket_configuration(
            bucket="test-bucket",
            reader_arns=[READER],
            current=before,
            cloudfront_distribution_arn=distribution,
        ).as_dict()
    )
    assert storage.connection.meta.client.mock_calls == []


def test_command_apply_writes_shared_policy_and_retention_then_verifies() -> None:
    before: BucketConfiguration = _shared_current()
    after: BucketConfiguration = build_bucket_configuration(
        bucket="test-bucket",
        reader_arns=[READER],
        current=before,
        cloudfront_distribution_arn=DISTRIBUTION,
    )
    storage: MagicMock = MagicMock()
    storage.bucket_name = "test-bucket"
    output: StringIO = StringIO()
    with (
        patch(
            "speleodb.background_jobs.management.commands.configure_export_bucket.ExportStorage",
            return_value=storage,
        ),
        patch(
            "speleodb.background_jobs.management.commands.configure_export_bucket.read_bucket_configuration",
            side_effect=[before, before, after],
        ) as read_configuration,
    ):
        call_command(
            "configure_export_bucket",
            reader_arn=[READER],
            cloudfront_distribution_arn=DISTRIBUTION,
            expected_fingerprint=before.fingerprint,
            apply=True,
            stdout=output,
        )
    expected_reads: int = 3  # Initial read, concurrency guard, and verification.
    assert read_configuration.call_count == expected_reads
    client: MagicMock = storage.connection.meta.client
    client.put_bucket_policy.assert_called_once_with(
        Bucket="test-bucket", Policy=orjson.dumps(after.policy).decode()
    )
    client.put_bucket_lifecycle_configuration.assert_called_once_with(
        Bucket="test-bucket",
        LifecycleConfiguration=after.lifecycle,
        TransitionDefaultMinimumObjectSize=after.transition_default_minimum_object_size,
    )
    assert "Shared storage access and export retention verified." in output.getvalue()
