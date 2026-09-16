# Shared storage policy and signed export downloads

Exports use the same private storage backend, bucket, CloudFront domain, and
signing key as the other protected files. Django authorizes access and returns a
normal, short-lived signed download URL. Production signs the CloudFront URL;
local RustFS signs its browser-facing S3 URL. Both paths call
`ExportStorage.url()` through `PrivateS3Storage` and the shared
`BrowserFacingS3Storage` implementation. Public photo/static backends use
`PublicS3Storage` on that same base. No export-specific credential or signing
mechanism is required.

New object keys are `exports/{filename}.zip`; the filename includes an attempt
UUID. Historical nested keys remain readable and eligible for cleanup.

## Complete production bucket policy

The complete JSON below uses placeholders for your AWS identifiers. Replace
`<APPLICATION_IAM_ARN>` with your application's exact IAM user/role ARN,
`<AWS_ACCOUNT_ID>` with the distribution's AWS account ID,
`<CLOUDFRONT_DISTRIBUTION_ID>` with its distribution ID, and `<S3_BUCKET_NAME>`
with your bucket name before applying the policy or running the commands below.
Keep these values in your private deployment configuration.

The policy retains the same three statements and HTTPS restriction. The existing
`bucket/*` object resource already includes exports. There are no separate
export access grants; the CloudFront grant remains restricted to one exact
distribution.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowSpeleoDBApplicationAccess",
      "Effect": "Allow",
      "Principal": {
        "AWS": "<APPLICATION_IAM_ARN>"
      },
      "Action": [
        "s3:PutObject",
        "s3:GetObjectAcl",
        "s3:GetObject",
        "s3:ListBucket",
        "s3:DeleteObject",
        "s3:PutObjectAcl",
        "s3:AbortMultipartUpload",
        "s3:ListBucketMultipartUploads"
      ],
      "Resource": [
        "arn:aws:s3:::<S3_BUCKET_NAME>/*",
        "arn:aws:s3:::<S3_BUCKET_NAME>"
      ]
    },
    {
      "Sid": "DenyInsecureConnections",
      "Effect": "Deny",
      "Principal": "*",
      "Action": "s3:*",
      "Resource": [
        "arn:aws:s3:::<S3_BUCKET_NAME>",
        "arn:aws:s3:::<S3_BUCKET_NAME>/*"
      ],
      "Condition": {
        "Bool": {
          "aws:SecureTransport": "false"
        }
      }
    },
    {
      "Sid": "AllowCloudFrontOACReadOnly",
      "Effect": "Allow",
      "Principal": {
        "Service": "cloudfront.amazonaws.com"
      },
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::<S3_BUCKET_NAME>/*",
      "Condition": {
        "ArnLike": {
          "AWS:SourceArn": "arn:aws:cloudfront::<AWS_ACCOUNT_ID>:distribution/<CLOUDFRONT_DISTRIBUTION_ID>"
        }
      }
    }
  ]
}
```

The identical, complete file is
[`examples/production-export-bucket-policy.json`](examples/production-export-bucket-policy.json).
This policy is based on the user's supplied snapshot; preserve any unrelated
statements added by another operator since that snapshot.

The application statement adds only `s3:AbortMultipartUpload` and
`s3:ListBucketMultipartUploads` for cleanup of interrupted uploads. Ordinary
upload, read, and delete operations already use the existing grants. The
CloudFront statement keeps `s3:GetObject`. These permissions apply to the same
shared bucket and object resources. See the
[S3 operation permission mapping](https://docs.aws.amazon.com/AmazonS3/latest/userguide/using-with-s3-policy-actions.html).

The policy has no anonymous read grant. `ExportStorage.default_acl` is `None`,
so export uploads do not send an ACL or grant public access. Keep intentional
public access limited to existing public assets; a broader public bucket grant
or public export ACL would also allow anonymous S3 access. The CloudFront OAC
grant authorizes the existing distribution to fetch objects from S3, following
the
[AWS OAC pattern](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/private-content-restricting-access-to-s3.html).

## CloudFront: ordinary signed downloads

Use the existing distribution, S3 origin/OAC, domain, and trusted signing key.
The production export URL is the stored file path with only `Expires`,
`Signature`, and `Key-Pair-Id`. Filename, content type, and
`Cache-Control: public, max-age=86400` are object metadata written during
upload. CloudFront downloads do not request response-header overrides.

Exports reuse the shared cacheable storage policy used by media and attachments.
The `public` cache directive permits caching; it does not grant anonymous object
access. S3 access policy and CloudFront signed viewer access remain
authoritative. The authenticated Django redirect retains `private, no-store` so
a browser does not reuse a redirect containing an expired signed URL. Existing
objects retain their stored headers; generating a new archive after deployment
writes the new cache metadata.

Direct S3 downloads also use an ordinary signed file URL, containing only SigV4
authentication parameters. Local Compose and CI pin RustFS `1.0.0-rc.1`, whose
ordinary GETs return the stored filename, content type, and cache headers. The
provider's [GET cache-header fix](https://github.com/rustfs/rustfs/pull/5241)
applies to every backend, including unsigned public files. No response-header
overrides or metadata lookup are needed to generate a download URL.

The existing private behavior must require signed URLs and trust the configured
signing identity, as it does for other protected files. Keep the existing
managed policies: `CachingOptimized`, `CORS-S3Origin`, and
`CORS-with-preflight-and-SecurityHeadersPolicy`. The user accepts CloudFront
caching; no custom cache policy or zero minimum TTL is required. New archives
carry the shared one-day cache lifetime. CloudFront still validates the
signature and expiry before serving cached content. Exports require no custom
query forwarding or additional CloudFront permissions. See
[AWS cache duration rules](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/Expiration.html),
[AWS signed URLs](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/private-content-signed-urls.html)
and
[cache behavior settings](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/DownloadDistValuesCacheBehavior.html).

## File identity and overwrite

An archive is identified only by its object key. Uploading or saving the same
key replaces its contents under that exact name. Each attempt still reserves a
flat `exports/{filename}.zip` key, and historical nested keys remain usable. The
application stores the key, filename, size, checksum, and expiry; it does not
track or select S3 object versions.

Migration `0003_remove_object_versions` removes the obsolete tracking fields
from attempts and artifacts. It preserves the job records, object keys, and
files. S3 bucket-level versioning is an external setting: if already enabled,
AWS can retain old copies independently of overwriting the current key. This
code does not configure that shared-bucket setting or operate on historical
copies.

## Production setup command

`configure_export_bucket` reconciles the same shared application and CloudFront
grants and installs the export retention fallback. It extends matching existing
grants without replacing their principals, resource paths, or conditions. It
preserves unrelated policy/lifecycle entries and removes recognized legacy
export-only statements created by the earlier tooling. Ambiguous statement-ID
collisions are rejected. Repeated runs produce the same configuration.

Run inside the application container using an administrative AWS identity with
bucket configuration permissions. Runtime application credentials only need the
shared data permissions above. The setup identity needs `s3:GetBucketPolicy`,
`s3:GetLifecycleConfiguration`, and `s3:GetBucketObjectLockConfiguration`;
applying additionally needs `s3:PutBucketPolicy` and
`s3:PutLifecycleConfiguration` on this bucket.

Preview (read-only):

```sh
python manage.py configure_export_bucket \
  --reader-arn "<APPLICATION_IAM_ARN>" \
  --cloudfront-distribution-arn "arn:aws:cloudfront::<AWS_ACCOUNT_ID>:distribution/<CLOUDFRONT_DISTRIBUTION_ID>"
```

Apply the previewed configuration:

```sh
python manage.py configure_export_bucket \
  --reader-arn "<APPLICATION_IAM_ARN>" \
  --cloudfront-distribution-arn "arn:aws:cloudfront::<AWS_ACCOUNT_ID>:distribution/<CLOUDFRONT_DISTRIBUTION_ID>" \
  --expected-fingerprint "<fingerprint-from-preview>" \
  --apply
```

`--reader-arn` accepts the application's exact IAM user/role identity and may be
repeated. Wildcards, account-root ARNs, STS session ARNs, and mixed partitions
are rejected. Omit the distribution only when using direct S3 signed URLs; the
command refuses omission when CloudFront signing is configured. It checks for
concurrent changes before writing and reads back the complete result. S3 policy
and lifecycle updates are separate operations; after a partial failure, preview
and rerun. The command never changes Object Lock, public-access-block settings,
or CloudFront behaviors.

## Local setup job

`compose/setup` calls `create_s3_local_buckets` after generating the local
application/test configuration and before migrations and background schedule
installation. Dependent services wait for setup to finish successfully.

Local provisioning uses RustFS credentials and its explicit local endpoint. It
creates/reconciles both development and test buckets, leaves anonymous reads
limited to `media/people/photos/*`, installs GET/HEAD CORS, and merges the same
export lifecycle fallback. Other stored files require signed URLs. It preserves
unrelated lifecycle rules and transition settings, and skips unchanged lifecycle
writes. Do not pass production IAM ARNs to RustFS or run the production policy
command there.

The shared storage backend uses the container endpoint for uploads and cleanup,
and `AWS_S3_BROWSER_ENDPOINT_URL` for browser-visible signed downloads. Public
S3 URLs use the matching configured endpoint's HTTP/HTTPS scheme; other custom
domains retain their configured protocol. This keeps browser URLs usable while
workers use the internal endpoint, without changing production CloudFront HTTPS.

## Retention and failure handling

Only retention remains specific to `exports/`: a two-day lifecycle applied to
all bucket objects would delete unrelated files. This lifecycle filter has no
bearing on the shared access grants above.

The application stops downloads 24 hours after readiness. Celery Beat schedules
worker cleanup; there is no Railway cron job. The `SpeleoDBExportsRetention`
fallback expires current objects and aborts incomplete multipart uploads after
two days. S3 lifecycle processing is asynchronous. Object Lock-enabled buckets
are refused by production setup because retention or legal holds can prevent
cleanup.

Object deletion and multipart abort only operate on the exact attempt-owned key;
adjacent keys and unrelated lifecycle rules are preserved. Existing broader
lifecycle rules still apply and should be checked for overlap.

## Verification

Run the policy/command, local setup, storage transfer, and URL signing tests
inside Docker. They cover shared grants, input immutability, idempotence, legacy
policy migration, collisions, and failed setup. Actual RustFS tests exercise
every concrete S3 backend with `save()` and `upload_file()`, checking signed and
unsigned GETs, stored content/cache/disposition headers, exact-key overwrite,
and deletion. Separate tests verify CloudFront signatures with a temporary key
and ensure local endpoint schemes do not change production CloudFront URLs.

After applying AWS configuration, verify a signed download succeeds, unsigned
CloudFront and anonymous S3 requests fail, and an existing public asset still
works. If private files were previously cached under public behavior, invalidate
those cached paths. Repository tests do not prove that the live distribution has
been updated.

The opt-in large-file test creates a real member larger than 4 GiB in the
isolated test bucket, verifies ZIP64 streaming and checksums, and removes its
objects. It needs at least 16 GiB free in Docker's backing filesystem:

```sh
docker compose -f local.yml exec -T -e SPELEODB_TEST_LARGE_ARCHIVE=1 django \
  pytest speleodb/background_jobs/tests/test_large_archive.py -q -s
```

Run it after other database tests finish. Normal pytest runs skip this capacity
check.

### Recorded local capacity check

The Docker/RustFS run on 2026-09-14 passed with a 4,294,967,313-byte member and
a 4,294,969,785-byte ZIP. Building took 14.83 seconds; source upload, build,
artifact upload, and complete artifact download verification took 35.70 seconds.
Peak process memory was about 405 MiB, an increase of about 130 MiB. Both the
extracted member and downloaded ZIP matched their SHA256 checksums. All test
objects and multipart uploads were removed.

This synthetic local test validates ZIP64, streaming, integrity, and bounded
memory. It does not predict production latency across GitLab and AWS networks.
