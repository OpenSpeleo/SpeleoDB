# Upload reporting is independent of HTTP status

The user requires Sentry reports for Git, file-processing, and input-processing
failures during upload. A 400 or 415 response describes the API outcome; it does
not mean an operator should be denied an error report.

- Explicitly capture caught upload exceptions regardless of HTTP status.
- Include input rejection, optional conversion, and cleanup paths in the audit.
- Preserve normal no-op outcomes and established upload/rollback semantics.
- Do not equate admin email routing with Sentry capture. ERROR logs can produce
  Sentry events through LoggingIntegration even when explicit capture is absent.
- SDK event-construction tests prove application reporting, not remote ingestion
  or the account's alert notification rules.
