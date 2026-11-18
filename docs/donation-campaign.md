# Donation campaigns

Donation campaigns combine a dashboard invitation with an email appeal. Users
follow the campaign's donation link to PayPal, which handles payments and
reports donations. SpeleoDB displays the fundraising goal but does not track
completed donations or calculate an amount raised.

## Managing the campaign

Open **Background operations → Operations → Manage fundraiser** in Django admin.
Active superusers can edit campaign content, import or export it, and send
emails. Staff with view permission have read-only access. The admin permits one
campaign record and does not allow campaign deletion.

Saving a campaign updates its dashboard presentation. Email sending is a
separate action; saving or changing dates does not send messages.

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

`DonationCampaign` stores the text used by the dashboard card, invitation,
story, and emails. Layout, styling, icon artwork, and navigation are defined by
the application.

| Content             | Fields and behavior                                                                                                                                                               |
| ------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Email               | `subject` is the inbox subject; optional `preheader` supplies the inbox preview text. `headline` and `body` provide the message content.                                          |
| Dashboard           | `card_title`, `card_summary`, and `popup_summary` provide the compact appeal.                                                                                                     |
| Donation            | `goal_usd`, `goal_currency_label`, and `donation_url` define the displayed goal and payment destination.                                                                          |
| Story               | Story headings, summaries, goal text, and promises accompany the ordered `story_cards`. Each card has a `title`, `description`, and an `icon` of `survey`, `gis`, or `mobile`.    |
| Recipient           | `recipient_name`, `recipient_intro`, and `tax_deductibility_notice` identify the receiving organization and display its tax-status wording beside donation actions and in emails. |
| Labels and branding | Button text, accessibility labels, dismissal-error text, photo credit, contact information, tagline, and email footer copy are editable.                                          |

`goal_message` and `card_summary` support `{goal}`, replaced with the formatted
fundraising goal. `recipient_intro` supports `{recipient}`, replaced with the
recipient name. Content is plain text and is escaped when rendered as HTML.
Story titles and goal captions support line breaks.

The reminder label is editable independently of `reminder_days`; its wording
should match the configured interval. New records contain no prefilled campaign
prose. The tax notice displays the supplied wording; SpeleoDB does not verify an
organization's tax status.

### Campaign photo

The optional image upload is shared by the dashboard and HTML email. Alternative
text and photographer credit are stored with the campaign. Without an upload,
the photo is omitted.

A public image endpoint serves the current upload from media storage. The image
remains accessible after the campaign ends so previously sent emails can still
display it. Replacing the photo changes what that endpoint serves, including for
older emails once their cached image expires.

## Sending email

The campaign's **Send email campaign** page has separate test and full-audience
workflows:

1. **Send test email** accepts explicit addresses separated by commas or
   newlines. Only those addresses receive the test message.
2. **Review send** prepares the registered-account audience and captures the
   current campaign content. Addresses are deduplicated, empty addresses are
   excluded, and SpeleoDB-update opt-outs are respected. Inactive accounts are
   included.
3. **Send to accounts** confirms that review and queues delivery. The review
   expires after one hour; content or audience changes require a fresh review.

Each recipient receives a separate HTML email with a plain-text alternative.
Delivery runs asynchronously, with results available in Django's Task results
admin. A single-recipient send opens its task detail; multiple recipients open a
filtered task list. Once a full-audience send is submitted, another
full-audience send is disabled for that campaign, even after task history
expires.

Unsubscribe links change the recipient's SpeleoDB-update preference. Test-email
unsubscribe links are informational and do not change preferences. Open and
click tracking are disabled. Provider acceptance of a message does not confirm
inbox delivery or a donation.

## Import, export, and dismissal history

Campaign import/export is available to active superusers. Retaining the exported
campaign ID updates the existing record. Imports preserve launch history and
user dismissals and do not send email. The photo column contains its storage
path, so the image file must be transferred separately between environments.

**Campaign dismissals** lists each account's first and latest dismissal times.
Active superusers can inspect and delete these records, but cannot add or edit
them. Deleting a dismissal makes the account eligible for the invitation again
while the campaign is active.

See [backend operations](donation-campaign-backend.md) for delivery execution,
task-result retention, unsubscribe handling, and production email-provider
requirements.
