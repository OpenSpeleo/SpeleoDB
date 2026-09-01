# Verify Local Compose Environment Precedence Before Changing Runtime Logic

When a browser receives an obvious placeholder credential, inspect the complete
configuration path before changing application or frontend fallback logic.

For local SpeleoDB services:

- `.envs/.django` becomes OS environment through Compose.
- Django also reads the repository-root `.env`.
- OS environment values take precedence over values loaded from `.env`.
- Compose uses the root `.env` for `${...}` interpolation.

A placeholder in `.envs/.django` can therefore silently shadow a valid private
root value. Make the intended owner explicit in `local.yml`, remove the
duplicate placeholder, inspect `docker compose config`, and verify the active
container/settings value without printing the credential. Existing containers
have immutable environments, so a plain `docker restart` is insufficient after
the Compose model changes. Keep standalone and devcontainer startup on the same
complete Compose build/up graph; do not introduce a selected-service `--no-deps`
path. Do not compensate in JavaScript for an infrastructure precedence bug.
