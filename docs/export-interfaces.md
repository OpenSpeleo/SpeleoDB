# Export account page, API, and administration

## Intent and ownership

The Account Settings **Export / Backup** page gives an account owner a durable
place to request archives and return to completed downloads. Email delivery and
the Kanchi dashboard are independent: an email or monitoring outage must not
hide a valid archive. The application job service owns permission decisions,
request deduplication, retries, and signing. Views do not enqueue arbitrary tasks.

The feature exports the five documented dataset categories. It is not an account
restoration format. Project access must be Read Only or higher; Web Viewer
access does not qualify. Generation failures affecting individual sources appear
as explicit omissions in the page and archive manifest.
Project folders contain readable current files and `.git/` history; zero-commit
projects contain only the empty `PROJECT IS EMPTY` marker. Downloads are named
`speleodb-export-YYYY-MM-DDTHH-MM-SSZ-<job-uuid>.zip`, with a UTC timestamp.

## Public interfaces

- `private:user_exports` renders `/private/exports/` and requires login.
- `GET /api/v2/user/exports/` returns owner-only active/nonexpired history, 20
  records per page. Expired/deleted artifacts are filtered before pagination;
  pending jobs and failed jobs without expired artifacts remain visible.
- `POST /api/v2/user/exports/` returns `202` for a durable accepted job, including
  the existing job when one is already active. Clients cannot select a requester.
- `GET /api/v2/user/exports/<uuid>/` returns status, progress, safe summary,
  notification state, artifact metadata, expiration, and an application download
  route. It never returns raw storage keys or notification exception details.
- `POST /api/v2/user/exports/<uuid>/retry/` starts a fresh attempt for a failed
  job. A `409` response reports the active job identifier when applicable.
- `GET /api/v2/user/exports/<uuid>/download/` checks ownership or superuser
  access and redirects to a short-lived signed URL. Unready exports return `409`;
  expired exports return `410`. Redirects use `private, no-store` caching.

Account history and details remain owner-only for staff. An active superuser can
use the protected download route for another user's archive. Export creation and
retry are available to every authenticated active account through the normal
account and resource permissions. No separate enablement setting is required.

## Browser behavior and safety

The `user-exports` controller loads through the Vite registry with inert JSON
configuration. Active cards say `An email will be sent when ready to download.`
Technical stage/item counts remain available through the API and admin. The page
refreshes active jobs every five seconds and pauses when hidden. Terminal jobs
do not require continuous polling; an expiry timer removes unavailable cards
when their download deadline arrives.
Requests are asynchronous; duplicate clicks are guarded in the browser and
deduplicated by the durable job service. History is paginated to bound response
size and rendering work. Artifact joins avoid per-row database queries.

Email links include `?export=<uuid>`. The page fetches and focuses that specific
job independently of the current history page, including older jobs retried by
an administrator. The result merges into the same export list by job UUID:
an export already on the page updates its existing card, and an older export
outside the page joins the list. Each export appears once, with one set of
status and download/retry controls. Expired cards are excluded after merging,
including old email links, while active retries remain visible. Detail/download
routes retain their ownership checks and expired downloads still return `410`.
When the two requests observe different
states, the newer update wins. Its active state also keeps progress polling
running.

History refreshes preserve keyboard focus on a surviving export card or its
download/retry control without scrolling. They do not move focus from elsewhere
on the page; explicit email-link focus still takes precedence.

API strings are rendered with `textContent`. Download and retry routes are
constructed from validated UUIDs; API-provided URLs cannot redirect the browser
to an arbitrary site. Mutations use the page's CSRF token. A partial export
always displays a prominent warning and its omissions. Notification failure does
not suppress a ready download.

## Administration

Active staff can inspect jobs, progress, attempt history, attachment metadata,
and sanitized errors. Fields are read-only and deletion is disabled. Audited
actions invoke application services to retry failed generation, retry failed
notifications, or generate replacements for partial archives. Only superusers
see attachment download links for other users.

`KANCHI_URL` optionally provides a link to the dashboard root. No undocumented
Kanchi deep-link format is assumed, and the dashboard is not the source of truth
for application permissions or export retries.

Celery task and group result tables retain their upstream diagnostic views and
filters, but their admin pages are read-only for staff and superusers. No manual
add, status modification, or deletion is permitted through those pages; this
prevents the repository's broad staff permissions from changing execution
records. Recovery actions belong to the application job dashboard.

## Verification

API tests exercise real database rows and authenticated requests for ownership,
pagination, deduplication, retry conflicts, expiration, signing, and admin
actions. Django test-client rendering verifies the actual page and both
responsive navigation links. JavaScript tests directly exercise the production
renderer for progress, partial results, escaping, download routes, and retry
availability without replacing dependencies. The overall export integration
suite must also verify actual object creation/download, real worker execution,
notification delivery, and storage deletion.

### Previous implementation verification

Container checks passed: 51 API/admin/private URL tests, all 986 JavaScript
tests (including nine export renderer tests), JavaScript lint, scoped Python
Ruff and mypy, template lint, and a clean production Vite build. The development
watcher was stopped before that build. An authenticated request to the running
Django server returned the export page and history API successfully, and the
served export controller, app script, and stylesheet matched the production
manifest files byte for byte. The temporary local verification account and
session were removed afterward. Browser automation was unavailable; these
checks do not constitute a visual browser review.

The single-list correction passed all 989 JavaScript tests (including 12 export
renderer tests), 51 API/admin/private URL tests, and a clean production build
inside Docker. Coverage includes linked-job merging, deduplication, freshness,
focus, and retry availability. Each export renders once in the same list.
An authenticated HTTP request verified one export list and no selected/recent
sections. The served controller, app script, and stylesheet matched the clean
production manifest byte for byte. Visual browser inspection remains unverified.

The final email-copy/expiry correction passed all 1,003 JavaScript tests and 54
focused API/admin/private URL/reloader checks inside Docker, plus all pre-commit
hooks and a clean production build. Coverage includes expiration before API
pagination, linked expired jobs, open-tab expiry timers, active retries with old
artifacts, and a bounded return to page one when expiry invalidates a later page.
The running server served the updated controller/app/CSS exactly as recorded in
manifest `e5e95988de65790f32684f0d4a1878b90bd390f37dcff607e20312f1c21cfd0a`.
