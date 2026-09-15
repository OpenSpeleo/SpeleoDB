# Show complete policies and reuse existing shared grants

The user corrected an export policy that added several feature-specific grants
even though the existing application and CloudFront statements already covered
the bucket and all object keys.

- When given a complete policy, provide a complete replacement inline and keep
  the downloadable example identical. An additions table alone is insufficient.
- Extend the existing shared application/CloudFront action lists when their
  principal and resource scope already match the requested storage operations.
  Do not introduce a feature-specific access-policy layer without a requirement.
- Keep setup commands aligned with the documented policy; otherwise rerunning
  setup silently reinstalls the design the user rejected.
- Distinguish origin access grants from signed viewer access. Reuse an existing
  private CloudFront behavior and signing identity when available.
- Retention still needs a feature prefix: export cleanup must not delete other
  stored files. This does not require a separate export access grant.
- Do not copy production AWS account IDs, distribution IDs, IAM identities, or
  bucket identifiers into checked-in examples. Use explicit placeholders and
  fictional test values. Keep full policies and command snippets consistent,
  quote placeholders in shell examples, and retain exact ARN restrictions.
- The user requires ordinary export files: writing the same key overwrites it.
  Do not add S3 version tracking, version-specific URLs/permissions, or
  mandatory CloudFront query forwarding. Store download headers on the object at
  upload and use the existing storage backend's ordinary signed URL method.
- A provider or endpoint bug affects every storage manager. Fix shared behavior
  and verify media, photos, attachments, vectors, exports and static files,
  including unsigned public downloads. Prefer a verified provider fix over
  per-feature response-header workarounds. Public and private classes must share
  transport, endpoint and transfer logic while retaining their access policies.
