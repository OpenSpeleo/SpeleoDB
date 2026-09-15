"""Preview or explicitly apply shared storage access and export retention."""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

import orjson
from botocore.exceptions import ClientError
from django.core.management.base import BaseCommand
from django.core.management.base import CommandError

from speleodb.background_jobs.bucket_configuration import BucketConfiguration
from speleodb.background_jobs.bucket_configuration import BucketConfigurationError
from speleodb.background_jobs.bucket_configuration import build_bucket_configuration
from speleodb.background_jobs.bucket_configuration import validate_readers
from speleodb.utils.s3_storages import ExportStorage

if TYPE_CHECKING:
    from django.core.management.base import CommandParser


def _read_optional(
    client: Any,
    operation: str,
    *,
    bucket: str,
    absent_codes: frozenset[str],
) -> dict[str, Any]:
    try:
        response: dict[str, Any] = getattr(client, operation)(Bucket=bucket)
    except ClientError as error:
        if error.response.get("Error", {}).get("Code") in absent_codes:
            return {}
        raise CommandError(
            f"Cannot inspect export bucket configuration ({operation})."
        ) from None
    response.pop("ResponseMetadata", None)
    return response


def read_bucket_configuration(client: Any, *, bucket: str) -> BucketConfiguration:
    """Read policies, lifecycle, and Object Lock without changing the bucket."""
    raw_policy: dict[str, Any] = _read_optional(
        client,
        "get_bucket_policy",
        bucket=bucket,
        absent_codes=frozenset({"NoSuchBucketPolicy"}),
    )
    lifecycle: dict[str, Any] = _read_optional(
        client,
        "get_bucket_lifecycle_configuration",
        bucket=bucket,
        absent_codes=frozenset({"NoSuchLifecycleConfiguration"}),
    )
    lock: dict[str, Any] = _read_optional(
        client,
        "get_object_lock_configuration",
        bucket=bucket,
        absent_codes=frozenset(
            {"ObjectLockConfigurationNotFoundError", "NoSuchObjectLockConfiguration"}
        ),
    )
    return BucketConfiguration(
        policy=orjson.loads(raw_policy["Policy"]) if "Policy" in raw_policy else {},
        lifecycle={"Rules": lifecycle.get("Rules", [])},
        object_lock=lock.get("ObjectLockConfiguration", {}),
        transition_default_minimum_object_size=lifecycle.get(
            "TransitionDefaultMinimumObjectSize"
        ),
    )


class Command(BaseCommand):
    help = (
        "Preview shared bucket access and the exports/ two-day lifecycle fallback; "
        "use --apply to change S3."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--cloudfront-distribution-arn",
            help="Exact CloudFront distribution ARN used for signed export downloads.",
        )
        parser.add_argument(
            "--reader-arn",
            action="append",
            required=True,
            help="Exact application IAM user/role ARN; repeat for each identity.",
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Apply the displayed configuration to S3.",
        )
        parser.add_argument(
            "--expected-fingerprint",
            help="Preview fingerprint; refuse configuration changed since review.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        try:
            readers: list[str] = validate_readers(options["reader_arn"])
            storage = ExportStorage()
            distribution_arn: str | None = options["cloudfront_distribution_arn"]
            if (
                storage.custom_domain
                and storage.querystring_auth
                and storage.cloudfront_signer
                and distribution_arn is None
            ):
                raise CommandError(
                    "CloudFront signed downloads are configured; supply "
                    "--cloudfront-distribution-arn to configure shared origin access."
                )
            bucket: str = storage.bucket_name
            client = storage.connection.meta.client
            before = read_bucket_configuration(client, bucket=bucket)
            expected: str | None = options["expected_fingerprint"]
            if expected is not None and expected != before.fingerprint:
                raise CommandError(
                    "Bucket configuration changed since the reviewed preview."
                )
            after = build_bucket_configuration(
                bucket=bucket,
                reader_arns=readers,
                current=before,
                cloudfront_distribution_arn=distribution_arn,
            )
        except BucketConfigurationError as error:
            raise CommandError(str(error)) from None
        preview: dict[str, Any] = {
            "bucket": bucket,
            "mode": "apply" if options["apply"] else "preview",
            "fingerprint": before.fingerprint,
            "changed": before.fingerprint != after.fingerprint,
            "before": before.as_dict(),
            "after": after.as_dict(),
        }
        self.stdout.write(orjson.dumps(preview, option=orjson.OPT_INDENT_2).decode())
        if not options["apply"] or before.fingerprint == after.fingerprint:
            return
        # Guard the read/modify/write window against a configuration change.
        if (
            read_bucket_configuration(client, bucket=bucket).fingerprint
            != before.fingerprint
        ):
            raise CommandError(
                "Bucket configuration changed during this run; preview again."
            )
        try:
            # Apply shared access first; an interrupted lifecycle update can be
            # retried idempotently after reviewing the resulting configuration.
            client.put_bucket_policy(
                Bucket=bucket, Policy=orjson.dumps(after.policy).decode()
            )
            lifecycle_options: dict[str, Any] = {
                "Bucket": bucket,
                "LifecycleConfiguration": after.lifecycle,
            }
            if after.transition_default_minimum_object_size is not None:
                lifecycle_options["TransitionDefaultMinimumObjectSize"] = (
                    after.transition_default_minimum_object_size
                )
            client.put_bucket_lifecycle_configuration(**lifecycle_options)
        except ClientError:
            raise CommandError(
                "Applying bucket configuration failed; shared access "
                "may already be updated. Preview and rerun."
            ) from None
        verified = read_bucket_configuration(client, bucket=bucket)
        if verified.fingerprint != after.fingerprint:
            raise CommandError(
                "S3 configuration readback differs from the requested configuration; "
                "inspect before enabling exports."
            )
        self.stdout.write(
            self.style.SUCCESS("Shared storage access and export retention verified.")
        )
