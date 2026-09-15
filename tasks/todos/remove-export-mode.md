# Remove the unrequested export mode switch

The user rejected the disabled/staff/all rollout switch. Exports must be
available to authenticated active accounts through ordinary account and resource
permissions, with no separate enablement setting.

## Plan

- [x] Trace the setting and its application, UI, environment, Railway, and
      documentation dependencies; review the complete removal.
- [x] Remove the setting and all mode-specific gating and copy. Keep account
      authorization and the existing concurrent-request protections.
- [x] Update API and controller regressions for normal operation without an
      enablement flag; record the correction in lessons and feature docs.
- [x] Document every remaining export/Kanchi setting as requested, including
      units, scope, and fallback/omission behavior. Wire the Celery task's
      timeout options to the existing settings instead of duplicated literal
      values.
- [x] Set soft/hard generation limits to the requested five/eight minutes in
      settings only. Derive scratch cleanup from the hard limit and preserve the
      existing recovery grace; remove copied durations from documentation.
- [x] Run Python and JavaScript suites inside Docker. The user's final
      instruction is tests and commit only, with no pre-commit execution.
- [x] Review and commit the completed correction. Production deployment and
      pushes remain paused.

## Review

The controller's submit and redraw paths both depended on the removed context
field. Remove those branches together with the template and view context; merely
removing the environment variable would leave the feature disabled. Keep active
account checks in services and all existing API/resource authorization.

## Verification

- Focused API/lifecycle checks passed 33 tests after removing the mode switch.
  The final lifecycle suite passed 20 tests after adding timeout and scratch
  cleanup coverage, including nondefault hard limits.
- The complete JavaScript suite passed **1,019 tests across 59 files** using one
  test process. The normal four-process run encountered process-startup and test
  timeouts under Docker load; no application assertions or timeouts were
  relaxed.
- The production Vite build passed after confirming no disk watcher was active.
- Railway SDK graph validation passed for the four existing application service
  declarations, with no cron schedules. Live `railway config plan` could not
  start because the CLI binary is unavailable inside Docker. No live Railway
  configuration was changed; a current platform preview remains a deployment
  prerequisite.
- The first Python run was deliberately stopped when the user changed the time
  limits, after 2,273 passing tests. The final full run passed **4,289 tests and
  108 subtests**, with **164 skipped**, in 438.60 seconds.
- Pre-commit was not run, as explicitly requested. No service restart, push, or
  deployment was performed during this correction.
