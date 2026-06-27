# Local Object Storage

## Intent and Ownership

Local development and backend tests use RustFS as an S3-compatible object
store. Django serves the private and public map viewers from
`http://localhost:8000`, while RustFS serves signed GeoJSON and GPS-track URLs
from `http://localhost:9000`. Those browser downloads are cross-origin, so the
RustFS bucket owns their CORS response headers. Django's CORS middleware cannot
alter a response returned directly by RustFS.

Production does not use this bootstrap path. Private production files use
CloudFront signed URLs, and production bucket/CDN policy remains external to
the local management command.

## Provisioning Contract

`create_s3_local_buckets` is the single owner of local bucket creation and
configuration. It:

- requires `AWS_S3_ENDPOINT_URL`, preventing accidental use of the default AWS
  endpoint;
- provisions the two canonical buckets, `speleodb-user-artifacts-dev` and
  `speleodb-user-artifacts-test`;
- creates buckets only after an S3 missing-bucket response;
- grants anonymous reads only under `media/people/photos/*`;
- permits cross-origin `GET` and `HEAD` requests from any origin; and
- reapplies policy and CORS configuration safely when a bucket already exists.

Those bucket names are a static local-infrastructure contract. The management
command intentionally does not derive them from `AWS_STORAGE_BUCKET_NAME`, so
an unexpected runtime setting cannot silently create or reconfigure a different
bucket.

The wildcard CORS origin is deliberately limited to local/test buckets. CORS
controls whether browser JavaScript may read a response; it does not grant S3
authorization. Private GeoJSON, GPS tracks, attachments, and default media
still require a valid presigned URL.

Local and test settings explicitly select S3 Signature Version 4. Current
boto3 and django-storages versions already default to SigV4, but making the
choice explicit keeps signed URLs deterministic across compatible object-store
versions. Production CloudFront signing is unchanged.

## One-Time Bootstrap

The Compose `rustfs` service is pinned to the same version used in CI and has a
health check. The `s3-init` service waits for RustFS, runs
`create_s3_local_buckets`, and exits. It is gated behind the `setup` profile and
is not a dependency of Django or the local webserver, so normal builds and
starts never schedule it.

Run it once when the local RustFS volume and buckets are first created:

```bash
docker compose -f local.yml --profile setup run --rm s3-init
```

Run it again only for an intentional local policy/CORS migration. For example,
an existing volume created before bucket CORS was introduced needs one explicit
run to receive the rule; the volume does not need to be deleted.

The same configuration can be applied explicitly from an already-running
Django container:

```bash
python manage.py create_s3_local_buckets
```

CI runs the management command once against its newly created RustFS service
with `config.settings.test`; it does not maintain a separate AWS CLI
provisioning path.

## Diagnostics

A browser may report a generic CORS failure when RustFS actually returned an
authorization or signature error without readable CORS headers. Distinguish
the two failure classes with the exact signed URL from the API response:

```bash
curl -i -H 'Origin: http://localhost:8000' '<presigned-url>'
```

A successful browser-readable response includes
`Access-Control-Allow-Origin: *`. An XML error body such as
`SignatureDoesNotMatch` indicates signing, endpoint, region, or clock skew
rather than a missing bucket CORS rule.

The stored rule can also be inspected directly:

```bash
aws --endpoint-url http://localhost:9000 s3api get-bucket-cors \
  --bucket speleodb-user-artifacts-dev
```

If provisioning fails, use the action- and bucket-specific command error
before resetting any volume. Authorization and RustFS availability failures
are not treated as missing buckets.

## Testing and Performance

Unit tests mock the S3 client and lock down bucket creation, policy, CORS, and
failure behavior. A live RustFS regression uploads a private GeoJSON object,
generates SigV4 `GET` and `HEAD` URLs, sends browser `Origin` headers, and
asserts the returned CORS headers before deleting the object.

Provisioning adds a few S3 control-plane calls during explicit setup only. It
adds no application-startup or Django request-path work, no map feature
rescans, and no production runtime cost. RustFS evaluates the stored CORS rule
while serving the object response.
