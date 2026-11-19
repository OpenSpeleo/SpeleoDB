# Donation acknowledgments

The campaigns section of Django admin lets an active superuser acknowledge a
verified monetary gift in US dollars, including gifts from people without
SpeleoDB accounts. Confirm the gift against the payment record first. PayPal
handles campaign payments. Visiting the public thank-you page, entering an email
in the fundraiser's donor-exclusion list, and saving an acknowledgment draft do
not issue a receipt.

## Prepare a template

Add a donation thank-you template with a descriptive name, email subject, and
email design. The printed letter carries the USAH Institute logo at the top
left. The two signatures share a line. Alberto Nava, President, aligns with the
left margin and Jonathan Dekhtiar, Vice-President, aligns with the right margin.
Check the letterhead and signatures in the preview before issuing the first
gift.

Use **Save & send preview** next to the template selector to send a sample email
and its attached PDF to your own admin account. The email uses the template's
subject verbatim. The sample donor is fictional. A preview never creates an
official acknowledgment. Preview and live emails use identical subjects, plain
text, HTML, and PDF presentation for the same gift details. Preview handling
only changes the recipient and delivery/issuance bookkeeping; it adds no
banners, watermarks, or alternate wording. Draft PDFs show the current local
date until issuance fixes the issue date.

## Record and issue a gift

1. Add a donation thank-you letter. Select the template and enter the receipt
   name, email, optional mailing address, positive USD amount, effective date,
   form of payment, and transaction reference. Use a unique bookkeeping
   reference for a gift received without a processor ID.
2. Save the draft. **Save & preview PDF** saves the entered details, opens the
   PDF in a new tab, and returns the original tab to the saved edit form. If the
   browser blocks the tab, allow pop-ups and try again. Validation errors keep
   the edits on the current form. Letter add/edit forms use a plain template
   selector without related-object edit, add, delete, or view icons; their
   preview action is in the footer. The reusable template's own admin form
   retains **Save & send preview**.
3. Choose **Review & issue**, check the donor email and financial details, then
   use **Review PDF** to open the PDF in a new tab, then confirm the orange
   **Issue & send** button. Django archives the official PDF and submits one
   transactional message with that PDF attached. The issue date and the gift's
   effective date appear separately. The receipt states the amount in USD.
4. After issuance, admin opens the delivery task directly so you can inspect its
   result. Acceptance records the mail backend's acknowledgment of the send.
   Inbox arrival depends on the receiving provider.

Provide acknowledgments promptly. For an individual monetary contribution of
$250 or more, the IRS requires a contemporaneous written acknowledgment for the
donor to substantiate a deduction. See the
[IRS written acknowledgment requirements](https://www.irs.gov/charities-non-profits/charitable-organizations/charitable-contributions-written-acknowledgments)
and
[IRS guidance on timing](https://www.irs.gov/charities-non-profits/charitable-organizations/charitable-organizations-substantiation-and-disclosure-requirements).

## Regenerate or resend a letter

The issued letter has one action row without a section heading: **Download
archived PDF**, **Save & regenerate PDF**, and **Resend archived PDF**. Download
opens in a separate tab. Regeneration saves the current form; resending uses a
separate POST form so unsaved or invalid edits do not change the archived send.

Open the issued letter, edit any donor or gift details, and choose **Save &
regenerate PDF**. This updates the stored PDF under the same acknowledgment ID
and original issue date. You can also regenerate after updating the print
design. Download the PDF from that record to review it.

Choose **Resend archived PDF** to send the currently stored copy to the donor.
If the send fails after issuance, the official PDF is already archived. Check
the task result, and, if acceptance is uncertain, reconcile the send with the
provider before explicitly resending. The task details include the addressed
email and gift amount, so only superusers can inspect acknowledgment tasks.

## Implementation and verification

`DonationThankYouTemplate` selects a UUID4-named HTML file from
`speleodb/templates/campaigns/thank_you_email_templates/`. The email receives
`letter`, `template`, `amount_usd`, `site_url`, and `email_assets_url`.
Renderers receive no preview flag. Use Django's normal HTML escaping. Keep
essential text in the email body for image blocking and plain-text readers. The
shipped illustration uses the existing collected campaign static-asset
directory.

`DonationThankYouLetters` holds one acknowledgment per gift, identified by a
stable UUID and a unique transaction reference. The shared print template uses
PyMuPDF to lay out selectable text on US Letter pages. The letter text, receipt,
and page numbers use Liberation Sans Regular. The two officer signatures are
handwritten illustrations. Issuing a letter stores its PDF in private object
storage and queues delivery through the existing Celery publisher.

The signed storage backend uses a separate `donation-thank-you-letters/` prefix
and private, no-store cache metadata. Include this prefix with the application's
private media in storage backups and retention policies. Public static assets
contain only presentation artwork. The test environment exercises the same
storage protocol against RustFS.

Focused tests live with the campaign tests and cover donor input, access,
preview isolation and live-content parity, receipt text, stored and emailed PDF
bytes, delivery, and regeneration. For design changes, preview a long address
and transaction reference, check both signatures on the printout, and inspect
the delivered email in Mailpit with images enabled and blocked.

PDF preview navigation uses the existing typed admin preview controller. The
save action returns the saved edit URL and PDF URL after native form validation;
the controller opens the tab during the click and navigates both tabs only after
a successful save. No acknowledgment is issued by opening a preview. The review
page groups **Review PDF**, **Issue & send**, and **Back to draft** in that
order, using shared admin button styling with warning colors for issuance.
