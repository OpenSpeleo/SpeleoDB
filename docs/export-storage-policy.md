# Private export storage policy

Exports share the existing bucket under `exports/`. Their objects must remain
private even if the bucket already has a CloudFront origin policy or public
photo permissions. Application downloads go directly to S3 through short-lived
presigned URLs after Django authorizes the requester.

## Preview and apply

Run the command inside the deployed application container or the Docker
development container with the intended environment. Reader ARNs are identifiers,
not credentials. Supply the IAM user or IAM role used by the application's S3
signing credentials; role sessions use their underlying IAM role ARN.

This command targets AWS S3 policies. Local RustFS uses the setup command's
private-by-default bucket policy and its own credentials; do not invent AWS IAM
reader ARNs for local RustFS root credentials.

```sh
python manage.py configure_export_bucket \
  --reader-arn arn:aws:iam::123456789012:role/speleodb-web
```

The default command performs only reads. Its JSON output includes before/after
configuration and a fingerprint. Review the bucket, allowed readers, and changes
to the two SpeleoDB-owned entries. Then apply the reviewed configuration:

```sh
python manage.py configure_export_bucket \
  --reader-arn arn:aws:iam::123456789012:role/speleodb-web \
  --expected-fingerprint <fingerprint-from-preview> \
  --apply
```

Repeat `--reader-arn` for every intended signer. Wildcards, account-root ARNs,
STS session ARNs, and mixed AWS partitions are rejected. An optional expected
fingerprint prevents applying over configuration changed since review. The
command also checks for concurrent changes immediately before writing and
reads the resulting configuration back after applying. S3 does not provide an
atomic transaction across bucket policy and lifecycle writes; run this while
other bucket configuration changes are paused.

The command requires bucket policy, lifecycle, versioning, and Object Lock read
permissions. Applying additionally requires `s3:PutBucketPolicy` and
`s3:PutLifecycleConfiguration`. It never enables or disables bucket versioning,
changes Object Lock, or changes public-access-block settings.

Runtime application credentials need `s3:PutObject`, `s3:GetObject`,
`s3:GetObjectVersion`, `s3:DeleteObject`, `s3:DeleteObjectVersion`, and
`s3:AbortMultipartUpload` on `exports/*`, plus `s3:ListBucketVersions` and
`s3:ListBucketMultipartUploads` on the bucket. Scope the bucket listing grants to
the export prefix where supported. Cleanup aborts only uploads with the exact
attempt-owned key, including when the worker died before obtaining a Version ID.

## Access policy

The `SpeleoDBExportsPrivateRead` statement explicitly denies `s3:GetObject` and
`s3:GetObjectVersion` for `exports/*` unless `aws:PrincipalArn` matches one of the
listed readers. The explicit deny overrides existing public and CloudFront
allows. Anonymous requests and CloudFront OAI/OAC requests do not match the
application signer allowlist. Allowed readers still need their ordinary IAM
permissions; this exception to a deny does not itself grant access.

AWS documents that signed role requests expose their IAM role ARN in
[`aws:PrincipalArn`](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_condition-keys.html#condition-keys-principalarn),
while anonymous requests omit it. A
[negated ARN condition](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_elements_condition_operators.html)
applies to an absent key, which is why anonymous access remains denied.

Preserve the application signing identity during credential rotation, or add its
replacement reader ARN before switching credentials. Removing a reader ARN
invalidates its existing download URLs. The policy does not affect other object
prefixes. An identifier collision with an existing entry outside `exports/`
causes the command to refuse the change.

After applying, verify direct presigned download as the configured application
signer, anonymous S3 denial, anonymous CloudFront denial, and an unrelated public
photo URL. If `exports/` was ever publicly cached, invalidate those existing
CloudFront paths before enabling downloads; changing the origin policy cannot
remove an already cached response.

## Retention and failure handling

The application enforces download expiry 24 hours after readiness. Celery Beat
schedules cleanup tasks consumed by the shared worker to delete expired objects;
there is no Railway cron job.

The `SpeleoDBExportsRetention` fallback rule expires current objects after two
days, noncurrent versions after two days, and incomplete multipart uploads after
two days. Lifecycle deletion is asynchronous and does not provide an exact
24-hour physical-deletion guarantee. All unrelated lifecycle rules and their
existing minimum-transition-object-size setting are preserved.

Object Lock-enabled buckets are refused, including those without a default
retention rule: per-object retention or legal holds would prevent the promised
cleanup. Use an unlocked bucket before deploying this feature.

The private-read policy is applied before lifecycle changes. If lifecycle
configuration fails, the private-read restriction stays installed; preview and
rerun the idempotent command. Complete configuration readback and actual
signed/anonymous download checks before deployment. Existing broader lifecycle
rules remain in force and must be reviewed for overlap with `exports/`.

## Verification

Pure builder tests exercise idempotence, reader validation, input immutability,
reserved-ID collisions, Object Lock rejection, and preservation of unrelated
configuration. Run them inside Docker. The deployment smoke test validates the
actual S3 and CloudFront access policy; builder tests do not substitute for AWS
policy evaluation.

The large-file check is opt-in because it transfers and stores several GiB in
the isolated test bucket. It requires at least 16 GiB free in Docker's backing
filesystem, creates a real member larger than 4 GiB, reads its ZIP64 output in
bounded chunks, uploads the completed ZIP, and removes its own test objects:

```sh
docker compose -f local.yml exec -T -e SPELEODB_TEST_LARGE_ARCHIVE=1 django \
  pytest speleodb/background_jobs/tests/test_large_archive.py -q -s
```

Run this after other database tests have finished. It reports archive/member
sizes, source-upload/build/total durations, and peak process RSS. The permitted
RSS increase is 512 MiB, independent of the member's size. Normal pytest runs
skip this capacity check.

### Recorded local capacity check

The Docker/RustFS run on 2026-09-14 passed with a 4,294,967,313-byte member
and a 4,294,969,785-byte ZIP. Building took 14.83 seconds; source upload, build,
artifact upload, and complete artifact download verification took 35.70 seconds.
Peak process memory was about 405 MiB, an increase of about 130 MiB. Both the
extracted member and downloaded ZIP matched their SHA256 checksums. All test
objects and multipart uploads were removed.

This synthetic local test validates ZIP64, streaming, integrity, and bounded
memory. It does not predict production latency across GitLab and AWS networks.
