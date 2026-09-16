# GitLab cleanup is manually triggered

The user requested removal of the cron after confirming pytest cleans up its own
repositories. Keep the cleanup workflow available through `workflow_dispatch`
only. Do not reintroduce scheduled cleanup as an automatic fallback without an
explicit request. Preserve the stale-age filter and bounded pytest runtime
already approved for safe concurrent branch runs.
