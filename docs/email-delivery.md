# Email delivery

Development mail uses Django's SMTP backend through `MAILERS["default"]` and
Mailpit. Open the inbox at <http://localhost:8025> to inspect account
verification, password reset, and export notification messages. Mailpit captures
messages; no relay or forwarding is configured.

The shared local Compose file owns Mailpit for both devcontainers. SMTP is
published on host loopback port 1025 and the inbox on host loopback port 8025.
Standalone web uses host networking and connects to `localhost:1025`; the
monorepo override sets `DJANGO_EMAIL_HOST=mailpit` for Compose networking.
`DJANGO_EMAIL_PORT` defaults to 1025. Connections use no authentication or TLS
and have a five-second timeout. `DJANGO_EMAIL_BACKEND` can still select another
backend; SMTP options are supplied only to the standard SMTP backend.

Mailpit uses temporary storage without a volume. Mail can disappear on restart
or recreation. Historical `.workdir/emails` files remain ignored and untouched;
new mail is no longer written there. There is no database migration or mailbox
import. Base settings retain SMTP on localhost port 25; tests use in-memory
mail.

Rebuild/reopen the devcontainer through its normal Compose lifecycle to apply
service and environment changes, preserving existing volumes. If delivery fails,
check Mailpit health and the sender's SMTP hostname before resending. This adds
one small development service and a bounded SMTP connection per send, with no
additional application database queries.

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
SMTP settings and non-SMTP option isolation. Live verification sends mail from
web and worker containers and reads it back through the Mailpit API. Django 7.0
deprecations are treated as errors in the affected regression tests and during
the focused verification run. The settings subprocess supplies an explicit
test-only `DJANGO_SECRET_KEY` with base/local dotenv loading disabled. This
keeps the probe independent of developer secrets and the test-settings fallback,
which does not populate the environment required by local settings.
