# Plain export files with overwrite semantics

- [x] Remove object-version fields, runtime arguments, and version-aware S3
      calls.
- [x] Make exact-key uploads/save overwrite and downloads ordinary signed URLs.
- [x] Remove version permissions and lifecycle rules from setup and full
      policies.
- [x] Update affected tests and documentation; retain generic storage reuse.
- [x] Share endpoint handling across every public/private S3 backend, including
      static files.
- [x] Upgrade local/CI RustFS to a release that returns stored headers on GET.
- [x] Exercise uploads, downloads, headers, access and cleanup for every
      backend.
- [x] Verify overwrite/download/deletion, retry lifecycle, migration, lint,
      types.

## Plan check-in

The user explicitly rejected all export versioning and requires overwriting an
existing key. Remove the added versioning machinery throughout the export path,
including persisted version IDs and CloudFront query requirements. Preserve
ordinary object metadata, private signing, bounded multipart upload/cleanup,
finite retries, and existing flat filenames. The shared bucket's live AWS
configuration is not changed by source edits. Preserve staged user work.

## Review

The initial regression run exposed RustFS omitting stored Content-Disposition
and Cache-Control on GET while returning them correctly on HEAD. The user's
follow-up requires fixing shared behavior for all local managers. Upgrade the
provider instead of compensating with export-specific download parameters.
RustFS rc.1 includes both header fixes and a legacy-data compatibility fix. All
storage classes share the browser endpoint/transport base and ordinary URL
handling, with explicit public/private access classes. Preserve existing model
filename rules and public cache policies; exports overwrite the reserved key.

### Final verification

- Background-job, export API, provisioning, storage and signing suite: 256
  passed, 9 skipped. All eight concrete backend cases exercised real
  save/upload, overwrite, GET/HEAD metadata, public/private access and deletion
  against rc.1.
- The five opt-in live Celery cases were then run separately: 5 passed,
  including actual generation, signed ZIP download with stored headers,
  notification, expiry cleanup, duplicate delivery, broker failure and worker
  recovery.
- Full mypy: 710 source files, no issues. Ruff and format checks passed all
  affected Python files. `makemigrations --check --dry-run`: no changes
  detected.
- Compose and CI use the same rc.1 image and matching explicit test credentials;
  the old default secret is rejected by newer RustFS releases. YAML validation,
  full inline policy/JSON parity and `git diff --check` passed.
- Restarted only local RustFS, preserving its volume. Health passed, and an
  object written before the upgrade retained identical contents afterwards. The
  probe and the integration matrix's disposable bucket were cleaned up.
- Review found the CI default-credential startup issue; it was corrected. The
  resulting runtime calls, migration and shared classes have no known blocker.

Production AWS settings were not changed. Deploy the new migration with the
application; historical migrations remain intact. The opt-in >4 GiB capacity
test was collected but not rerun because transfer buffering did not change.
