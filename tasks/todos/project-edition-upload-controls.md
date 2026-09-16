# Project edition and upload controls

## Plan

- [x] Trace the banner lock action, upload form events, and existing tests.
- [x] Check in with the implementation plan before changing behavior.
- [x] Reuse the mutex controller for the banner: POST the existing acquire API
      with CSRF, prevent duplicate requests, and reload the current page
      immediately after success. Preserve permission gates and display
      acquisition errors.
- [x] Make Upload Revision a real form submit control and route Enter and clicks
      through the same validation/upload handler, preventing native navigation.
- [x] Add regression coverage for rendered controls, lock acquisition and
      permissions, immediate reload/error handling, and upload submission.
- [x] Document ownership, behavior, verification, and performance under docs/.
- [x] Run JavaScript tests, focused Django tests, lint, and a clean production
      asset build inside the existing application container; review the final
      diff and record results in tasks/todo.md.

## Design

The lock API remains the permission and concurrency authority. The banner uses
the existing mutex controller, with its own inert context placed in the
inherited content so child script blocks cannot remove it. Project pages share
one error modal, including read-only content pages that previously had no
mutation action. Acquisition reloads immediately; existing unlock feedback
remains unchanged.

The upload bug is native form navigation: the footer button is outside the form,
has type=button, and only clicks trigger the AJAX upload. Associate a submit
button with the form and handle submit rather than keyboard-specific events.

## Review

Implemented the banner with the shared mutex controller, immediate successful
acquisition reload, disabled pending controls, and centralized project error
modal. Upload now uses native form submission for both Enter and button clicks.

Container verification:

- Full JavaScript suite: 1,040 tests passed across 64 files (8 new regressions).
- Focused Django banner and template suite: 57 passed.
- Root JavaScript lint, focused Ruff and mypy, and changed-template djLint pass.
- Clean production Vite build passed; all 99 manifest outputs and all registered
  sources exist. Both changed controller assets served by Django exactly match
  the built bytes (mutex: controller-mutex-lock-CNpT6aEG.js; upload:
  controller-project-upload-DoyVAIIH.js).
- A competing watcher in the webserver container initially caused ENOTEMPTY
  during clean. Stopped it, rebuilt successfully, verified production assets
  over HTTP, then restored the development watcher.
- GitLab audit b4294628e50543ca94fd1f7638488a1f: 0 creations, 0 creation POSTs,
  0 violations, no unresolved allocations; no remote cleanup required.
- Independent diff review found no concrete regressions. JSDOM verifies native
  submit/reload calls but does not simulate actual Enter default behavior or
  perform real browser navigation.

See docs/project-edition-and-upload.md for design and verification boundaries.
