# Cache export archives through the existing managed CloudFront policy

- [x] Reuse the normal shared storage cache headers for export objects.
- [x] Update actual object-header and worker regressions.
- [x] Align documentation with the cacheable archive and uncached redirect.
- [x] Run storage/API regressions, live generation, Ruff and mypy.

## Plan check-in

The user wants caching retained and asks to remove the export no-cache header.
Use the existing `BaseS3Storage.object_parameters` policy, as attachments and
GeoJSON already do. Keep the shared private signing/access implementation and
the authenticated API redirect's no-store header: cached redirects could reuse
an expired signed URL. This changes new export upload metadata in both local and
production storage; it does not rewrite existing objects or CloudFront.

## Review

`ExportStorage` now uses `BaseS3Storage.object_parameters` directly, producing
`Cache-Control: public, max-age=86400` like other cacheable storage backends.
Private signing and bucket access still apply. The API redirect keeps no-store
to avoid reusing expired signed links. Existing object metadata is unchanged;
newly generated exports receive the shared cache metadata after deployment.

Verification inside Docker: 85 storage, signing and API tests passed, including
real RustFS downloads across all eight backends and anonymous-access rejection.
The live generation/download/notification/expiration case passed separately.
Full mypy passed on 710 files; Ruff, formatting and diff checks passed.

The initial live run timed out while another pytest process was using the shared
test database. Repeating it with a unique test database and separate dedicated
broker database passed in 10.13 seconds. Future concurrent live checks must use
isolated database and broker namespaces. No CloudFront or production S3 changes
were made.
