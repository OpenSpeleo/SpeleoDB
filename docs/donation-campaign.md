# Donation campaigns

Donation campaigns combine a dashboard invitation with an email appeal. Users
follow the campaign's donation link to PayPal, which handles payments and
reports donations. SpeleoDB displays the fundraising goal but does not track
completed donations or calculate an amount raised.

## Managing the campaign

Open **Background operations → Operations → Manage fundraiser** in Django admin.
Active superusers can edit campaign content, import or export it, and send
emails. Staff with view permission have read-only access. The admin permits one
campaign record. Only active superusers may delete it, individually or through
the bulk delete action. Confirmation lists the related dismissal and email
history records, which are deleted with the campaign.

The **Main email** and **Reminder email** sections each group their subject,
template selector, and corresponding send action. Both selectors retain the
adjacent **Save & send preview** button. Campaign goal/link, scheduling, and
submission history remain in their own sections.

Saving a campaign updates its dashboard presentation. Email sending is a
separate action; saving or changing dates does not send messages.

Each email-template selector has a **Save & send preview** button. It validates
and saves the entire form, then requests that template's preview for the
signed-in administrator's account email. A success modal confirms the request
and offers a delivery-status link without reloading the page. Select a reminder
template before using its preview button. Validation errors preserve the form's
edits for correction. Previews use the existing background test-email operation,
bypass recipient preferences for that explicit address, and never create
real-send history. Normal **Save** continues to save without requesting an
email.

## Scheduling dashboard visibility

`start_date` and `end_date` define when the campaign appears on the dashboard.
Both dates are inclusive, using the application's local timezone. The end date
must be on or after the start date.

- A future start date keeps the campaign hidden until that date.
- During the date range, the dashboard shows the campaign card and eligible
  users receive the invitation.
- After the end date, both the card and invitation disappear.

Campaign dates do not restrict administrator-initiated email sends.

## Invitation and reminders

The invitation presents the campaign image, summary, fundraising goal, donation
action, and recipient notice. The story button opens a second view in the same
modal, with illustrated highlights and the campaign's ownership promise. Back
returns to the donation view. Story navigation does not dismiss the campaign.

Closing the invitation, choosing the reminder action, or following its donation
link records a dismissal for that account. Escape and clicking outside the modal
have the same effect. The invitation becomes eligible to appear again on a
dashboard visit once `reminder_days` have elapsed, provided the campaign is
still within its dates. The default interval is seven days.

The dashboard card remains available after dismissal. Reopening it does not
change the reminder date; closing it again or donating from the card starts a
new reminder interval. Dismissals persist across devices and survive campaign
edits or rescheduling. If saving a dismissal fails, the modal closes and the
page offers a retry action.

Automatic opening is suppressed while another dialog is open or the user is
already focused on a dashboard control. Donation links open in a new tab.

## Campaign content

`DonationCampaign` stores only the campaign-specific content and operational
state. Campaign presentation belongs to readable HTML files, so changing the
appeal's layout or wording does not require editing dozens of database fields.

| Content                | Field and behavior                                                                                   |
| ---------------------- | ---------------------------------------------------------------------------------------------------- |
| Action link            | `donation_url` is the campaign donation destination.                                                 |
| Financial goal         | `goal_usd` is an integer, displayed as a US-dollar amount.                                           |
| Modal                  | `modal_template` selects a file from the separate modal template folder.                             |
| Main email             | `email_main_template` selects a file from the email template folder.                                 |
| Reminder email         | `reminder_email_template` optionally selects another email template.                                 |
| Main email subject     | `email_main_subject` is the main email inbox subject line.                                           |
| Reminder email subject | `email_reminder_subject` is the reminder inbox subject line, required when its template is selected. |

Dates and `reminder_days` remain separate operational fields. Successful sends
are recorded in readonly email-history rows. The reminder button reflects the
configured dismissal interval.

Email templates live in `speleodb/templates/campaigns/email_templates/`, with
UUID4 filenames ending in `.html`. The selection lists are computed from the
files present in that directory. Add a template file to make it selectable; its
copy, preheader, image, attribution, and footer are maintained together in HTML.
Dynamic values remain escaped by Django. The mail system supplies the
authenticated preferences URL for the unsubscribe link.

The approved **Bring the light** design remains the main email template. It uses
deep navy, teal type, an expedition photograph, and an amber donation panel.
Text uses inline justified alignment for email-client compatibility. Both
template dropdowns can select this file; the reminder selection remains
optional.

The optional **The next discovery starts with you** reminder shares the credited
photograph and centered gold serif signature. It opens with an amber appeal and
donation goal, then resolves into the expedition photograph and shared
signature. A centered donation action follows the paragraph about maintaining
SpeleoDB and keeping survey work under its owners' control.

Each template identifies its direction in an opening HTML comment. Select its
UUID filename in **Reminder email template**, then use **Save & send preview**
to preview the selected design. Adding a file does not switch the saved
selection or modify the main design. Main and reminder subjects are separately
editable. The selected subject appears in the email's HTML title and inbox
header; headings and opening phrases belong to the HTML templates.

Reminder copy describes the campaign as coming to a close and highlights U.S.
tax-deductible giving near the donation action, qualified by the existing "to
the extent permitted by U.S. law" wording. It does not invent an expiry date,
countdown, amount raised, or matching offer. Send it when the campaign is
nearing its actual close; sending remains an explicit administrator action.

Text alignment is inherited from the main presentation table. Spacing between
text blocks uses table-cell padding instead of paragraph margins for more
consistent email-client rendering. Mailpit's HTML compatibility report helps
check these choices; it does not measure spam placement or Promotions sorting.

The template uses inline styles, system fonts, and optional mobile media
queries. Its optimized expedition photograph retains the photographer's credit;
the modal keeps its original photograph. Assets resolve through Django static
storage, including S3 in production. Plain-text mail is derived from the email
body, excluding head metadata and responsive CSS.

The dashboard card and dialog shell use
`frontend_private/templates/snippets/donation_campaign.html`. Each campaign's
required **Modal template** selector chooses a UUID4-named HTML file from
`speleodb/templates/campaigns/modal_templates/`. Email selectors discover only
`email_templates/`; modal selectors discover only `modal_templates/`. Adding a
UUID4 HTML file to the appropriate directory makes it selectable. Missing files
and paths outside that directory are rejected.

The selected modal owns its photo, copy, buttons, recipient notice, and story
cards. It receives `donation_campaign`, including the formatted goal, donation
link, and dismissal interval. Retain the existing dialog heading and
`data-campaign-*` hooks when authoring variants so navigation and dismissal work
with the shared controller and stylesheet. New campaigns initially select the
included design and can choose another. Email and modal markup remain separate
because email clients require different layout and inline styles. Email preview
buttons continue to send email previews only. The tax-status wording is
maintained as campaign copy; SpeleoDB does not verify an organization's tax
status.

### Donor thank-you page

`/campaigns/thank-you/` is a public, fully static celebration of SpeleoDB's
supporters. It works without a campaign record, account, or active campaign. Its
copy and illustrated cave scene belong to the template and stylesheet; there is
no campaign lookup, model field, or admin configuration.

The page combines a thank-you message, three community impact highlights, and
links to the dashboard and the people behind SpeleoDB. **Back to exploring**
opens the dashboard, using its normal sign-in flow for visitors without a
session. An optional cave high-five animates the illustration and announces a
playful reply. The message and navigation remain usable without JavaScript;
reduced-motion preferences suppress movement. Desktop uses a two-column
composition; mobile stacks the introduction and illustration with full-width
primary navigation and compact impact rows.

Use the absolute URL on your SpeleoDB domain as the donation provider's return
URL. The page does not verify a payment or record donations, dismissals, or
email sends; payment-looking query parameters do not change its response.
Configuring the provider's return URL is a separate operation.

### Campaign photo

The campaign photograph lives in
`speleodb/templates/campaigns/email_templates/assets/`, beside the HTML files.
Django serves this folder as static assets under the
`campaigns/email_templates/assets/` prefix. The modal and email templates
contain its alternative text and photographer credit. To change the image, add
an asset and update the relevant HTML templates; there is no campaign image
upload field.

## Sending email

The campaign admin offers two buttons: **Send Email Campaign** uses the main
email template, and **Send Reminder Email Campaign** uses the reminder template.
Select and save a reminder template and subject to enable its button. Each opens
its own send page, showing the selected email type and providing these
workflows:

1. **Send test email** accepts explicit addresses separated by commas or
   newlines. Only those addresses receive the test message. The subject is the
   selected email type's subject exactly, with no test prefix.
2. **Review send** prepares the registered-account audience and captures the
   current campaign content. Addresses are deduplicated, empty addresses are
   excluded, and SpeleoDB-update opt-outs are respected. Inactive accounts are
   included. Enable **Only users with access to at least one project** to omit
   accounts with no current project access. This option is available for both
   normal and reminder sends and is off by default.
3. **Send to accounts** confirms that review and queues delivery. The review
   expires after one hour; campaign data, template source, or audience changes
   require a fresh review. The audience option is bound to the review, so
   changing it requires reviewing again. Queued messages retain the approved
   template source.

Each recipient receives a separate HTML email with a plain-text alternative.
Delivery runs asynchronously, with results available in Django's Task results
admin. A single-recipient send opens its task detail; multiple recipients open a
filtered task list. Main and reminder emails can be sent again after a fresh
review. Replaying an already-submitted confirmation cannot create another batch.
Successful real-send recipients are recorded in email history separately for
each batch. Test and preview messages do not create real-send history.

Reminder email is an explicit administrator action. Choosing its template or
setting `reminder_days` does not schedule email; that interval only governs the
dashboard invitation. Both email types use the current registered-account
audience and update opt-outs.

The project-access option includes active direct permissions and access through
active team membership and team permissions, across every project type. Even
web-viewer access qualifies. Revoked permissions, inactive team memberships, and
inactive projects do not qualify. Existing update opt-outs and address
deduplication still apply. Delivery rechecks access before sending, so an
account that loses its last project after submission is skipped. Explicit test
addresses are unaffected by this option.

Every email's unsubscribe link opens `/private/preferences/` on the SpeleoDB
site that sent the message. Locally this is
`http://localhost:8000/private/preferences/`; production uses its own domain.
Opening the link changes nothing. Users sign in if needed and change their
update preference themselves in the form. Campaign mail does not offer automatic
one-click unsubscribe actions. Open and click tracking are disabled. Provider
acceptance of a message does not confirm inbox delivery or a donation.

## Import, export, and dismissal history

Campaign import/export is available to active superusers. Retaining the exported
campaign ID updates the existing record. Imports preserve email history and user
dismissals and do not send email. Template files and static images are shipped
with the application, rather than transferred through campaign exports.

**Campaign dismissals** lists each account's first and latest dismissal times.
Active superusers can inspect and delete these records, but cannot add or edit
them. Deleting a dismissal makes the account eligible for the invitation again
while the campaign is active.

See [backend operations](donation-campaign-backend.md) for delivery execution,
task-result retention, preference navigation, and email-provider behavior.

## Implementation and verification

Campaign content and delivery state belong to `speleodb/campaigns/`; the
selected modal templates own modal presentation and the existing campaign
controller owns navigation and dismissal. Template discovery reads the small
local template directory when choices are requested; it adds no database tables
or background work. Delivery snapshots capture email source before queueing, so
recipients do not trigger a fresh template-file read.

Campaign tests cover selected-file validation, reviewed source preservation,
delivery permissions, independent main/reminder submission history, review-type
binding, missing reminder templates, project-access audience filtering, and
preference-link behavior. Dashboard presentation tests cover visibility dates,
persistent dismissal, escaped dynamic values, and the preserved modal story. The
frontend controller tests cover modal navigation and failure recovery.

### Repeated sends, donor exclusions, and email history

Configure both reminder subject and template together, or clear both.

The campaign’s editable `donors` list accepts one email per line in admin; leave
it blank for no exclusions. Addresses are validated and deduplicated. Imports
and exports retain the JSON list format. This list contains addresses to exclude
from registered-account sends. Matching ignores case and is checked again during
delivery. Explicit preview/test addresses remain independent of audience
filters.

Each confirmed review submits one new batch. To send again, create a fresh
review; reusing an already-submitted confirmation is rejected. Successful email
batches appear in readonly history on the campaign form and the sending page.
Each record contains the actual subject, template, and accepted recipient
addresses, with a link to task results while those details remain available.
Only active superusers can view email history; it cannot be added, edited, or
deleted independently in admin. Deleting the campaign also deletes its email
history.
