"""Deterministic, prefix-scoped S3 policy and lifecycle configuration builders."""

from __future__ import annotations

import copy
import hashlib
import re
from dataclasses import dataclass
from typing import Any

import orjson

POLICY_STATEMENT_ID: str = "SpeleoDBExportsPrivateRead"
LIFECYCLE_RULE_ID: str = "SpeleoDBExportsRetention"
EXPORT_PREFIX: str = "exports/"
READER_ARN_PATTERN: re.Pattern[str] = re.compile(
    r"arn:(aws|aws-cn|aws-us-gov):iam::[0-9]{12}:(?:user|role)/[A-Za-z0-9+=,.@_/-]+"
)


class BucketConfigurationError(ValueError):
    """A configuration cannot be updated safely without operator intervention."""


@dataclass(frozen=True)
class BucketConfiguration:
    policy: dict[str, Any]
    lifecycle: dict[str, Any]
    versioning: dict[str, Any]
    object_lock: dict[str, Any]
    transition_default_minimum_object_size: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "policy": self.policy,
            "lifecycle": self.lifecycle,
            "versioning": self.versioning,
            "object_lock": self.object_lock,
            "transition_default_minimum_object_size": (
                self.transition_default_minimum_object_size
            ),
        }

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(
            orjson.dumps(self.as_dict(), option=orjson.OPT_SORT_KEYS)
        ).hexdigest()


def validate_readers(reader_arns: list[str]) -> list[str]:
    if not reader_arns:
        raise BucketConfigurationError("At least one exact IAM reader ARN is required.")
    readers: list[str] = sorted(set(reader_arns))
    for arn in readers:
        if READER_ARN_PATTERN.fullmatch(arn) is None or arn.endswith("/"):
            raise BucketConfigurationError(
                "Readers must be exact IAM user or role ARNs; "
                "wildcards, root, and STS sessions are not accepted."
            )
    if len({arn.split(":")[1] for arn in readers}) != 1:
        raise BucketConfigurationError(
            "All reader ARNs must use the same AWS partition."
        )
    return readers


def build_bucket_configuration(
    *,
    bucket: str,
    reader_arns: list[str],
    current: BucketConfiguration,
) -> BucketConfiguration:
    """Preserve all unrelated configuration and replace only our owned entries."""
    readers: list[str] = validate_readers(reader_arns)
    if not bucket or any(character in bucket for character in "/:*?\\"):
        raise BucketConfigurationError(
            "A bucket name without a path or wildcard is required."
        )
    if current.object_lock.get("ObjectLockEnabled") == "Enabled":
        raise BucketConfigurationError(
            "Object Lock is enabled on this bucket; exports require "
            "an unlocked bucket for timely deletion."
        )
    partition: str = readers[0].split(":")[1]
    resource: str = f"arn:{partition}:s3:::{bucket}/{EXPORT_PREFIX}*"
    policy: dict[str, Any] = copy.deepcopy(current.policy)
    policy.setdefault("Version", "2012-10-17")
    statements: Any = policy.get("Statement", [])
    if isinstance(statements, dict):
        statements = [statements]
    if not isinstance(statements, list) or not all(
        isinstance(s, dict) for s in statements
    ):
        raise BucketConfigurationError(
            "The existing bucket policy has an invalid Statement value."
        )
    retained_statements: list[dict[str, Any]] = []
    for statement in statements:
        if statement.get("Sid") != POLICY_STATEMENT_ID:
            retained_statements.append(statement)
        elif statement.get("Resource") not in (resource, [resource]):
            raise BucketConfigurationError(
                "The export policy statement ID is already used "
                "outside the exports prefix."
            )
    policy["Statement"] = [
        *retained_statements,
        {
            "Sid": POLICY_STATEMENT_ID,
            "Effect": "Deny",
            "Principal": "*",
            "Action": ["s3:GetObject", "s3:GetObjectVersion"],
            "Resource": resource,
            "Condition": {"ArnNotEquals": {"aws:PrincipalArn": readers}},
        },
    ]
    lifecycle: dict[str, Any] = copy.deepcopy(current.lifecycle)
    rules: Any = lifecycle.get("Rules", [])
    if not isinstance(rules, list) or not all(isinstance(rule, dict) for rule in rules):
        raise BucketConfigurationError(
            "The existing lifecycle configuration has invalid rules."
        )
    retained_rules: list[dict[str, Any]] = []
    for rule in rules:
        if rule.get("ID") != LIFECYCLE_RULE_ID:
            retained_rules.append(rule)
        elif (
            rule.get("Filter") != {"Prefix": EXPORT_PREFIX}
            and rule.get("Prefix") != EXPORT_PREFIX
        ):
            raise BucketConfigurationError(
                "The export lifecycle rule ID is already used "
                "outside the exports prefix."
            )
    lifecycle["Rules"] = [
        *retained_rules,
        {
            "ID": LIFECYCLE_RULE_ID,
            "Status": "Enabled",
            "Filter": {"Prefix": EXPORT_PREFIX},
            "Expiration": {"Days": 2},
            "NoncurrentVersionExpiration": {"NoncurrentDays": 2},
            "AbortIncompleteMultipartUpload": {"DaysAfterInitiation": 2},
        },
    ]
    return BucketConfiguration(
        policy=policy,
        lifecycle=lifecycle,
        versioning=copy.deepcopy(current.versioning),
        object_lock=copy.deepcopy(current.object_lock),
        transition_default_minimum_object_size=(
            current.transition_default_minimum_object_size or "all_storage_classes_128K"
        ),
    )
