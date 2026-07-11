# Local S3 CORS Hardening

## Implementation

- [x] Harden `create_s3_local_buckets` for local-only, idempotent provisioning.
- [x] Make local and test presigned URL signing explicitly deterministic.
- [x] Align and pin the RustFS version used by Compose and CI.
- [x] Replace recurring automatic initialization with an explicit, profile-gated
      setup job.
- [x] Exercise the real provisioning command during CI setup.

## Tests

- [x] Add management-command unit coverage for success and failure paths.
- [x] Verify local/test presigned URLs use Signature Version 4.
- [x] Add a live RustFS browser-CORS regression test.
- [x] Run focused tests, full backend tests, lint, type checks, and Compose
      validation.

## Documentation

- [x] Document local object-storage ownership, bootstrap, diagnostics, and
      production boundaries.
- [x] Add the new document to the agent documentation index.

## Review

- Correction: canonical bucket names must stay explicit and the initializer must
  not be a normal application startup dependency.
- Reworked the target commit without carrying its unrelated editor setting.
- Confirmed the previously running floating local image was RustFS alpha.83;
  pinned local and CI environments to beta.8 and repaired existing buckets
  through one explicit initializer run.
- Verified 16 focused S3/security tests, including live SigV4 `GET`/`HEAD` CORS
  responses and rejection of unsafe or hostless URL schemes.
- Verified the full backend suite: 3,819 passed and 154 skipped.
- Verified Ruff, strict mypy (520 source files), Compose configuration, and diff
  whitespace checks.
- Verified by Compose dry-run that normal Django startup does not schedule
  `s3-init`; the job is available only through the explicit `setup` profile.
- Verified the repository Bandit hook passes after removing `urlopen`.
- Production CloudFront signing and map-viewer request behavior are unchanged.
