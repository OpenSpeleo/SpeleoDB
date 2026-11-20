# Sign in with SpeleoDB

Registered websites can use SpeleoDB as an OpenID Connect provider.

## Configure the provider signing key

The devcontainer’s Compose setup job generates a 4096-bit RSA key in the web
checkout’s ignored `.env` when the setting is missing, empty, or still contains
the template example. Subsequent runs reuse the same key. If the setup process
already has `DJANGO_OIDC_PRIVATE_KEY` in its environment, it skips generation.

CI needs no private-key secret: the `oidc_public_key` pytest fixture generates
a fresh RSA signing key. Startup rejection tests supply their own invalid keys
and a test-only Django secret so they reach signing-key validation without
depending on a developer's environment or `.env` file.

For a manual setup or production deployment, generate an unencrypted 4096-bit
RSA private key for the Django web server. Celery workers, Beat and client
applications do not need the key.

```sh
openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:4096
```

In the web checkout’s ignored `.env`, put the opening single quote immediately
before OpenSSL’s BEGIN line and the closing single quote immediately after its
END line. Paste every line of output, keeping the line breaks.

```dotenv
DJANGO_OIDC_PRIVATE_KEY='<first line of OpenSSL output, including the dashes>
<all lines of key material>
<last line of OpenSSL output, including the dashes>'
```

For Railway, paste the multiline PEM directly into the web service variable
without the surrounding quotes. Restart the web process to load the key. To
check it separately, run `python manage.py check --deploy --tag oidc`.

## Register a website

A SpeleoDB superuser creates an OpenID Connect client in Django admin with a
display name and the website’s exact callback URL. Store the client ID and the
secret shown at registration on the website’s backend.

## Connect a sign-in button

1. Configure an OIDC client library with the issuer `https://www.speleodb.org`,
   the credentials and the registered callback. The public discovery document is
   at `/.well-known/openid-configuration`.
2. Send the browser through the authorization code flow with S256 PKCE, state
   and nonce. Request `openid` for sign-in, `email` for email claims and
   `data:read` for optional API access.
3. At the callback, have the library validate state, exchange the code and
   validate the ID token. Identify the user by issuer and subject. Keep tokens
   server-side and return the user to their original local page.

Send the access token as `Authorization: Bearer <access_token>`. With
`data:read`, v2 GETs use the same handlers and user permissions as ordinary
requests, including Git clone and reset. The sole GET exception is
`/api/v2/user/auth-token/`. Other HTTP methods and Git pushes are unavailable
with the access token. Ordinary responses can include GIS sharing links, which
retain their own lifetime.

Users with active connections can open **Connected Apps → Manage Apps** in
Account Settings to review each app’s permissions and revoke access.

## Run the example

With Django at `http://localhost:8000`, register
`http://127.0.0.1:8300/callback`. In the monorepo’s
`apps/speleodb-oidc-example/`, copy `.env.example` to `.env`, enter the client
ID and secret, and run `bun run dev`. Open `http://127.0.0.1:8300` and sign in
to see the user’s identity and, with data access, their project count.
