"""Shared S3 application access and prefix-scoped export retention builders."""

from __future__ import annotations

import copy
import hashlib
import re
from dataclasses import dataclass
from typing import Any

import orjson

POLICY_STATEMENT_ID: str = "SpeleoDBExportsPrivateRead"
CLOUDFRONT_POLICY_STATEMENT_ID: str = "SpeleoDBExportsCloudFrontRead"
APPLICATION_POLICY_STATEMENT_ID: str = "AllowSpeleoDBApplicationAccess"
SHARED_CLOUDFRONT_POLICY_STATEMENT_ID: str = "AllowCloudFrontOACReadOnly"
APPLICATION_ACTIONS: list[str] = [
    "s3:PutObject",
    "s3:GetObjectAcl",
    "s3:GetObject",
    "s3:ListBucket",
    "s3:DeleteObject",
    "s3:PutObjectAcl",
    "s3:AbortMultipartUpload",
    "s3:ListBucketMultipartUploads",
]
OBSOLETE_VERSION_ACTIONS: frozenset[str] = frozenset(
    {"s3:GetObjectVersion", "s3:DeleteObjectVersion", "s3:ListBucketVersions"}
)
LIFECYCLE_RULE_ID: str = "SpeleoDBExportsRetention"
EXPORT_PREFIX: str = "exports/"
READER_ARN_PATTERN: re.Pattern[str] = re.compile(
    r"arn:(aws|aws-cn|aws-us-gov):iam::[0-9]{12}:(?:user|role)/[A-Za-z0-9+=,.@_/-]+"
)
CLOUDFRONT_ARN_PATTERN: re.Pattern[str] = re.compile(
    r"arn:(aws|aws-cn|aws-us-gov):cloudfront::[0-9]{12}:distribution/[A-Z0-9]+"
)


class BucketConfigurationError(ValueError):
    """A configuration cannot be updated safely without operator intervention."""


@dataclass(frozen=True)
class BucketConfiguration:
    policy: dict[str, Any]
    lifecycle: dict[str, Any]
    object_lock: dict[str, Any]
    transition_default_minimum_object_size: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "policy": self.policy,
            "lifecycle": self.lifecycle,
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


def _values(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return value
    return []


def _legacy_export_statements(
    *, bucket_arn: str, readers: list[str], distribution: str | None
) -> list[dict[str, Any]]:
    """Exact historical shapes eligible for removal; other SID uses are refused."""
    resource: str = f"{bucket_arn}/{EXPORT_PREFIX}*"
    reader_condition: dict[str, Any] = {"aws:PrincipalArn": readers}
    deny: dict[str, Any] = {
        "Sid": POLICY_STATEMENT_ID,
        "Effect": "Deny",
        "Principal": "*",
        "Action": ["s3:GetObject", "s3:GetObjectVersion"],
        "Resource": resource,
        "Condition": {"ArnNotEquals": reader_condition},
    }
    statements: list[dict[str, Any]] = [copy.deepcopy(deny)]
    principal: dict[str, Any] = {"AWS": readers[0] if len(readers) == 1 else readers}
    for sid, actions, scoped_resource, condition in (
        (
            "AllowSpeleoDBExportVersionAccess",
            [
                "s3:GetObjectVersion",
                "s3:DeleteObjectVersion",
                "s3:AbortMultipartUpload",
            ],
            resource,
            None,
        ),
        (
            "AllowSpeleoDBExportVersionListing",
            "s3:ListBucketVersions",
            bucket_arn,
            {"StringLike": {"s3:prefix": f"{EXPORT_PREFIX}*"}},
        ),
        (
            "AllowSpeleoDBExportMultipartListing",
            "s3:ListBucketMultipartUploads",
            bucket_arn,
            None,
        ),
    ):
        statement: dict[str, Any] = {
            "Sid": sid,
            "Effect": "Allow",
            "Principal": principal,
            "Action": actions,
            "Resource": scoped_resource,
        }
        if condition is not None:
            statement["Condition"] = condition
        statements.append(statement)
    if distribution is not None:
        reader_condition["AWS:SourceArn"] = distribution
        statements.extend(
            [
                deny,
                {
                    "Sid": CLOUDFRONT_POLICY_STATEMENT_ID,
                    "Effect": "Allow",
                    "Principal": {"Service": "cloudfront.amazonaws.com"},
                    "Action": ["s3:GetObject", "s3:GetObjectVersion"],
                    "Resource": resource,
                    "Condition": {"ArnEquals": {"AWS:SourceArn": distribution}},
                },
            ]
        )
    return statements


def _extend_shared_grant(
    statements: list[dict[str, Any]], *, desired: dict[str, Any]
) -> None:
    """Update one exact shared grant and remove obsolete application version access."""
    matches: list[dict[str, Any]] = []
    for statement in statements:
        comparable: dict[str, Any] = copy.deepcopy(statement)
        expected: dict[str, Any] = copy.deepcopy(desired)
        for candidate in (comparable, expected):
            candidate.pop("Sid", None)
            candidate.pop("Action", None)
            candidate["Resource"] = sorted(_values(candidate.get("Resource")))
            principal: Any = candidate.get("Principal")
            if isinstance(principal, dict) and set(principal) == {"AWS"}:
                candidate["Principal"] = {"AWS": sorted(_values(principal["AWS"]))}
            condition: Any = candidate.get("Condition")
            if isinstance(condition, dict) and len(condition) == 1:
                operator: str = next(iter(condition))
                if operator in {"ArnLike", "ArnEquals", "StringEquals"}:
                    candidate["Condition"] = {"ArnEquals": condition[operator]}
        if comparable == expected and _values(statement.get("Action")):
            matches.append(statement)
        elif (
            comparable.get("Effect") == "Allow"
            and comparable.get("Principal") == expected.get("Principal")
            and comparable.get("Resource") == expected.get("Resource")
        ):
            raise BucketConfigurationError(
                "An existing grant for this identity and resource has different "
                "conditions; review it before extending shared access."
            )
        elif statement.get("Sid") == desired["Sid"]:
            raise BucketConfigurationError(
                "The shared policy statement ID has a different identity, "
                "resource scope, or condition; review it before changing access."
            )
    if len(matches) > 1:
        raise BucketConfigurationError(
            "Multiple matching shared grants are ambiguous; consolidate them first."
        )
    if matches:
        actions: list[str] = [
            action
            for action in _values(matches[0]["Action"])
            if action not in OBSOLETE_VERSION_ACTIONS
        ]
        actions.extend(
            action for action in _values(desired["Action"]) if action not in actions
        )
        matches[0]["Action"] = (
            actions[0]
            if isinstance(desired["Action"], str) and len(actions) == 1
            else actions
        )
    else:
        statements.append(desired)


def build_export_lifecycle(current: dict[str, Any]) -> dict[str, Any]:
    """Merge only export retention; production S3 and local RustFS share this rule."""
    lifecycle: dict[str, Any] = copy.deepcopy(current)
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
            "AbortIncompleteMultipartUpload": {"DaysAfterInitiation": 2},
        },
    ]
    return lifecycle


def build_bucket_configuration(
    *,
    bucket: str,
    reader_arns: list[str],
    current: BucketConfiguration,
    cloudfront_distribution_arn: str | None = None,
) -> BucketConfiguration:
    """Extend shared grants, remove recognized legacy grants, and merge retention."""
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
    if cloudfront_distribution_arn is not None:
        if CLOUDFRONT_ARN_PATTERN.fullmatch(cloudfront_distribution_arn) is None:
            raise BucketConfigurationError(
                "CloudFront must use an exact distribution ARN without wildcards."
            )
        if cloudfront_distribution_arn.split(":")[1] != partition:
            raise BucketConfigurationError(
                "CloudFront and reader ARNs must use the same AWS partition."
            )
    bucket_arn: str = f"arn:{partition}:s3:::{bucket}"
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
    legacy: list[dict[str, Any]] = _legacy_export_statements(
        bucket_arn=bucket_arn, readers=readers, distribution=cloudfront_distribution_arn
    )
    legacy_sids: set[str] = {statement["Sid"] for statement in legacy} | {
        CLOUDFRONT_POLICY_STATEMENT_ID
    }
    retained_statements: list[dict[str, Any]] = []
    for statement in statements:
        if statement.get("Sid") not in legacy_sids:
            retained_statements.append(statement)
        elif statement not in legacy:
            raise BucketConfigurationError(
                "An obsolete export policy statement ID has an unexpected shape; "
                "review it before removing access controls."
            )
    _extend_shared_grant(
        retained_statements,
        desired={
            "Sid": APPLICATION_POLICY_STATEMENT_ID,
            "Effect": "Allow",
            "Principal": {"AWS": readers[0] if len(readers) == 1 else readers},
            "Action": APPLICATION_ACTIONS.copy(),
            "Resource": [f"{bucket_arn}/*", bucket_arn],
        },
    )
    if cloudfront_distribution_arn is not None:
        _extend_shared_grant(
            retained_statements,
            desired={
                "Sid": SHARED_CLOUDFRONT_POLICY_STATEMENT_ID,
                "Effect": "Allow",
                "Principal": {"Service": "cloudfront.amazonaws.com"},
                "Action": "s3:GetObject",
                "Resource": f"{bucket_arn}/*",
                "Condition": {
                    "ArnLike": {"AWS:SourceArn": cloudfront_distribution_arn}
                },
            },
        )
    policy["Statement"] = retained_statements
    return BucketConfiguration(
        policy=policy,
        lifecycle=build_export_lifecycle(current.lifecycle),
        object_lock=copy.deepcopy(current.object_lock),
        transition_default_minimum_object_size=(
            current.transition_default_minimum_object_size or "all_storage_classes_128K"
        ),
    )
