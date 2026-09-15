# -*- coding: utf-8 -*-

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import boto3
from botocore.exceptions import ClientError
from django.conf import settings
from django.core.management.base import BaseCommand
from django.core.management.base import CommandError

from speleodb.background_jobs.bucket_configuration import BucketConfigurationError
from speleodb.background_jobs.bucket_configuration import build_export_lifecycle

if TYPE_CHECKING:
    from typing import Any


MISSING_BUCKET_ERROR_CODES = frozenset({"404", "NoSuchBucket", "NotFound"})
LOCAL_CORS_CONFIGURATION = {
    "CORSRules": [
        {
            "AllowedOrigins": ["*"],
            "AllowedMethods": ["GET", "HEAD"],
        }
    ]
}


class Command(BaseCommand):
    help = "Create local S3 buckets with access, CORS, and export retention rules."

    def _configure_lifecycle(self, s3: Any, bucket_name: str) -> None:
        try:
            response: dict[str, Any] = s3.get_bucket_lifecycle_configuration(
                Bucket=bucket_name
            )
        except ClientError as exc:
            if (
                exc.response.get("Error", {}).get("Code")
                != "NoSuchLifecycleConfiguration"
            ):
                raise CommandError(
                    f"Failed to inspect lifecycle rules for bucket '{bucket_name}': "
                    f"{exc}"
                ) from exc
            response = {}
        current: dict[str, Any] = {"Rules": response.get("Rules", [])}
        try:
            desired: dict[str, Any] = build_export_lifecycle(current)
        except BucketConfigurationError as exc:
            raise CommandError(
                f"Failed to configure lifecycle rules for bucket '{bucket_name}': {exc}"
            ) from exc
        if desired == current:
            return

        parameters: dict[str, Any] = {
            "Bucket": bucket_name,
            "LifecycleConfiguration": desired,
        }
        minimum_size: str | None = response.get("TransitionDefaultMinimumObjectSize")
        if minimum_size is not None:
            parameters["TransitionDefaultMinimumObjectSize"] = minimum_size
        try:
            s3.put_bucket_lifecycle_configuration(**parameters)
        except ClientError as exc:
            raise CommandError(
                f"Failed to apply lifecycle rules to bucket '{bucket_name}': {exc}"
            ) from exc
        self.stdout.write(
            self.style.SUCCESS(f"Export retention applied to bucket '{bucket_name}'.")
        )

    def handle(self, *args: Any, **kwargs: Any) -> None:
        endpoint_url: str | None = getattr(settings, "AWS_S3_ENDPOINT_URL", None)
        if not endpoint_url:
            raise CommandError(
                "AWS_S3_ENDPOINT_URL must be configured; refusing to provision "
                "buckets against the default AWS endpoint."
            )

        s3: Any = boto3.client(  # type: ignore[no-untyped-call]
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=getattr(settings, "AWS_S3_REGION_NAME", "us-east-1"),
            use_ssl=getattr(settings, "AWS_S3_USE_SSL", True),
            verify=getattr(settings, "AWS_S3_VERIFY", True),
        )

        for bucket_name in [
            "speleodb-user-artifacts-dev",
            "speleodb-user-artifacts-test",
        ]:
            policy_local_json: dict[str, Any] = {
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

            try:
                s3.head_bucket(Bucket=bucket_name)
                self.stdout.write(
                    self.style.SUCCESS(f"Bucket '{bucket_name}' already exists.")
                )
            except ClientError as exc:
                error_code = str(exc.response.get("Error", {}).get("Code", ""))
                if error_code not in MISSING_BUCKET_ERROR_CODES:
                    raise CommandError(
                        f"Failed to inspect bucket '{bucket_name}': {exc}"
                    ) from exc

                try:
                    s3.create_bucket(Bucket=bucket_name)
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Bucket '{bucket_name}' created successfully."
                        )
                    )
                except ClientError as exc:
                    raise CommandError(
                        f"Failed to create bucket '{bucket_name}': {exc}"
                    ) from exc

            try:
                s3.put_bucket_policy(
                    Bucket=bucket_name, Policy=json.dumps(policy_local_json)
                )
                self.stdout.write(
                    self.style.SUCCESS(f"Policy applied to bucket '{bucket_name}'.")
                )
            except ClientError as exc:
                raise CommandError(
                    f"Failed to apply policy to bucket '{bucket_name}': {exc}"
                ) from exc

            try:
                s3.put_bucket_cors(
                    Bucket=bucket_name,
                    CORSConfiguration=LOCAL_CORS_CONFIGURATION,
                )
                self.stdout.write(
                    self.style.SUCCESS(f"CORS rules applied to bucket '{bucket_name}'.")
                )
            except ClientError as exc:
                raise CommandError(
                    f"Failed to apply CORS rules to bucket '{bucket_name}': {exc}"
                ) from exc

            self._configure_lifecycle(s3, bucket_name)
