# Remove unsolicited export encryption configuration

The user requested downloadable ZIP backups without adding an export encryption
policy. Remove the extra production/test settings and S3 request override;
uploads follow the bucket's existing configuration.

- [x] Remove export encryption settings, environment entries, and upload header.
- [x] Correct feature/operations documentation and capture the scope lesson.
- [x] Verify actual archive upload/download inside Docker.

## Review

The real ZIP64/S3 integration test passed inside Docker: a 4,294,967,313-byte
member was archived, uploaded, downloaded, and checksum-verified with bounded
memory. Continue the separately requested adversarial review and container-only
full checks before committing. Push and deployment remain paused.
