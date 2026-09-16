# API Error Handling & Observability

How all API views handle failures, why `ATOMIC_REQUESTS` requires explicit
rollback for caught exceptions, and how Sentry / admin-email reporting works.

---

## Architecture overview

```
Client PUT /api/v2/projects/<id>/upload/<format>/
  │
  ▼
FileUploadView.put()
  ├─ validate input
  ├─ checkout_commit_or_default_pull_branch()   ← git pull / clone
  │    └─ construct_git_history_from_project()  ← sync ProjectCommit rows
  ├─ processor.add_to_project(file)             ← write to working tree
  ├─ commit_and_push_project()                  ← git add/commit/push
  │    └─ construct_git_history_from_project()  ← sync ProjectCommit rows
  ├─ create_project_geojson()                   ← optional GeoJSON
  └─ return SuccessResponse
```

Every step above can fail. The view preserves the appropriate client response
(including 400, 415, and 500) while reporting upload input, file-processing, and
Git failures to Sentry. Optional GeoJSON generation may fail after the source
commit succeeds; those failures are reported without changing the successful
upload response.

---

## Why `ATOMIC_REQUESTS` + caught exceptions = data integrity risk

Django's `ATOMIC_REQUESTS` wraps every view call in `transaction.atomic()`. The
`atomic()` context manager **only rolls back if an exception propagates**. It
does **not** inspect the HTTP status code of the response.

If the view catches an internal exception and returns
`ErrorResponse(status=500)`, Django sees a successful view execution and
**commits** the transaction. Any ORM writes that happened before the failure —
`Format.objects.get_or_create()`, `ProjectCommit` inserts, etc. — are persisted
despite the logical failure.

### The fix: `transaction.set_rollback(True)`

`handle_exception()` in `file.py` calls `transaction.set_rollback(True)`
unconditionally — for **all** status codes, not just 5xx. If we reach
`handle_exception`, the upload did not succeed and no partial writes should be
committed. This tells Django's `ATOMIC_REQUESTS` to roll back the entire
transaction even though no exception propagated, eliminating the need for manual
ORM cleanup.

Git working-tree cleanup (`reset_and_remove_untracked()`) is still performed
because git operations are outside the DB transaction.

### Static public endpoints

Robots and advertising-policy text, icon redirects, and `.well-known` discovery
responses do not read or write application rows. Their view functions explicitly
use `transaction.non_atomic_requests` so serving static content does not open a
database transaction. The decorator belongs on the final view callable, outside
DRF's `api_view`; URL-level cache wrappers preserve that marker.

Keep `ATOMIC_REQUESTS=True` in production and test settings for database-backed
APIs. The static endpoint tests intentionally use `SimpleTestCase`, which
forbids database access and verifies this boundary with SQLite and PostgreSQL
alike.

---

## Why admin email shows `Traceback: None`

Django's `BaseHandler.get_response()` calls `log_response()` for all responses
with `status_code >= 400`. This `log_response` call does **not** pass `exc_info`
because there is no active Python exception at that point (the view already
caught it). For 5xx responses, the `django.request` logger fires at ERROR level
→ `AdminEmailHandler` → `ExceptionReporter` with no traceback →
`Traceback (most recent call last): None`.

For 4xx responses, Django logs at WARNING instead. Production's admin-email
handler requires ERROR, and application loggers use the console handler, so an
upload's application ERROR log does not itself send an admin email. Sentry issue
reporting is a separate path; the upload reporting policy below does not change
admin-email configuration.

---

## How caught exceptions reach Sentry

Sentry's `DjangoIntegration` observes unhandled request exceptions. A view that
catches an exception and returns an error response does not emit Django's
`got_request_exception` signal for that exception, so response status alone does
not guarantee an exception event.

Production also enables `LoggingIntegration(event_level=logging.ERROR)`, which
captures application ERROR logs, including `logger.exception(...)`. The SDK
patches `logging.Logger.callHandlers`; `propagate=False` does **not** prevent
that capture. `DjangoIntegration` explicitly ignores `django.request` and
`django.server` for logging events to avoid duplicate framework reports.

Previously, upload `handle_exception()` explicitly captured only 5xx failures. A
caught `BadZipFile` returned 400 and skipped that call. Its application ERROR
log should still have produced an event when production's logging integration
was active, so the status guard alone cannot establish why a particular
production issue or alert was absent.

### Upload reporting policy

HTTP status describes the client's outcome; it does not decide whether an
operator needs a report. Reporting stays in the project-upload view so other API
endpoints retain their existing policies.

- `handle_exception()` logs the original traceback and calls
  `sentry_sdk.capture_exception(...)` for every handled upload failure,
  including 400 validation/parser errors, 415 rejected files, and 500 Git or
  internal failures. Transaction rollback and existing-checkout cleanup retain
  their existing behavior.
- `upload_input_error()` uses `capture_message(..., level="error")` for direct
  validation responses, such as missing files or messages, unsupported formats,
  and file-count/size limits. These branches have no raised exception, so they
  report the validation message without manufacturing a traceback.
- `FileUploadView.handle_exception()` captures DRF parsing, media-type, and
  validation exceptions that escape `put()`, then delegates to DRF to preserve
  response behavior. Unexpected exceptions that propagate beyond DRF retain
  Django's normal unhandled-exception reporting. Ordinary authentication and
  permission rejections are outside this processing policy.
- Caught optional GeoJSON conversion and S3 failures are captured even when the
  uploaded source has already been committed successfully. A secondary Git
  cleanup failure is captured independently of the original upload failure.
- Normal no-op outcomes remain unchanged: duplicate or unchanged files, absent
  GPS anchors, empty surveys, excluded GeoJSON generation, and an incomplete
  Compass bundle without a MAK file. They do not become processing failures.

The default SDK deduplication integration prevents the same exception object
from producing duplicate events when both logging and explicit capture run.
Reporting adds no database queries, file rescans, or Git operations; validation
reports do not invoke upload rollback or repository cleanup.

`DRFWrapResponseMiddleware` remains a legacy `/api/v1/` backstop. It logs and
explicitly captures caught internal exceptions. It returns `/api/v2/` responses
verbatim, so it does not provide reporting for v2 uploads.

Local tests observe real SDK event construction through `before_send`, with an
empty DSN to prevent external delivery. They verify capture policy and exception
identity, not remote ingestion or alert delivery. Production DSN/integration
state, transport failures, issue grouping, filters, and alert rules require
separate runtime evidence; remote ingestion and alert delivery have not been
verified by these tests.

---

## `construct_git_history_from_project` and savepoints

This method syncs `ProjectCommit` rows from git history.
`ProjectCommit.get_or_create_from_commit` uses Django's built-in
`objects.get_or_create()` which handles savepoints internally — if the
`create()` step hits an `IntegrityError`, `get_or_create` rolls back to its own
savepoint and retries with `get()`. The outer transaction stays healthy.

**Important:** `get_or_create()` already handles savepoints. Do NOT wrap it in
an extra `transaction.atomic()` — that is redundant. A raw
`Model.objects.create()` does NOT create a savepoint, so if you catch
`IntegrityError` around a plain `create()`, you DO need `transaction.atomic()`
(see `station_tag.py` for an example).

---

## Git retry strategy for `commit_and_push_project`

When multiple gunicorn workers process overlapping requests for the same
project, `index.add()` or `index.commit()` can fail with `GitCommandError` due
to `index.lock` contention.

All three operations (`index.add`, `index.commit`, `git push`) use
`retry_with_backoff()` from `speleodb/utils/helpers.py` with exponential backoff
(base 0.1s, factor 2x, up to `DJANGO_GIT_RETRY_ATTEMPTS` = 5 attempts).

```python
from speleodb.utils.helpers import retry_with_backoff

retry_with_backoff(
    fn,
    *args,
    retries=5,
    exc_types=(GitCommandError,),
    base_delay=0.1,  # first retry after 0.1s
    backoff_factor=2.0,  # then 0.2s, 0.4s, 0.8s ...
    **kwargs,
)
```

Git's own lock files are **never** manually deleted. The lock belongs to the git
process that created it; removing it from under a live process would corrupt the
index. Retrying with a sleep lets the competing process finish and release the
lock naturally.

---

## Three-step protocol for all API views

Every `except` block in any API view that returns an `ErrorResponse` with
status >= 500 **must** follow this protocol:

1. **`logger.exception(...)`** — preserves the full traceback in console/Railway
   logs.
2. **`sentry_sdk.capture_exception(exc)`** — creates a Sentry event with
   traceback, tags, and request context.
3. **`transaction.set_rollback(True)`** — required **only** when ORM writes
   (`create`, `save`, `get_or_create`, etc.) happen inside the `try` block
   before the error. Tells Django's `ATOMIC_REQUESTS` to roll back the entire
   transaction.

For project uploads, the reporting policy above also applies to 4xx input and
processing failures. Other endpoints retain their own expected-input-error
policies. Rollback depends on whether failed work may have written database
rows, not on whether the response is 4xx or 5xx; upload `handle_exception()`
always rolls back.

### Files covered by this protocol

| File                  | View                          | Sentry | Rollback | Notes                                                                                                                                            |
| --------------------- | ----------------------------- | ------ | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| `file.py`             | `FileUploadView`              | Yes    | Yes      | all upload processing failures; rollback through `handle_exception()`, separate reporting for input validation and optional conversion failures  |
| `file.py`             | `FileDownloadView`            | Yes    | No       | read-only, no DB writes                                                                                                                          |
| `gpx_import.py`       | `GPXImportView`               | Yes    | Yes      | `Landmark` + `GPSTrack` writes                                                                                                                   |
| `kml_kmz_import.py`   | `KML_KMZ_ImportView`          | Yes    | Yes      | `Landmark` writes                                                                                                                                |
| `project_explorer.py` | `ProjectGitExplorerApiView`   | Yes    | No       | read-only                                                                                                                                        |
| `project.py`          | `ProjectSpecificApiView`      | Yes    | No       | read-only                                                                                                                                        |
| `gis_view.py`         | `GISViewDataApiView`          | Yes    | No       | read-only                                                                                                                                        |
| `gis_view.py`         | `PublicGISViewGeoJSONApiView` | Yes    | No       | read-only                                                                                                                                        |
| `tools.py`            | `ToolDMP2JSON`                | Yes    | No       | temp file only                                                                                                                                   |
| `tools.py`            | `ToolDMPDoctor`               | Yes    | No       | wraps `mnemo_lib.correct_dmp_cmd`; returns 400 but captures because `correct_dmp_cmd` failures can be either corrupt user input or upstream bugs |
| `middleware.py`       | `DRFWrapResponseMiddleware`   | Yes    | No       | last-resort backstop (v1 only)                                                                                                                   |

### Savepoint rule for catching `IntegrityError`

Under PostgreSQL + `ATOMIC_REQUESTS`, a caught `IntegrityError` leaves the
transaction in an aborted state unless a savepoint was used.

**`get_or_create()` handles this automatically** — it creates its own savepoint
around the `create()` call. Do not add a redundant wrapper:

```python
# GOOD — get_or_create manages its own savepoint
try:
    obj, created = MyModel.objects.get_or_create(...)
except IntegrityError:
    pass

# BAD — redundant savepoint, unnecessary nesting
try:
    with transaction.atomic():
        obj, created = MyModel.objects.get_or_create(...)
except IntegrityError:
    pass
```

**A raw `create()` does NOT create a savepoint.** If you catch `IntegrityError`
around a plain `create()`, you MUST wrap it:

```python
# GOOD — savepoint protects the outer transaction
try:
    with transaction.atomic():
        MyModel.objects.create(...)
except IntegrityError:
    pass

# BAD — corrupts PostgreSQL transaction under ATOMIC_REQUESTS
try:
    MyModel.objects.create(...)
except IntegrityError:
    pass
```

---

## Running the tests

Use the already-running application container and run suites serially. Upload
integration tests use real GitLab repositories and must follow the shared pool
and audit requirements in [the GitLab testing contract](ci-gitlab-testing.md).

```bash
# Git retry tests (no DB, no network)
docker exec -w /app speleodb_local_django pytest speleodb/git_engine/tests/test_git_retry.py -v

# Upload error-handling tests (requires DB and real GitLab)
docker exec -w /app speleodb_local_django pytest speleodb/api/v2/tests/test_file_upload_error_handling.py -v

# All error-reporting tests (Sentry capture across all views)
docker exec -w /app speleodb_local_django pytest speleodb/api/v2/tests/test_error_reporting.py -v
```
