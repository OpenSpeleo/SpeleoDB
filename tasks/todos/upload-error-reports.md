# Upload error reports

## Problem and scope

An Ariane upload raises `zipfile.BadZipFile`, logs the traceback, and returns
HTTP 400 without the expected operator error report. Preserve the response and
upload rollback while repairing the reporting path. Existing GitLab test-budget
work is unrelated and must be preserved.

## Plan

- [x] Trace upload exception handling, production logging, and reporting tests.
- [x] Confirm the expected report channel and check in with the proposed fix.
- [x] Reproduce the corrupt ZIP with real parser/reporting code and verify
      capture.
- [x] Apply the reporting correction without changing HTTP semantics.
- [x] Verify regression coverage, lint, and types in the running container;
      inspect any GitLab creation audit and cleanup.
- [x] Update the upload design documentation and record review/results in
      `tasks/todo.md`.

## Initial findings

- `FileUploadView.put()` catches `BadZipFile` and returns HTTP 400.
- `handle_exception()` logs at ERROR but explicitly captures Sentry only for
  5xx.
- The production root logger has only a console handler; admin email handles
  `django.request` ERROR records, while Django logs HTTP 400 as WARNING.
- Production Sentry logging integration can independently capture ERROR logs;
  the missing explicit capture alone does not prove no Sentry event existed.

## Review

`handle_exception()` now captures every caught upload failure, including 400
validation/parser failures and 415 file rejections. Direct input validation
responses emit Sentry error messages; the view explicitly captures DRF request
parsing errors. Optional conversion/S3 failures and secondary Git cleanup
exceptions also report without changing the established response behavior.

Verification inside `speleodb_local_django`, after the pre-existing full test
invocation finished:

- Upload error handling, cross-API error reporting, and upload GeoJSON suites:
  **33 passed, 1 skipped**. The skip is the existing PostgreSQL-only immediate
  foreign-key/savepoint test in this SQLite run.
- A real invalid Ariane ZIP proves `BadZipFile`, traceback construction, HTTP
  400, rollback, and clean Git state. SDK logging plus explicit capture produces
  exactly one event for the same exception. Git lock cleanup produces two
  distinct reports, preserving the original exception.
- Input validation, rejected file types, malformed JSON, unsupported request
  media types, optional Ariane/Compass conversion failures, successful uploads,
  unchanged uploads, and incomplete optional Compass bundles are covered.
- Ruff checks and formatting passed. Full mypy passed for **725 source files**.
- Final GitLab audit `4a674aaf3c6e41ceab829d8e81cb7a87`: **2 creations, 2
  creation POSTs, 0 violations, no unresolved outcomes**; both canonical
  repositories were marked for deletion by session cleanup. The initial test run
  also created two repositories, with zero violations and both marked for
  deletion; its three failures were corrected test assumptions about native
  parser errors and a format-validation route.
- Independent code/docs review completed; its reachable-validation test finding
  was addressed. `git diff --check` passed. Existing staged/unstaged GitLab work
  was preserved.

No production deployment or Sentry delivery test was performed. Production's
existing LoggingIntegration should already capture the original ERROR log; local
code cannot establish why that historical issue/alert was absent. Existing
Compass model ERROR messages can produce a separate message event alongside the
captured conversion exception; this change does not redesign the model's logging
policy.

## Confirmed reporting policy

The user expects Sentry issues/alerts for Git, file-processing, and
input-processing errors, including 400 and 415 responses. Remove the status
gate; report direct input rejections and caught request parsing errors as well
as optional conversion and cleanup failures. Preserve response semantics and
normal no-op outcomes (unchanged files, missing geographic anchors, empty
surveys, incomplete optional Compass bundles). Verify actual SDK event creation
with external delivery disabled. An existing full-suite invocation must finish
before starting our pytest run.
