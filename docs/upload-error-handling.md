# API Error Handling & Observability

How all API views handle failures, why `ATOMIC_REQUESTS` requires
explicit rollback for caught exceptions, and how Sentry / admin-email
reporting works.

---

## Architecture overview

```
Client PUT /api/v1/projects/<id>/upload/<format>/
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

Every step above can fail. The view catches broad exception categories
and converts them to `ErrorResponse(status=500)`.

---

## Why `ATOMIC_REQUESTS` + caught exceptions = data integrity risk

Django's `ATOMIC_REQUESTS` wraps every view call in
`transaction.atomic()`. The `atomic()` context manager **only rolls back
if an exception propagates**. It does **not** inspect the HTTP status
code of the response.

If the view catches an internal exception and returns
`ErrorResponse(status=500)`, Django sees a successful view execution and
**commits** the transaction. Any ORM writes that happened before the
failure — `Format.objects.get_or_create()`, `ProjectCommit` inserts,
etc. — are persisted despite the logical failure.

### The fix: `transaction.set_rollback(True)`

`handle_exception()` in `file.py` calls `transaction.set_rollback(True)`
unconditionally — for **all** status codes, not just 5xx. If we reach
`handle_exception`, the upload did not succeed and no partial writes
should be committed. This tells Django's `ATOMIC_REQUESTS` to roll back
the entire transaction even though no exception propagated, eliminating
the need for manual ORM cleanup.

Git working-tree cleanup (`reset_and_remove_untracked()`) is still
performed because git operations are outside the DB transaction.

---

## Why admin email shows `Traceback: None`

Django 6.0's `BaseHandler.get_response()` calls `log_response()` for
all responses with `status_code >= 400`. This `log_response` call does
**not** pass `exc_info` because there is no active Python exception at
that point (the view already caught it). The `django.request` logger
fires at ERROR level → `AdminEmailHandler` → `ExceptionReporter` with
no traceback → `Traceback (most recent call last): None`.

---

## Why Sentry didn't capture these errors

Sentry's `DjangoIntegration` hooks into the `got_request_exception`
signal. That signal is only emitted by `response_for_exception()`,
which is only called from `convert_exception_to_response()` when an
**uncaught** exception propagates out of the view/middleware chain.

Additionally, the `django.request` logger in production had
`propagate: False`, so Sentry's `LoggingIntegration` never saw the
error-level log records either.

### The fix

1. `handle_exception()` now calls `logger.exception(...)` (full
   traceback to console/Railway logs) and
   `sentry_sdk.capture_exception(...)` (explicit Sentry event).
2. `DRFWrapResponseMiddleware` does the same in its `except Exception`
   block, catching anything that escapes the view layer.
3. The `django.request` logger now includes the `console` handler so
   error records appear in stdout.

---

## `construct_git_history_from_project` and savepoints

This method syncs `ProjectCommit` rows from git history.
`ProjectCommit.get_or_create_from_commit` uses Django's built-in
`objects.get_or_create()` which handles savepoints internally — if the
`create()` step hits an `IntegrityError`, `get_or_create` rolls back
to its own savepoint and retries with `get()`. The outer transaction
stays healthy.

**Important:** `get_or_create()` already handles savepoints. Do NOT
wrap it in an extra `transaction.atomic()` — that is redundant.
A raw `Model.objects.create()` does NOT create a savepoint, so if
you catch `IntegrityError` around a plain `create()`, you DO need
`transaction.atomic()` (see `station_tag.py` for an example).

---

## Git retry strategy for `commit_and_push_project`

When multiple gunicorn workers process overlapping requests for the
same project, `index.add()` or `index.commit()` can fail with
`GitCommandError` due to `index.lock` contention.

All three operations (`index.add`, `index.commit`, `git push`) use
`retry_with_backoff()` from `speleodb/utils/helpers.py` with
exponential backoff (base 0.1s, factor 2x, up to
`DJANGO_GIT_RETRY_ATTEMPTS` = 5 attempts).

```python
from speleodb.utils.helpers import retry_with_backoff

retry_with_backoff(
    fn,
    *args,
    retries=5,
    exc_types=(GitCommandError,),
    base_delay=0.1,      # first retry after 0.1s
    backoff_factor=2.0,   # then 0.2s, 0.4s, 0.8s ...
    **kwargs,
)
```

Git's own lock files are **never** manually deleted. The lock belongs to
the git process that created it; removing it from under a live process
would corrupt the index. Retrying with a sleep lets the competing
process finish and release the lock naturally.

---

## Three-step protocol for all API views

Every `except` block in any API view that returns an `ErrorResponse`
with status >= 500 **must** follow this protocol:

1. **`logger.exception(...)`** — preserves the full traceback in
   console/Railway logs.
2. **`sentry_sdk.capture_exception(exc)`** — creates a Sentry event
   with traceback, tags, and request context.
3. **`transaction.set_rollback(True)`** — required **only** when ORM
   writes (`create`, `save`, `get_or_create`, etc.) happen inside the
   `try` block before the error. Tells Django's `ATOMIC_REQUESTS` to
   roll back the entire transaction.

Views that return 4xx for user-input errors (e.g. `BadZipFile`,
`ValidationError`, `FileNotFoundError`) do **not** need Sentry capture
or rollback — those are expected outcomes, not internal failures.

### Files covered by this protocol

| File | View | Sentry | Rollback | Notes |
|------|------|--------|----------|-------|
| `file.py` | `FileUploadView` | Yes | Yes | via `handle_exception()` |
| `file.py` | `FileDownloadView` | Yes | No | read-only, no DB writes |
| `gpx_import.py` | `GPXImportView` | Yes | Yes | `Landmark` + `GPSTrack` writes |
| `kml_kmz_import.py` | `KML_KMZ_ImportView` | Yes | Yes | `Landmark` writes |
| `project_explorer.py` | `ProjectGitExplorerApiView` | Yes | No | read-only |
| `project.py` | `ProjectSpecificApiView` | Yes | No | read-only |
| `gis_view.py` | `GISViewDataApiView` | Yes | No | read-only |
| `gis_view.py` | `PublicGISViewGeoJSONApiView` | Yes | No | read-only |
| `tools.py` | `ToolDMP2JSON` | Yes | No | temp file only |
| `middleware.py` | `DRFWrapResponseMiddleware` | Yes | No | last-resort backstop |

### Savepoint rule for catching `IntegrityError`

Under PostgreSQL + `ATOMIC_REQUESTS`, a caught `IntegrityError` leaves
the transaction in an aborted state unless a savepoint was used.

**`get_or_create()` handles this automatically** — it creates its own
savepoint around the `create()` call. Do not add a redundant wrapper:

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

**A raw `create()` does NOT create a savepoint.** If you catch
`IntegrityError` around a plain `create()`, you MUST wrap it:

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

```bash
# Git retry tests (no DB, no network)
pytest speleodb/git_engine/tests/test_git_retry.py -v

# Upload error-handling tests (requires DB)
pytest speleodb/api/v1/tests/test_file_upload_error_handling.py -v

# All error-reporting tests (Sentry capture across all views)
pytest speleodb/api/v1/tests/test_error_reporting.py -v
```
