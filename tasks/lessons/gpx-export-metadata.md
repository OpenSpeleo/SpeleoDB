# Lesson: GPX Export Metadata Must Be Product-Owned

When adding GPX exports, never rely on dependency defaults for root metadata.
Set the GPX version, namespace/schema behavior, and `creator` explicitly, then
test the raw XML root attributes.

For SpeleoDB exports:

- Use GPX 1.1.
- Preserve the standard Topografix GPX namespace and schema declaration.
- Set `creator="SpeleoDB"` instead of leaking `gpxpy`'s default creator string.
- Assert the raw XML does not contain dependency-branded creator metadata.
