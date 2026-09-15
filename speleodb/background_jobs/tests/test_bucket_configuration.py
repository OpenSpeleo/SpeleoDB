"""Pure configuration builders preserve unrelated S3 policy and lifecycle data."""

from __future__ import annotations

import copy

import pytest

from speleodb.background_jobs.bucket_configuration import LIFECYCLE_RULE_ID
from speleodb.background_jobs.bucket_configuration import POLICY_STATEMENT_ID
from speleodb.background_jobs.bucket_configuration import BucketConfiguration
from speleodb.background_jobs.bucket_configuration import BucketConfigurationError
from speleodb.background_jobs.bucket_configuration import build_bucket_configuration
from speleodb.background_jobs.bucket_configuration import validate_readers

READER: str = "arn:aws:iam::123456789012:role/speleodb-web"


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
        versioning={"Status": "Enabled"},
        object_lock={},
        transition_default_minimum_object_size="all_storage_classes_128K",
    )


def test_configuration_preserves_unrelated_settings_without_mutating_input() -> None:
    before = _current()
    snapshot = copy.deepcopy(before.as_dict())
    after = build_bucket_configuration(
        bucket="test-bucket", reader_arns=[READER], current=before
    )
    assert before.as_dict() == snapshot
    assert after.policy["Statement"][0] == before.policy["Statement"][0]
    assert after.lifecycle["Rules"][0] == before.lifecycle["Rules"][0]
    assert after.versioning == before.versioning
    assert (
        after.transition_default_minimum_object_size
        == before.transition_default_minimum_object_size
    )
    deny = after.policy["Statement"][-1]
    assert deny == {
        "Sid": POLICY_STATEMENT_ID,
        "Effect": "Deny",
        "Principal": "*",
        "Action": ["s3:GetObject", "s3:GetObjectVersion"],
        "Resource": "arn:aws:s3:::test-bucket/exports/*",
        "Condition": {"ArnNotEquals": {"aws:PrincipalArn": [READER]}},
    }
    rule = after.lifecycle["Rules"][-1]
    assert rule["Filter"] == {"Prefix": "exports/"}
    assert rule["Expiration"] == {"Days": 2}
    assert rule["NoncurrentVersionExpiration"] == {"NoncurrentDays": 2}
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
        versioning={},
        object_lock={"ObjectLockEnabled": "Enabled"},
    )
    with pytest.raises(BucketConfigurationError, match="Object Lock"):
        build_bucket_configuration(
            bucket="test-bucket", reader_arns=[READER], current=current
        )


@pytest.mark.parametrize("collision", ["policy", "lifecycle"])
def test_reserved_identifier_collision_does_not_modify_another_prefix(
    collision: str,
) -> None:
    before = _current()
    if collision == "policy":
        before.policy["Statement"][0]["Sid"] = POLICY_STATEMENT_ID
    else:
        before.lifecycle["Rules"][0]["ID"] = LIFECYCLE_RULE_ID
    with pytest.raises(BucketConfigurationError, match="outside the exports prefix"):
        build_bucket_configuration(
            bucket="test-bucket", reader_arns=[READER], current=before
        )


def test_versioning_disabled_is_preserved() -> None:
    before = BucketConfiguration(policy={}, lifecycle={}, versioning={}, object_lock={})
    after = build_bucket_configuration(
        bucket="test-bucket", reader_arns=[READER], current=before
    )
    assert after.versioning == {}
