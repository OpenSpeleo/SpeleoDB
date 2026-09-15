# Private export storage policy

Exports share the existing bucket under `exports/` and use the same private
storage backend as other protected files. Django authorizes the requester before
issuing a short-lived signed download URL. Production uses the configured
CloudFront domain and signing key; local RustFS uses its browser endpoint and S3
presigning. Uploads, metadata checks, version deletion, and multipart cleanup use
the backend's S3 connection in both environments.

New archive keys use the flat `exports/{filename}.zip` layout, with an attempt
UUID in the filename for uniqueness. Previously stored nested export keys remain
readable and eligible for cleanup; the prefix-scoped policy covers both layouts.

The object prefix has its own access and retention rules because an export can
contain private project data. S3 origin authorization and CloudFront viewer
authorization are separate requirements: an OAC bucket grant alone does not
require viewers to have a signed URL.

## Required production configuration

For the supplied `static.speleodb.org` bucket policy, keep the existing application,
TLS, and CloudFront statements. Add these runtime grants for `sdb-prod`:

| Resource | Additional permissions |
| --- | --- |
| `arn:aws:s3:::static.speleodb.org/exports/*` | `s3:GetObjectVersion`, `s3:DeleteObjectVersion`, `s3:AbortMultipartUpload` |
| Bucket, with `s3:prefix` matching `exports/*` | `s3:ListBucketVersions` |
| Bucket | `s3:ListBucketMultipartUploads` |

AWS distinguishes version-specific reads/deletes from ordinary object operations.
Multipart upload creation, upload, and completion use the existing `s3:PutObject`
grant. The cleanup implementation does not call `ListParts`, so it does not need
`s3:ListMultipartUploadParts`. See the
[S3 API permission mapping](https://docs.aws.amazon.com/AmazonS3/latest/userguide/using-with-s3-policy-actions.html).

`ListBucketMultipartUploads` does not support the `s3:prefix` condition; its grant
must be separate from the prefix-constrained version listing grant. The cleanup
request still supplies the exact attempt key as its prefix and verifies key
equality before aborting uploads. See the
[S3 action and condition reference](https://docs.aws.amazon.com/service-authorization/latest/reference/list_s3.html).

The complete policy in
[`examples/production-export-bucket-policy.json`](examples/production-export-bucket-policy.json)
preserves the three supplied statements and adds these permissions, the exact
CloudFront distribution's version-read grant, and the private export restriction.
It targets account `520473892271`, user `sdb-prod`, bucket `static.speleodb.org`,
and distribution `E1F0W4EUQJLP0X`. Review it against the live policy before replacing
the policy; another operator may have added unrelated statements since the
supplied snapshot. Existing IAM grants may already supply some of the additional
permissions, but the supplied bucket policy alone does not.

In CloudFront, the cache behavior that matches `exports/*` must:

- Use the existing S3 REST origin and OAC with request signing enabled.
- Require HTTPS and signed URLs using the trusted key group/signing identity
  corresponding to the application's existing CloudFront key.
- Use the managed `CachingDisabled` cache policy (minimum, default, and maximum
  TTL all zero), preserving the object's `Cache-Control: private, no-store`
  metadata.
- Forward `versionId`, `response-content-disposition`, and
  `response-cache-control` query strings to S3. With `CachingDisabled`, configure
  this allowlist in the origin request policy. If caching is enabled later,
  include these values in the cache key as well.

An earlier matching public behavior must not capture `exports/*`. CloudFront's
[cache behavior settings](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/DownloadDistValuesCacheBehavior.html)
control viewer restrictions and minimum TTL. Its
[query string configuration](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/QueryStringParameters.html)
controls forwarding; the CloudFront authentication parameters are consumed at
the edge. Without forwarding `versionId`, S3 would serve the current object
instead of the recorded version.

Configure the CloudFront behavior and bucket grants before deploying the
version-aware storage change. The application changes do not modify AWS
configuration automatically. Verify a signed export download, unsigned
CloudFront rejection, anonymous S3 rejection, and an unrelated existing public
asset after applying the configuration. A signed request for a nonexistent
`versionId` must fail; success would show that a cache or origin request policy
is still dropping the version parameter.

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
  --reader-arn arn:aws:iam::520473892271:user/sdb-prod \
  --cloudfront-distribution-arn arn:aws:cloudfront::520473892271:distribution/E1F0W4EUQJLP0X
```

The default command performs only reads. Its JSON output includes before/after
configuration and a fingerprint. Review the bucket, allowed readers,
distribution, and changes to the SpeleoDB-owned entries. Then apply the reviewed
configuration:

```sh
python manage.py configure_export_bucket \
  --reader-arn arn:aws:iam::520473892271:user/sdb-prod \
  --cloudfront-distribution-arn arn:aws:cloudfront::520473892271:distribution/E1F0W4EUQJLP0X \
  --expected-fingerprint <fingerprint-from-preview> \
  --apply
```

Repeat `--reader-arn` for every intended S3 signer. The distribution argument
accepts one exact ARN, not a hostname, key ID, or wildcard. It must use the same
AWS partition as the IAM readers. Wildcards, account-root reader ARNs,
STS session ARNs, and mixed AWS partitions are rejected. An optional expected
fingerprint prevents applying over configuration changed since review. The
command also checks for concurrent changes immediately before writing and
reads the resulting configuration back after applying. S3 does not provide an
atomic transaction across bucket policy and lifecycle writes; run this while
other bucket configuration changes are paused.

Omit the distribution argument only in an environment explicitly configured for
direct S3 signed URLs. The command refuses to install an IAM-only deny when its
storage backend has active CloudFront signing, because that would block all
CloudFront export downloads. It preserves existing unrelated CloudFront grants
and owns only `SpeleoDBExportsPrivateRead`, `SpeleoDBExportsCloudFrontRead`, and
the export lifecycle rule. It does not install the application's runtime IAM
grants or change CloudFront cache behaviors.

The command requires bucket policy, lifecycle, versioning, and Object Lock read
permissions. Applying additionally requires `s3:PutBucketPolicy` and
`s3:PutLifecycleConfiguration`. It never enables or disables bucket versioning,
changes Object Lock, or changes public-access-block settings.

Runtime application credentials need `s3:PutObject`, `s3:GetObject`,
`s3:GetObjectVersion`, `s3:DeleteObject`, `s3:DeleteObjectVersion`, and
`s3:AbortMultipartUpload` on `exports/*`, plus the two bucket listing grants shown
above. Cleanup aborts only uploads with the exact attempt-owned key, including
when the worker died before obtaining a Version ID.

## Access policy

The `SpeleoDBExportsPrivateRead` statement explicitly denies `s3:GetObject` and
`s3:GetObjectVersion` for `exports/*` unless either `aws:PrincipalArn` matches one
of the listed readers or `AWS:SourceArn` matches the configured CloudFront
distribution. Both negated conditions must be true for the deny to apply.
Anonymous direct S3 requests match neither exception and remain denied. Without
a distribution argument, the policy retains the original IAM-only restriction.

`SpeleoDBExportsCloudFrontRead` separately allows `cloudfront.amazonaws.com` to
read both current and specific export versions, conditioned on the exact
distribution ARN. This follows AWS's
[OAC origin policy pattern](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/private-content-restricting-access-to-s3.html).
Other distributions and OAI identities remain excluded. IAM readers still need
their ordinary permissions; an exception to a deny does not grant access.

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

After applying, verify the configured signed download route, anonymous S3 denial,
unsigned CloudFront denial, and an unrelated public photo URL. If `exports/` was
ever publicly cached, invalidate those existing
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

Pure builder and command tests exercise IAM-only and CloudFront configurations,
exact reader/distribution validation, idempotence, input immutability,
reserved-ID collisions, Object Lock rejection, preservation of unrelated
configuration, the missing-distribution guard, and read-only previews. Run them
inside Docker. The deployment smoke test validates the actual S3 and CloudFront
access policy; builder tests do not substitute for AWS policy evaluation.

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
