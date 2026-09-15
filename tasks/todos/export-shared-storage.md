# Export storage reuse and CloudFront delivery

- [x] Inspect existing private storage backends, export operations, and policy.
- [x] Verify AWS permissions and CloudFront requirements against primary docs.
- [x] Reuse shared S3 connection, upload, signing, and version cleanup behavior;
      retain immutable export keys, bounded uploads, and expiry enforcement.
- [x] Store new exports directly as exports/{filename}.zip; keep filenames
      unique per attempt and retain access/cleanup for stored legacy keys.
- [x] Align the bucket configuration helper with authenticated CloudFront reads
      and provide a concrete policy update for the supplied production bucket.
- [x] Test existing backends and export storage against local S3, plus production
      CloudFront signing, versioned objects, cleanup, and expiry regressions.
- [x] Run focused pytest, Ruff, and mypy; review the final diff and update docs,
      lessons, and tasks/todo.md.

## Plan check-in

The user authorized reusing generic storage code and following the existing
production CloudFront/local S3 patterns. Preserve existing private/public storage
behavior and local browser endpoint handling. S3 policy changes will be provided
as a concrete artifact; inspect live configuration read-only if possible.

## Review

Implemented and reviewed. `PrivateS3Storage` centralizes configured CloudFront
or local S3 URL signing. `BrowserFacingS3Storage` supplies shared exact-name
streaming uploads, location-safe object keys, permanent version cleanup, and
CloudFront HTTP query-name conversion. The export adapter contains only prefix
validation and ZIP metadata. Runtime credentials, endpoint/session configuration,
and region now come from django-storages. Existing public storage stays unsigned.

New attempts reserve flat `exports/speleodb-export-<UTC timestamp>-<attempt UUID>.zip`
keys. Generation uses that basename for the artifact and download filename.
Historical nested keys remain readable and cleanable. Each retry uses a new
attempt ID. No schema migration is required. Seven obsolete type-ignore comments
on existing model storage constructors were removed because the shared private
constructor is now typed; model fields are otherwise unchanged.

The policy builder/command accepts an exact CloudFront distribution ARN and
preserves unrelated policies/lifecycle settings. It refuses an IAM-only deny
when CloudFront signing is active. The complete example policy preserves the
user-supplied statements and adds missing runtime/versioned OAC permissions.
Documentation includes the required exports cache behavior and deployment order.

### Verification

- Existing storage/lifecycle/retention/export API suites: 52 passed, 1 skipped.
- Actual RustFS export upload/download/cleanup and prefix guards: 5 passed.
  Both flat and legacy keys cross the multipart threshold and preserve data,
  content disposition, content type, SHA metadata, and no-store headers.
- Disposable local versioned bucket and multipart-neighbor cleanup tests passed
  in the existing storage suite.
- Real isolated Redis/PostgreSQL worker suite: 5 passed. This covers export,
  download, notification, expiry, duplicate delivery, broker failure, and worker
  death/retry recovery; new flat artifact keys match download names.
- Bucket policy/command suite: 29 passed; production JSON matches builder output.
- Existing local bucket provisioning/CORS tests: 9 passed.
- URL tests: 39 passed with real ephemeral RSA signatures. A local-only install
  passes 24 and explicitly skips 15 production-signing cases. For full coverage,
  the existing production pin cryptography==50.0.1 was installed only in the
  disposable test container; manifests and lockfile were unchanged.
- Total completed targeted suites: 139 passed, 1 skipped. Full mypy passed all
  695 source files; Ruff passed on task-owned files; git diff --check passed.
- `makemigrations --check --dry-run`: no changes detected. Independent review
  found no actionable regression. The opt-in 4 GiB load test was not rerun;
  transfer code retains the existing bounded two-thread/16 MiB configuration.

### Live AWS audit and remaining deployment prerequisite

Read-only production checks found signed CloudFront HEAD 200 and unsigned HEAD
403 for an existing export. Latest S3 HEAD succeeded, but an explicit HEAD of
its actual version returned 403. Multipart/version listings also returned 403.
A CloudFront request with a nonexistent versionId returned 200 and a cache hit;
the response-header override was ignored. Thus the current distribution does
not preserve the version/query semantics required by the updated backend.

Administrative policy/lifecycle/versioning/distribution configuration reads were
denied to the application identity. No AWS writes or source deployments were
performed. The operator must apply the provided policy and exports/* CloudFront
behavior (trusted signing, CachingDisabled, query forwarding) before deployment,
then verify exact-version download and nonexistent-version rejection. This live
configuration prerequisite is not covered by the local signature tests.
