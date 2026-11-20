# Public supporters and donations

The public Supporters page at `/supporters/` credits the organizations and
people who sustain SpeleoDB. Visitors can reach it from the public navigation or
footer. The directory is also included in the public sitemap.

## Editing the credits

In Django admin, open **Supporting Organizations** or **Supporting People**
under **Frontend_Public**. Each saved record appears on the public page. Enter
the name exactly as it should be credited. The administrator chooses which
supporters to publish. Campaign donor lists and acknowledgment letters are
private and separate from this directory.

- **Organizations** require a name, website, and logo. Upload a PNG, JPEG, or
  WebP suitable for a light neutral background. Use a transparent PNG or WebP
  when the mark needs transparency. SpeleoDB serves the original image at its
  natural aspect ratio inside a padded area. The logo and organization name form
  one link to the website. Set **Order** in the admin list to place
  organizations. Lower values come first, ties sort by name, and entries with a
  blank order follow in name order.
- **People** appear alphabetically by their full display name, ignoring case.
  Every name uses the same typography. Enter a website to add a link with a
  small arrow, or leave it blank to publish plain text.

Organization and individual websites open in a new tab. An empty category
disappears, including its heading. Before the first entry, visitors see the
introduction and a collective thank-you.

### Importing and exporting people

Open **Supporting People** and choose **Export** to download the directory. For
a CSV you can edit and reimport, keep all three columns: `id`, `name`, and
`website`. Keep the exported ID to update a person, including when changing
their name. Leave the ID cell empty to add someone new. A name is required, and
a blank website publishes the name without a link. Two people can share a name
because the import matches on ID.

Choose **Import**, upload the edited file, review the proposed changes, then
choose **Confirm import** to publish them. Active staff can import and export
supporting people through their usual admin access.

## Enabling donations

Set the web process environment variable `SPELEODB_DONATION_CAMPAIGN_URL` to the
full HTTPS donation destination. Restart the web process after changing its
environment. Both donation links open this URL in a new tab. An empty value or
an invalid HTTPS destination hides the donation section and its hero link.
Credits remain visible throughout the year.

For local development, set the value in the web checkout's `.env` and restart
Django. If Compose supplies the variable through an `env_file`, recreate the web
service to load the new value. To enable giving on Railway, add the chosen URL
to the web service's managed environment in `.railway/railway.ts`, then follow
the configuration plan, apply, and runtime verification procedure in the
[Railway operations guide](railway-production.md). The directory can launch with
that variable absent. Dated dashboard campaigns continue to use their own
[campaign action URL](donation-campaign.md).

## Design and delivery

The explorer’s headlamp lights an amber heart in the opening illustration,
shared with the campaign thank-you page. The credits follow immediately. The
navy background fades into apricot as the People credits come into view. Two
illustrated cave divers meet in a fist bump. Each person gets a separate line
beside the illustration on desktop and beneath it on small screens. Browsers
with reduced motion or without scroll-driven animation show the completed
illustration. Names and links remain readable throughout. The apricot background
continues through the optional donation invitation and the crew’s sign-off, then
fades back to navy above the footer.

The `frontend_public` app owns the two editorial models and their admin forms.
The public Django view reads each ordered category once and renders the page,
including every credit and link, on the server. Organization logos use unsigned
URLs under `media/supporters/organizations/{uuid}.ext`. Each upload gets a new
UUID. JPEG, PNG and WebP uploads retain their original bytes. HEIC and HEIF
uploads are converted to JPEG. In production, the CloudFront behavior for
`media/supporters/organizations/*` must allow unsigned viewer requests, as it
does for People photos.

The public view tests cover the empty directory, published credit order,
donation availability, and donor privacy. The organization upload test covers
public recognition and retrieval of the saved wordmark. Review layout changes on
desktop and phone.
