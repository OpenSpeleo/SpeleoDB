# Email delivery

Email backends are configured through Django's `MAILERS["default"]`. Base
settings use SMTP at localhost:25 with a five-second timeout; local settings
write `.eml` files under `.workdir/emails`; tests use the in-memory backend.
`DJANGO_EMAIL_BACKEND` still selects the backend in base/local settings. SMTP
and file backends receive only their relevant options, since mailers reject
unknown options. Custom backend paths must accept the supplied options; custom
SMTP/file subclasses need their connection/file options configured explicitly.

Production keeps Anymail's MailerSend backend and existing `ANYMAIL`
credentials. Its HTTP timeout remains Anymail's existing default; the former
`EMAIL_TIMEOUT` setting applied only to SMTP. See Django's
[mailer migration guide](https://docs.djangoproject.com/en/6.1/howto/mailers-migration/).

Account mail keeps delivery errors non-fatal through the backend's
`fail_silently` attribute. The adapter obtains a fresh backend from `mailers`
for each send, so this policy never changes the default for export notifications
or other callers. Backend-specific exception handling remains in the backend;
template errors and unexpected errors still propagate. This adds no database
queries and preserves the existing per-send connection lifecycle.

Anymail 15.2 still supports this backend attribute but plans to remove its
fail-silent behavior after Django 6.2. Revisit the account-delivery exception
policy when upgrading Anymail rather than assuming every backend error inherits
`OSError`. The local test environment does not install the production-only
Anymail package.

Export notifications continue to surface SMTP failures to the job retry logic.
The lifecycle test uses a bound, non-listening socket with a scoped `MAILERS`
override, then restores normal delivery and verifies that retry reuses the
artifact without extending its expiry.

Verification runs in the application container. Adapter tests verify successful
signup/email changes, real SMTP failure isolation, and unexpected-error
propagation. Settings tests construct the supported local backends and verify
file delivery, including `.eml` naming. Django 7.0 deprecations are treated as
errors in the affected regression tests and during the focused verification run.
The settings subprocess supplies an explicit test-only `DJANGO_SECRET_KEY` with
base/local dotenv loading disabled. This keeps the probe independent of
developer secrets and the test-settings fallback, which does not populate the
environment required by local settings.
