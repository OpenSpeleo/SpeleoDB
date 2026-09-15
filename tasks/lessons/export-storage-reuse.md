# Reuse the configured storage backend

The user corrected the export-specific boto3 client and deliberate CloudFront
bypass. Exports must use the same configured private storage infrastructure as
other files: CloudFront signing in production and browser-reachable S3 signing
locally. Put reusable transfer/cleanup operations on the shared storage backend,
and retain only export-specific policy in the export adapter.

Check both signing modes, persisted object keys, exact-key deletion, and expiry
enforcement. Bucket policy must allow the configured CloudFront origin while
viewer access remains restricted by signed URLs.

The user also requested flat object names: exports/{filename}.zip. Do not add
user/job directories without a requirement. Make the download filename the
stored basename and include the unique attempt ID to prevent retries overwriting
each other. Existing stored keys remain authoritative for historical files.
