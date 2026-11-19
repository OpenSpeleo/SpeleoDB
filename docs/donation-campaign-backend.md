# Donation campaign backend

The fundraiser uses required `start_date` and `end_date`, inclusive in Django's
local date. There is no activation or live-send flag. Dashboard dismissal is
unique per campaign/account and survives rescheduling. Its modified_date records
the latest dismissal; the invitation returns after the configured
`reminder_days` elapsed days only while the campaign is active. The
authenticated `POST /api/v2/user/donation-campaigns/{campaign_id}/dismiss/`
operation returns 204 and creates or updates only the caller's dismissal,
renewing that interval without adding duplicate rows.

Django admin's Operations page links to the fundraiser. The form edits the
action URL, integer USD goal, main email subject, reminder email subject,
required main email and modal selections, optional reminder selection, and
operational dates/dismissal timing. Copy, images, labels, and story cards live
in HTML. Main and reminder subjects, template selectors, and send actions are
grouped in separate admin fieldsets. `email_reminder_subject` is optional until
a reminder template is selected; model validation and the send boundary reject
an empty reminder subject; either both reminder fields must be configured or
both cleared. `snapshot()` freezes the selected type's subject under `subject`,
so the delivery header and HTML title agree for real sends and previews. The
campaign model stores separate main/reminder subjects and successful email
batches. `modal_template` stores a UUID4 HTML filename selected from
`speleodb/templates/campaigns/modal_templates/`; email choices come only from
`speleodb/templates/campaigns/email_templates/`. Both use the same filename
discovery rule with separate directories and choice callables. The dashboard
includes the validated `modal_template_name` in its existing dialog shell, using
the shared navigation and dismissal controller. New campaigns initially select
the included modal design. Modal selection adds no database query; Django's
template loader renders the selected file. `test_modal_templates.py` covers
directory separation, invalid or removed selections, selected content, and
escaped campaign values; dashboard presentation tests retain the original design
and dismissal coverage. Normal saving never sends email. All five Campaigns
admin models require active superuser access for navigation and reading as well
as permitted writes. Direct or group model grants never let staff view campaign
records, history, lookup popups, or recipient information. Only active
superusers may create/change campaigns, import/export, send test messages,
review the audience, and explicitly submit a production send. Campaign deletion
is restricted to active superusers, including bulk deletion. Django's native
confirmation and cascade remove the campaign's dismissals and email history.
`DonationCampaignAdmin.get_deleted_objects()` permits that history cascade while
keeping standalone email-history deletion disabled. This uses the existing
foreign keys and admin permission hooks without additional queries or persistent
state. Endpoint regressions in `test_admin_delete.py` cover individual and bulk
deletion, cascades, and denial for staff even with model permissions.

Both email template selectors expose **Save & send preview**. The typed admin
controller posts the current form with `_save_preview` identifying the selected
email type. Native Django admin validation, saving, audit logging, and its
transaction remain in charge. Successful response hooks schedule the existing
explicit-recipient test operation using only `request.user.email`; arbitrary
recipient input is ignored. The JSON response provides inline feedback, the
saved change URL, and the native task-results URL. The controller opens a native
success dialog after a successful response; validation and request failures
remain visible beside the selector. Validation failures return JSON without
saving or queuing mail. Preview requests require active superuser access and
CSRF. Test and preview messages never create real-send history. All delivery
modes use the same content snapshot and renderer; test status stays in task
metadata and never alters subjects, bodies, or links. Delivered-content parity
for main and reminder messages is covered by the campaign history tests. Modal
previews are not provided in admin.

The admin exposes separate **Send Email Campaign** and **Send Reminder Email
Campaign** buttons. The main action uses `email_main_template`; the reminder
action uses `reminder_email_template` and is disabled until that selection is
saved. Both actions require active superuser access and preserve the explicit
test/review/confirm workflow. Signed reviews bind the campaign and selected
email type, so a main-email review cannot authorize reminder delivery.

The audience is registered account email addresses, including inactive accounts,
excluding existing SpeleoDB update opt-outs, empty addresses, and the campaign’s
case-insensitive `donors` list, deduplicated case-insensitively. Provider
suppressions may reject additional recipients. Test addresses are entered
explicitly and do not expand to account recipients. A signed review captures a
content/audience fingerprint and expires after one hour. Changes require a fresh
review. Each recipient gets a separate message.

Both real-send forms offer an optional `project_users_only` flag, off by
default. When selected, eligibility requires at least one active direct project
permission or an active team permission through an active membership, on an
active project of any type. Web-viewer access counts. Filtering happens before
case-insensitive email deduplication and preserves update opt-outs. The flag and
resulting audience participate in the review digest and are captured in the send
snapshot. Workers recheck the same eligibility at delivery. Explicit test
recipients remain independent of this filter. The option is per send and adds no
campaign model field, migration, or background schedule.

The email task disables Celery’s automatic STARTED write because the shared
execution guard must claim the pending result row first. Worker-trace coverage
verifies real backend state transitions and email acceptance, not only eager
task execution. When the guard refuses a duplicate task, the campaign task
raises Celery `Ignore` so its worker cannot overwrite an existing running or
failed result with a spurious success.

Each real-send review receives a unique signed `send_id`, bound to the campaign,
email type, and content/audience digest. A new review permits another send;
replaying the same confirmation is rejected through the existing submission
audit. Each newly confirmed review creates its own main or reminder batch. Tasks
retain frozen content and recheck account/address/preferences, donor exclusions,
and any selected project-access requirement before delivery.

Failed email tasks expose the immediate **RETRY** action in task administration.
A retry uses the same task ID and TaskResult row, but reloads the same
campaign's current selected template, subject and content. It retains the
main/reminder choice and project-user filter. Account recipients are resolved by
their saved user ID and use their current email; direct/test recipients retain
the saved email. New receipts retain user ID and site URL independently of the
snapshot. Older account receipts prefer the user ID in intact stored arguments,
so an email change or reassignment cannot retarget the task. Only receipts with
truncated arguments resolve the stored recipient email once; the recovered user
ID is then retained for later retries. A missing campaign or linked user leaves
the failed result unchanged and reports why it cannot retry. The rebuilt
snapshot is frozen for that new execution, and workers still recheck opt-outs,
donor exclusions and account/project eligibility. The existing batch history
remains the original send's summary; the task's updated payload records the
exact content used for its retry.

This adds one campaign read and, for linked recipients, one user read per retry,
plus the selected template file read; it creates no new model or schedule.
Regressions exercise actual email-header rejection followed by successful
same-task delivery after campaign edits, user-email changes, and explicit-email
or older-receipt resolution, including reminder subjects. No retry results or
email backend behavior are mocked.

`DonationCampaignEmail` stores successful delivery batches, including the type,
subject, template, and successfully accepted recipient addresses. Recipient
workers lock the shared batch row inside the existing outcome transaction before
appending an address. This keeps accepted recipients intact across worker
replicas. Its UUID is the Celery group identifier, so the readonly admin detail
links to native task results while they remain available. Failures and skips do
not become successful recipients; an entirely unsuccessful batch creates no
success record. The campaign form includes readonly history, and standalone
history is restricted to active superusers with creation, editing, and deletion
disabled. History remains available after detailed Celery results expire.
Preview/test sends bypass the registered audience and never create real-send
history. They use the existing single-execution guard, audit log and
after-commit publisher on background_control, with a 90-second soft and
120-second hard execution limit. Failures retain their original exception and
traceback. There are no automatic retries. Inspect provider records before
attempting any separately authorized recovery of uncertain publication or
delivery. If a provider accepts a message but recording its successful delivery
fails, the task fails and requires manual investigation against provider
records. It is never retried automatically.

Email templates receive `campaign` (selected subject, action URL, integer goal,
and formatted goal), `site_url`, `email_assets_url`, and `unsubscribe_url`. The
staticfiles prefix `campaigns/email_templates/assets/` exposes the colocated
`email_templates/assets/` directory, including the campaign photo. The asset
base URL is absolute and uses Django's configured static storage, including the
existing S3 static storage in production. Normal deployment `collectstatic`
publishes these colocated assets with the other static files. Database content
remains escaped data. Only reviewed, application-owned files provide executable
template source. The shared `VALIDATE_TEMPLATES_IGNORES` setting excludes JPEG
and PNG images from `validate_templates`, preserving its temporary-file
exclusions so CI compiles template source without decoding binary assets. This
does not change template rendering or static-file discovery and adds no request
overhead. Command-level regression tests in
`speleodb/common/tests/test_template_validation.py` cover colocated images and
ensure malformed HTML and plain-text templates still fail validation. Templates
should contain their own full markup, rather than include mutable source from
other files. The review digest includes selected file contents, and submission
snapshots those contents for workers so edits cannot change queued mail. Only
the selected email type's source is read; a removed optional reminder file
cannot block main email snapshotting. Plain text is derived from the rendered
HTML with explicit action and unsubscribe URLs. Tracking is disabled. Provider
acceptance does not establish inbox delivery or a donation.

Photo rendering tests explicitly exercise both filesystem static storage and S3
storage with a bucket path. Local debug startup selects filesystem storage,
while CI selects S3; the tests resolve asset paths through Django's configured
static storage instead of assuming a `/static/` URL prefix. Both configurations
must discover and decode the bundled email and modal images through staticfiles,
which also owns their publication through `collectstatic`.

A missing reminder template is rejected before review or task creation,
including direct requests to the reminder send page. Reminder delivery shares
the main email's audience, worker, unsubscribe handling, and execution guard; it
adds no schedule or automatic sending. `reminder_days` continues to control
dashboard invitation eligibility only.

Campaign email's `unsubscribe_url` resolves to the existing authenticated
`private:user_preferences` route on the sending site's origin, for both real and
test mail. Locally it points to `http://localhost:8000/private/preferences/`;
production uses its own domain. GET only displays the normal preferences form
(or sign-in first) and does not mutate preferences. Users update their own
settings through the existing form. There are no campaign signed-unsubscribe or
test-unsubscribe endpoints, automatic unsubscribe POSTs, or mailbox-bound
tokens.

Campaign mail omits `List-Unsubscribe` and `List-Unsubscribe-Post` headers and
MailerSend's `list_unsubscribe` field because those would advertise an automatic
unsubscribe action that this workflow does not provide. MailerSend tracking
settings remain disabled through the existing Anymail backend. Existing
transactional email delivery is unchanged.

## Admin import and export

The Donation campaigns list exposes django-import-export's Import and Export
workflows to active superusers. `DonationCampaignResource` in
`speleodb/campaigns/admin.py` matches rows by `id` (the campaign UUID): keep the
exported ID to update an existing campaign. An initial import can create the
campaign; imports cannot create a second campaign. The standard import preview
runs without persisting changes, followed by explicit confirmation.

Campaign dates, donor exclusions, donation settings and email template
selections are editable through imports and undergo model validation. Missing
template files and paths outside the UUID-named file choices are rejected.
Templates and assets ship with the application; they are not imported as
database content. Campaign email history belongs to separate readonly records
and cannot be rewritten or deleted by a campaign import. Audit timestamps remain
readonly.

### Dismissal history in admin

Active superusers can inspect Campaign dismissals in Django admin, search by
user email or campaign subject, and filter by campaign. Records are ordered by
`modified_date`, the latest dismissal time; `creation_date` preserves the first
dismissal. The view uses related-object loading and permits no add or edit
operations. Only active superusers may delete dismissal records, including
through bulk deletion; deletion makes that user eligible for the invitation
again during the active campaign dates.

### Native task-result navigation

Campaign sends redirect to Django’s existing Task result admin: a single
recipient opens that result’s change/detail page, while multiple recipients open
the task-results list filtered to their database IDs. Each email-history detail
links its UUID to the matching Celery group and the same native task pages.
Normal Celery retention may remove those task rows or the group, in which case
the permanent readonly delivery record remains but its task link is replaced
with an unavailable notice. A fresh review can still submit a new batch. There
is no custom campaign receipt endpoint or status page.

## Admin privacy boundary

Campaign management, acknowledgments, email history, dismissals, PDF downloads,
and delivery actions are superuser-only in Django admin. Native model permission
hooks enforce this on direct requests as well as menus. Existing read-only
history and issued-letter restrictions still apply to superusers. Public
fundraising presentation, the thank-you page, and a user's own invitation
dismissal retain their separate product permissions.

Staff task-result queries exclude the `speleodb.campaigns.` namespace. Campaign
groups are excluded using the group IDs in permanent campaign submission audit
entries, including test sends and groups whose tasks have expired. The group
filter is one database subquery, excludes missing/null group IDs, and preserves
unrelated export and technical results. No model fields or migrations support
this restriction.

`LogEntry.for_admin_user()` applies the same campaign audit visibility policy to
the full audit admin and the dashboard's recent actions. A former administrator
who becomes staff cannot see old campaign snapshots through those surfaces.
Other permitted audit history remains available.

`test_admin_permissions.py` verifies all five registered models with no grants,
direct grants and group grants; custom send/preview/PDF/import routes; publisher
role checks; superuser access; demotion; and unrelated task/group/audit
preservation. Existing transfer/deletion tests enforce the same restriction.
