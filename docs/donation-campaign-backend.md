# Donation campaign backend

The fundraiser uses required `start_date` and `end_date`, inclusive in Django's
local date. There is no activation or live-send flag. Dashboard dismissal is
unique per campaign/account and survives rescheduling. Its modified_date records
the latest dismissal; the invitation returns after the configured
`reminder_days` elapsed days only while the campaign is active. The
authenticated `POST /api/v2/user/donation-campaigns/{campaign_id}/dismiss/`
operation returns 204 and creates or updates only the caller's dismissal,
renewing that interval without adding duplicate rows.

Django admin's Operations page links to the fundraiser. The grouped form edits
persisted content, story cards, and action labels. New campaigns have no
hardcoded content defaults; the owner supplies their copy and dates. Saving
never sends email. Staff with campaign view permission can inspect campaigns
read-only. Only active superusers may create/change campaigns, import/export,
send test messages, review the audience, and explicitly submit a production
send. Campaign deletion remains disabled. Email and modal previews are not
provided in admin.

The audience is registered account email addresses, including inactive accounts,
excluding existing SpeleoDB update opt-outs and empty addresses, deduplicated
case-insensitively. Provider suppressions may reject additional recipients. Test
addresses are entered explicitly and do not expand to account recipients. A
signed review captures a content/audience fingerprint and expires after one
hour. Changes require a fresh review. Each recipient gets a separate message.

The email task disables Celery’s automatic STARTED write because the shared
execution guard must claim the pending result row first. Worker-trace coverage
verifies real backend state transitions and email acceptance, not only eager
task execution. When the guard refuses a duplicate task, the campaign task
raises Celery `Ignore` so its worker cannot overwrite an existing running or
failed result with a spurious success.

Submission snapshots the approved content and records a permanent launch marker
and Celery group identifier. Celery task results and groups provide detailed
outcomes under the existing retention policy. Once detailed history expires, the
campaign still cannot be submitted again through the full-audience action. Tasks
recheck account/address/preferences before delivery. They use the existing
single-execution guard, audit log and after-commit publisher on
background_control, with a 90-second soft and 120-second hard execution limit.
Failures retain their original exception and traceback. There are no automatic
retries. Inspect provider records before attempting any separately authorized
recovery of uncertain publication or delivery.

The fixed HTML/plain-text templates receive `campaign` (a content mapping),
`site_url`, an absolute storage-resolved `photo_url`, and `unsubscribe_url`.
Database content is plain text, never executable template source. Tracking is
disabled. Provider acceptance does not establish inbox delivery or a donation.

Signed unsubscribe links are bound to the account and current email address. GET
displays confirmation without mutation; POST changes only
`email_on_speleodb_updates`. The signed token authorizes mailbox-provider
one-click POST without a session/CSRF token. Repeated POST is harmless. Test
emails link to an informational page that changes no preferences.

## Production email prerequisite

MailerSend's [email API](https://developers.mailersend.com/api/v1/email) exposes
`list_unsubscribe` for qualifying accounts. The
[Anymail MailerSend backend](https://anymail.dev/en/stable/esps/mailersend/)
passes `esp_extra` into that API. Campaign mail uses this dedicated field
instead of assuming arbitrary extra headers survive delivery. Local SMTP/locmem
mail uses standard List-Unsubscribe and List-Unsubscribe-Post headers. Anymail
is a production-only dependency and is not imported by campaign code.

Before sending production campaign mail, verify the existing account supports
custom unsubscribe behavior, provider policy permits this application-managed
flow, generated headers are present and signed correctly, and domain-wide
suppression will not affect account mail. No provider-account verification or
production send is performed by implementation tests. This prerequisite is an
operational requirement, not a stored boolean. Existing transactional email code
is unchanged.

## Admin import and export

The Donation campaigns list exposes django-import-export's Import and Export
workflows to active superusers. `DonationCampaignResource` in
`speleodb/campaigns/admin.py` matches rows by `id` (the campaign UUID): keep the
exported ID to update an existing campaign. An initial import can create the
campaign; imports cannot create a second campaign. The standard import preview
runs without persisting changes, followed by explicit confirmation.

Campaign copy, dates, donation settings and photo metadata are editable through
imports and undergo model validation. The `photo` column contains a storage
path, not image bytes; transfer the referenced file separately when moving
between storage environments. Launch time, approved send snapshot and audit
timestamps are exported for reference and ignored during import. Existing launch
history and account dismissals remain intact when updating a campaign. Importing
never sends campaign email; sending still uses the explicit review/send
workflow.

### Dismissal history in admin

Active superusers can inspect Campaign dismissals in Django admin, search by
user email or campaign headline, and filter by campaign. Records are ordered by
`modified_date`, the latest dismissal time; `creation_date` preserves the first
dismissal. The view uses related-object loading and permits no add or edit
operations. Only active superusers may delete dismissal records, including
through bulk deletion; deletion makes that user eligible for the invitation
again during the active campaign dates.

### Native task-result navigation

Campaign sends redirect to Django’s existing Task result admin: a single
recipient opens that result’s change/detail page, while multiple recipients open
the task-results list filtered to their database IDs. The submitted campaign’s
“View task results” link resolves its existing Celery group to the same native
pages. No campaign receipt endpoint, template, or custom delivery-status table
exists. Normal Celery retention can remove those task rows or the group; the
send page then omits the history link while remaining available, and the
permanent launch marker still prevents a full-audience resend.
