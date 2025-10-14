# -*- coding: utf-8 -*-

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import boto3
from botocore.exceptions import ClientError
from django.conf import settings
from django.core.management.base import BaseCommand
from django.core.management.base import CommandError

if TYPE_CHECKING:
    from typing import Any


class Command(BaseCommand):
    help = "Create a MinIO bucket and apply a bucket policy."

    def handle(self, *args: Any, **kwargs: Any) -> None:
        for bucket_name in [
            "speleodb-user-artifacts-dev",
            "speleodb-user-artifacts-test",
        ]:
            policy_local_json = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Sid": "AllowPublicReadForMedia",
                        "Effect": "Allow",
                        "Principal": "*",
                        "Action": "s3:GetObject",
                        "Resource": f"arn:aws:s3:::{bucket_name}/media/*",
                    }
                ],
            }

            # Create S3/MinIO client
            s3 = boto3.client(  # type: ignore[no-untyped-call]
                "s3",
                endpoint_url=getattr(settings, "AWS_S3_ENDPOINT_URL", None),
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=getattr(settings, "AWS_S3_REGION_NAME", "us-east-1"),
                use_ssl=getattr(settings, "AWS_S3_USE_SSL", True),
                verify=getattr(settings, "AWS_S3_VERIFY", True),
            )

            # Create bucket
            try:
                s3.head_bucket(Bucket=bucket_name)
                self.stdout.write(
                    self.style.SUCCESS(f"Bucket '{bucket_name}' already exists.")
                )

            except ClientError:
                try:
                    s3.create_bucket(Bucket=bucket_name)
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Bucket '{bucket_name}' created successfully."
                        )
                    )
                except ClientError as e:
                    raise CommandError(
                        f"Failed to create bucket '{bucket_name}': {e}"
                    ) from e

            try:
                s3.put_bucket_policy(
                    Bucket=bucket_name, Policy=json.dumps(policy_local_json)
                )
                self.stdout.write(
                    self.style.SUCCESS(f"Policy applied to bucket '{bucket_name}'.")
                )
            except ClientError as e:
                raise CommandError(f"Failed to apply policy: {e}") from e
