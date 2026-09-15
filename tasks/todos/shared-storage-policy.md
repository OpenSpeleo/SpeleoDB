# Complete shared S3 policy and setup consistency

- [x] Inspect the supplied production policy, storage signing, and setup
      commands.
- [x] Verify S3 action requirements and CloudFront signed URL behavior in AWS
      docs.
- [x] Put the complete updated policy inline and in the downloadable JSON
      example.
- [x] Reuse the existing bucket-wide application and CloudFront grants in setup.
- [x] Audit local provisioning and preserve private signed/public photo
      behavior.
- [x] Verify setup, policy builders, downloads, lint, and types; record the
      result.
- [x] Replace production AWS identifiers with documentation placeholders and
      render those placeholders with fictional values in the example test.

## Plan check-in

The user explicitly requests complete policies and extending existing shared
grants instead of adding export-specific grants. Keep the existing bucket/object
resources and exact CloudFront distribution. Retention remains scoped to exports
because deleting all bucket contents after two days would be incorrect.
Downloads continue through the shared storage backend and existing signing key.
This is a repository code/documentation correction; no AWS configuration is
applied by editing the document or running local verification.

## Review

The full inline policy and JSON example contain the same three statements as the
supplied policy. Five application actions and CloudFront version reads are
merged into the existing bucket-wide grants. Production setup generates that
exact policy, preserves unrelated entries, and removes only recognized legacy
export-specific controls. No new download signing mechanism is introduced.

Local setup now installs the same two-day lifecycle through a shared builder. It
preserves unrelated lifecycle rules and versioning, keeps exports private, and
leaves public photos available. Retention is the only prefix-scoped policy.

Verification: inline JSON, complete example, and production builder output match
exactly. Local setup, real RustFS export transfers, versioned deletion, and
multipart cleanup tests: 23 passed. Independent review found no actionable
issue. Production policy/command tests: 40 passed, covering the supplied full
policy, existing-grant preservation, recognized legacy migration, collisions,
idempotence, previews, and apply/readback. Full mypy passed all 708 source
files; Ruff and format checks passed all 14 Python files owned across the
storage and clock corrections. `git diff --check` passed. No live AWS
configuration was changed. The 63 storage/setup cases supplement the 167
clock-related regression cases (one skipped) recorded in the clock task.

## Identifier privacy correction

The user requested a generic CloudFront ARN and no production AWS identifiers in
documentation. Replace account/distribution, application identity, and bucket
values in both policy examples and command snippets. Keep exact resource
scoping; placeholders must be substituted, not changed to permission wildcards.
Update the existing example parity test to use fictional identities.

Completed: both full policies and shell snippets now use explicit placeholders;
the example test renders them with fictional values. Repository search found no
remaining original account/distribution or application IAM ARN in non-ignored
files. The updated example test passed, full mypy passed 708 source files, Ruff
and formatting passed, and the inline/document JSON templates match exactly.
