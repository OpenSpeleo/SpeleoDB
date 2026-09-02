# Local Object Storage

## Intent and Ownership

Local development and backend tests use RustFS as an S3-compatible object store.
Django serves the private and public map viewers from `http://localhost:8000`,
while RustFS serves signed GeoJSON and GPS-track URLs from
`http://localhost:9000`. Those browser downloads are cross-origin, so the RustFS
bucket owns their CORS response headers. Django's CORS middleware cannot alter a
response returned directly by RustFS.

Production does not use this bootstrap path. Private production files use
CloudFront signed URLs, and production bucket/CDN policy remains external to the
local management command.

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
command intentionally does not derive them from `AWS_STORAGE_BUCKET_NAME`, so an
unexpected runtime setting cannot silently create or reconfigure a different
bucket.

The wildcard CORS origin is deliberately limited to local/test buckets. CORS
controls whether browser JavaScript may read a response; it does not grant S3
authorization. Private GeoJSON, GPS tracks, attachments, and default media still
require a valid presigned URL.

Local and test settings explicitly select S3 Signature Version 4. Current boto3
and django-storages versions already default to SigV4, but making the choice
explicit keeps signed URLs deterministic across compatible object-store
versions. Production CloudFront signing is unchanged.

## Automatic Local Bootstrap

The Compose `setup` job is a required one-shot dependency of both the Django
workspace and `django-webserver`. Compose does not start either application
service until PostgreSQL, Redis, RustFS, and GitLab are healthy and `setup`
exits successfully. GitLab uses its full readiness probe, including its own
database, Redis, and Gitaly checks; a first GitLab boot can take many minutes.

On its first run, the setup job copies `.env.dist` to the ignored `.env` and
`.envs/test.env.dist` to the ignored `.envs/test.env`. Existing files are never
replaced. The job then uses the existing `python-gitlab` dependency to provision
the development `speleodb` group and the isolated `speleodb-test` group. Each
group receives its own named, non-expiring access token, validated against the
credential stored in its corresponding private env file and replaced only when
missing, expired, or invalid. Group IDs are discovered independently and never
assumed. The local GitLab bootstrap disables access-token expiration
enforcement and rotates any older expiring token. Normal Django settings load
the development resources from `.env`, while `config.settings.test` loads only
the test resources from `.envs/test.env`.

The same job then runs `create_s3_local_buckets`. The command creates missing
RustFS buckets and reapplies the canonical local policy and CORS configuration
idempotently. It writes `speleodb-user-artifacts-dev` and its concrete custom
domain to `.env`, and separately writes `speleodb-user-artifacts-test` and its
custom domain to `.envs/test.env`, before invoking the Django command. Both
buckets use the local RustFS service but do not share object namespaces.

After object-storage setup, the same one-shot job applies migrations and runs
`ensure_local_superuser`. The DEBUG-only command creates or repairs
`contact@speleodb.org` with password `contact`, bypasses password validation for
that fixed local credential, sets its country to USA (stored as `US`), and
marks its allauth email record verified and primary.

Every `docker compose up` may rerun the one-shot job. Existing valid GitLab and
RustFS resources are reused. If either persistent volume is reset, the next run
recreates the missing resources and refreshes stale development and test env
values without requiring a hard-coded group ID.

For a clean test without touching existing volumes, use a different Compose
project and container prefix:

```bash
COMPOSE_INSTANCE_PREFIX=speleodb_fresh \
  docker compose -p speleodb_fresh -f local.yml up --build django-webserver
```

Compose creates new project-prefixed volumes. The old stack must be stopped so
the standard host ports are available, but its containers and volumes do not
need to be removed. `docker compose ... down` preserves the fresh volumes too;
avoid `--volumes` unless deletion is explicitly intended.

The project also owns `/app/node_modules` as a named volume. Container-side
Linux optional dependencies therefore remain separate from host-native npm
installs even though the rest of the source tree is bind-mounted at `/app`.
The root setup job initializes or migrates that volume to `dev-user` ownership,
while both Django application services run as `dev-user`. Consequently `npm
ci`, the Vite watcher, pre-commit builds, and interactive devcontainer commands
all share one writer identity. The setup job checks the volume-root ownership
before any recursive migration, so established volumes do not pay for a full
`node_modules` traversal on every startup. Host `node_modules` is excluded from
the image build context, and the volume uses `nocopy: true`, so image contents
cannot seed a fresh Linux dependency volume. The devcontainer disables
per-service remote UID rewriting because the setup, workspace, and webserver
must agree that `dev-user` is UID/GID 1000 across the shared volume.

The standalone Compose stack exposes the host-networked Django process on Linux.
The root devcontainer instead publishes port 8000 on host loopback from its
workspace container and runs the webserver in that shared network namespace,
making `http://localhost:8000` available in both VS Code and Zed. Internal
Django requests use the `rustfs` Compose hostname while browser-facing URLs are
signed separately with `AWS_S3_BROWSER_ENDPOINT_URL` and retain
`localhost:9000`. Its setup service also uses Compose DNS for
provisioning while persisting browser-facing GitLab and RustFS addresses. The
container-local database health check is `/api/health/details/`.

The root devcontainer also supplies test-only internal GitLab and RustFS
endpoints. `config.settings.test` applies them after loading the standalone test
environment, so the same test suite reaches Compose services in the root
container while standalone tests keep their host-networked `localhost` values.

The RustFS configuration can still be applied explicitly from an already-running
Django container:

```bash
python manage.py create_s3_local_buckets
```

CI runs the management command once against its newly created RustFS service
with `config.settings.test`; it does not maintain a separate AWS CLI
provisioning path.

## Diagnostics

A browser may report a generic CORS failure when RustFS actually returned an
authorization or signature error without readable CORS headers. Distinguish the
two failure classes with the exact signed URL from the API response:

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

If provisioning fails, use the action- and bucket-specific command error before
resetting any volume. Authorization and RustFS availability failures are not
treated as missing buckets.

## Testing and Performance

Unit tests mock the S3 client and lock down bucket creation, policy, CORS, and
failure behavior. A live RustFS regression uploads a private GeoJSON object,
generates SigV4 `GET` and `HEAD` URLs, sends browser `Origin` headers, and
asserts the returned CORS headers before deleting the object.

Provisioning adds a few GitLab and S3 control-plane calls before local services
start. It adds no Django request-path work, no map feature rescans, and no
production runtime cost. RustFS evaluates the stored CORS rule while serving the
object response.
