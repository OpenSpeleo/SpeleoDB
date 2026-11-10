# Project edition and revision submission

## Intent and ownership

Project pages let writers enable edition without leaving their current page. The
shared project banner renders **Enable Project Edition** as a button when the
project is unlocked and the viewer has write access. Clicking it immediately
POSTs to `api:v2:project-acquire`, then reloads the same page on success. There
is no trip through Lock Management and no success-dialog delay. The Lock
Management page keeps its own acquisition button, using the same behavior.

The existing API remains responsible for authorization and lock conflicts. A
stale banner cannot take another user's lock. Failed acquisition displays the
API error and re-enables the button for retry without navigating away.

## Frontend design

`pages/project/base.html` owns the banner, CSRF input, inert `mutex-lock`
controller context, and the single shared error modal. Keeping the controller
context beside the banner prevents child `inline_extra_js` overrides from
dropping the behavior. Child project pages must not include another error modal
with the same IDs. The Lock Management page supplies its own controller context
so each page initializes the mutex controller exactly once.

`frontend_common/controllers/mutex-lock.ts` attaches the existing
`forms/mutex_lock.ts` helper. Acquisition uses the established POST and CSRF
transport and immediately reloads after success. Its button stays disabled while
the request is pending, preventing repeated clicks. Unlock actions retain their
existing success feedback and reload delay. Error rendering continues to use the
shared escaping-aware AJAX error helper.

Revision uploads use native form semantics: the footer's **Upload Revision**
button is `type="submit"` with `form="file_upload_form"`. The `project-upload`
controller handles the form's `submit` event and prevents native navigation.
Enter in the revision title and clicking the button therefore run the same
validation and multipart PUT request. An invalid title or a failed upload keeps
the title and selected files available for correction or retry. Successful
uploads retain their existing revisions-page navigation.

This design avoids a separate keyboard handler, duplicated permission rules, and
an extra lock-management page request. It adds no polling, backend queries, or
additional upload requests.

## Verification

- Django banner tests render the project subpages, verify one acquisition
  controller/button and one error modal, and check the permission gates.
- Real API requests test CSRF protection, acquisition followed by rendering the
  same page, read-only rejection, and a lock taken after the banner was loaded.
- JavaScript tests use real jQuery and local HTTP fixture servers to verify
  transport, immediate acquisition reload, duplicate-click prevention, error
  rendering/retry, and upload title/file preservation. JSDOM's `requestSubmit()`
  exercises native form submission; it does not synthesize an Enter key's
  browser default action or perform actual navigation.
- Run JavaScript tests, focused Django tests, lint, and a clean Vite production
  build inside `speleodb_local_django`. The Django tests are database-only and
  require no GitLab repositories.

Project settings do not display or poll map-generation status. Background
generation and its status API remain independent of this page.

The typed project-upload controller retains its load barrier and multipart
submission flow. Its direct initialization tests cover file count, individual
and aggregate size limits, removal/reset, escaped filenames, repeated submit
wiring, delayed missing-context failure and map-status feedback. The wire
integration cases retain real local HTTP requests through jQuery.

## File API

All file processors use the same authenticated routes. Uploads require write
access and ownership of the edition lock; downloads require read access.

| Operation                | Method | Path                                                                |
| ------------------------ | ------ | ------------------------------------------------------------------- |
| Acquire edition lock     | POST   | `/api/v2/projects/{project_id}/acquire/`                            |
| Upload files             | PUT    | `/api/v2/projects/{project_id}/upload/{fileformat}/`                |
| Download latest file     | GET    | `/api/v2/projects/{project_id}/download/{fileformat}/`              |
| Download historical file | GET    | `/api/v2/projects/{project_id}/download/{fileformat}/{commit_sha}/` |
| Release edition lock     | POST   | `/api/v2/projects/{project_id}/release/`                            |

Use `ariane_tml`, `compass_zip`, or `stalagmight` for the corresponding file
format, or `auto` for upload detection. Uploads use multipart `artifact` and
`message` fields. Responses include the stored filenames, revision `hexsha`, and
source-save confirmation. Downloads return the selected revision's file as an
attachment. See [project capabilities](project-formats.md) for validation and
conversion support.

## Upload validation

`FileUploadView` owns server validation after the existing write-access and
edition-lock checks. It trims surrounding message whitespace and replaces each
newline group and surrounding whitespace with `. `, then checks the normalized
character count against `ProjectCommit.message`'s declared `max_length`. Unicode
characters count as characters, rather than encoded bytes. Raw input can exceed
the limit when trimming brings it within bounds, or fit the limit but exceed it
after newline replacement. The OpenAPI operation describes this normalization; a
raw-input `maxLength` would describe the wrong contract.

Three independent settings own artifact limits:

- `DJANGO_UPLOAD_TOTAL_FILES_LIMIT`: maximum number of uploaded artifacts.
- `DJANGO_GIT_UPLOAD_INDIVIDUAL_FILESIZE_MB_LIMIT`: maximum bytes per artifact,
  fixed at 5 MiB in `config/settings/base.py`.
- `DJANGO_GIT_COMMIT_TOTAL_FILESIZE_MB_LIMIT`: maximum combined artifact bytes,
  fixed at 7 MiB in `config/settings/base.py`.

These size settings apply only to `projects/{id}/upload/{fileformat}/` and its
web form. A commit's combined limit measures the artifacts in that upload, not
the size of the repository or resulting Git objects. General uploads, including
station resources, log attachments, GPX and GIS layers, continue to use
`DJANGO_UPLOAD_INDIVIDUAL_FILESIZE_MB_LIMIT`. The Git limits are common Django
settings, with no environment-variable overrides or Railway variables.
Application deployment activates them independently of the general-upload
allowance.

One MiB is `1024**2` bytes. Both byte limits are inclusive: the exact boundary
is accepted, and one byte over is rejected. Size errors report MiB and the
applicable setting. These limits measure the uploaded artifact bytes, excluding
multipart overhead, expanded archive contents and generated Compass metadata.
The web form already uses these settings for its client-side checks.

Message and artifact validation returns the existing HTTP 400 error envelope
before checkout synchronization, processing, commits or pushes. Early validation
prevents a message rejected by PostgreSQL from entering Git history, without
changing storage, permissions, history reconstruction or upload bookkeeping. It
adds only a string-length check and retains the existing file-size pass. There
is no migration, message truncation, history rewriting, skipped historical
commit or exception suppression. Existing affected histories require manual
repair; these checks prevent future invalid uploads and do not repair them.

The real upload integration suite covers normalized message boundaries, newline
expansion, trimming and multibyte Unicode; it checks Git and PostgreSQL
messages. Rejection cases compare local/remote HEAD, checkout contents, revision
rows and upload bookkeeping. A subsequent upload after a normal mutex handoff
checks that another writer can still use the project. Small real artifacts and
scoped settings exercise aggregate and individual inclusive byte boundaries,
exact committed bytes and independent file-count enforcement, using the
canonical GitLab pool and real request transactions. Run these cases, the upload
and project-history suites, schema checks and the complete backend suite inside
`speleodb-monorepo-django` from `/app`; review the GitLab audit and cleanup. SDK
snapshots import the reviewed backend schema bytes and regenerate operation
documentation without changing SDK signatures or package versions.

## Empty revision downloads

Every existing revision supports an Everything ZIP download, including the empty
initial revision. Empty revisions return a valid ZIP with no entries rather than
a server error. Nonempty archives retain their original paths and bytes. The
authenticated empty-download regression uses a real local Git repository; no
additional queries or conversion work are introduced.
