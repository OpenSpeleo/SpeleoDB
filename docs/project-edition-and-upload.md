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

`frontend_common/controllers/mutex-lock.js` attaches the existing
`forms/mutex_lock.js` helper. Acquisition uses the established POST and CSRF
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
