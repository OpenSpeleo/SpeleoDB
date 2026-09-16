# Keep one Railway service configuration

The user corrected retaining the deprecated `railway.toml` alongside the
existing Infrastructure as Code configuration. `.railway/railway.ts` is this
repository's sole service configuration. When migrating configuration ownership,
remove the superseded file, its build-context exceptions, and stale operational
references in the same change. Verify that the retained file includes the
intended settings and that Railway has no active custom legacy config path.

Keep `railpack.json` for image construction: its build recipe has a separate
responsibility. Preserve the existing IaC partial name and ownership boundaries;
removing a duplicate config does not authorize taking over unrelated services.
Distinguish committing application code from applying IaC changes, and never
claim that local configuration edits have already changed production.
