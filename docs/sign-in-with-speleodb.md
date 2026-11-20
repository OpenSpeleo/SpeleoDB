# Sign in with SpeleoDB

Registered websites, browser apps and native apps can use SpeleoDB as an OpenID
Connect provider.

## Configure the provider signing key

The devcontainer’s Compose setup job generates a 4096-bit RSA key in the web
checkout’s ignored `.env` when the setting is missing, empty, or still contains
the template example. Subsequent runs reuse the same key. If the setup process
already has `DJANGO_OIDC_PRIVATE_KEY` in its environment, it skips generation.

CI needs no private-key secret: the `oidc_public_key` pytest fixture generates a
fresh RSA signing key. Startup rejection tests supply their own invalid keys and
a test-only Django secret so they reach signing-key validation without depending
on a developer's environment or `.env` file.

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

## Configure the instance and register a client

For a staging or self-hosted production installation, set `DJANGO_OIDC_ISSUER`
on the Django web service to the instance’s canonical HTTPS origin, for example
`https://stage.speleodb.org`. Production defaults to `https://www.speleodb.org`.
Local settings derive the issuer from the request. Open the discovery document
on that exact origin and verify its `issuer` and advertised endpoints.

To sign in from a local browser app against staging, set
`DJANGO_OIDC_ALLOW_HTTP=true` on the staging **Django web service** and restart
it. Keep `DJANGO_OIDC_ISSUER=https://stage.speleodb.org` and register the app’s
exact HTTP callback, including its port and path. The switch defaults to
`false`, even with `DEBUG=True`. Turning it off blocks new sign-ins and pending
consent for HTTP callbacks.

In Django admin, a superuser creates an OpenID Connect client with a display
name and the exact callback URLs, one per line. Choose the type at creation.

- **Confidential** is the default for a website with a backend. Store the
  generated client ID and one-time secret on that backend.
- **Public** is for a browser or installed app. Give users the generated client
  ID. The app exchanges its authorization code with its client ID and PKCE
  verifier. The registered HTTP(S) callbacks determine which web origins may
  read this client’s token and revocation responses. Connected Apps links to the
  website when the callbacks identify one web origin. An installed app can
  register an exact reverse-domain URI such as
  `org.karstunderwater.speleomap:/oauth/callback/…`.

When HTTP callbacks are enabled, both client types can use `127.0.0.1` or
`[::1]`. Public clients can also use `localhost`.

For SpeleoMap, enter the instance URL in the app, copy its displayed
issuer-specific callback URLs into the **Public** registration, then enter the
generated **client ID** in SpeleoMap. Register the callback for each platform
you use. If the browser map downloads GeoJSON from separate object storage,
configure that storage to allow GET requests from the web app’s origin. SpeleoDB
issues a signed download URL for each available artifact.

## Connect a sign-in button

1. Configure an OIDC client library with the issuer `https://www.speleodb.org`,
   the registered client ID, callback and client authentication method. The
   public discovery document is at `/.well-known/openid-configuration`.
2. Send the browser through the authorization code flow with S256 PKCE, state
   and nonce. Request `openid` for sign-in, `email` for email claims and
   `data:read` for optional API access.
3. At the callback, have the library validate state, exchange the code and
   validate the ID token. Identify the user by issuer and subject. Confidential
   clients keep tokens server-side. Native clients use OS-protected storage.
   Return the user to their original local page.

Registered browser apps can use GET or POST at UserInfo with a bearer access
token. The response includes `sub` for the user and `aud` for the registered
client that obtained the access token. A service authenticating a client’s
requests through UserInfo can compare `aud` with its configured client ID.

Send the access token as `Authorization: Bearer <access_token>`. With
`data:read`, v2 GETs use the same handlers and user permissions as ordinary
requests, including Git clone and reset. The sole GET exception is
`/api/v2/user/auth-token/`. Other HTTP methods and Git pushes are unavailable
with the access token. Ordinary responses can include GIS sharing links, which
retain their own lifetime.

Users with active connections can open **Connected Apps → Manage Apps** in
Account Settings to review each app’s permissions and revoke access.

## Run the example

Set `DJANGO_OIDC_ALLOW_HTTP=true` in the web checkout’s `.env`. With Django
running at `http://localhost:8000`, register `http://127.0.0.1:8300/callback`.
In the monorepo’s `apps/speleodb-oidc-example/`, copy `.env.example` to `.env`,
enter the client ID and secret, and run `bun run dev`. Open
`http://127.0.0.1:8300` and sign in to see the user’s identity and, with data
access, their project count.
