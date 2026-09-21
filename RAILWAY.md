# Railway configuration

`.railway/railway.ts` is the sole Railway service configuration for this
repository. It owns the production web, Celery worker, Beat, and Kanchi
settings. The deprecated `railway.toml` has been removed; do not recreate it or
add a `railway.json`. Preserve the existing named partial so applying this file
does not take ownership of unrelated services or databases.

`railpack.json` is the image-build recipe, including Python dependencies and
frontend assets. It keeps the Python provider and runs frontend commands through
Mise with the Node major read from `.node-version`; do not duplicate that major
in the Railpack package map. Service start commands, predeployment commands,
resources, and environment references belong in `.railway/railway.ts`.

Validate edits in the running application container:

```bash
docker exec -w /app speleodb_local_django npm run typecheck:railway
```

For the intended Railway project/environment, preview with `railway config plan`
and review the changes before `railway config apply`. IaC settings require an
apply; pushing application code alone does not apply edits to this file. See
[operations and ownership boundaries](docs/background-jobs-operations.md#railway-deployment)
and
[Railway's IaC documentation](https://docs.railway.com/infrastructure-as-code).

## Install the Railway CLI

```bash
curl -fsSL https://railway.app/install.sh | sh
```

## Login to Railway

```bash
railway login

railway link
```

## Create a superuser

```bash
railway run python manage.py createsuperuser
```

## Generate some random URLs

```bash
DJANGO_HIJACK_URL="$(openssl rand -base64 4096 | tr -dc 'A-HJ-NP-Za-km-z2-9' | head -c 32)"
DJANGO_ADMIN_URL="$(openssl rand -base64 4096 | tr -dc 'A-HJ-NP-Za-km-z2-9' | head -c 32)"
```

#### DEPLOY DEBUG Commands

A. Install `railpack`

```bash
curl -sSL https://railpack.com/install.sh | sh
```

B. Install `mise`

```bash
brew install mise
```

C. Start BuildKit

```bash
docker run --rm --privileged -d --name buildkit moby/**buildkit**
export BUILDKIT_HOST='docker-container://buildkit'
```

D. Launch the build

Execute the following:

```bash
railpack build .
# OR
railpack build --show-plan .
# OR
railpack prepare --plan-out out.json .
```

Verify

```bash
  ↳ Using config file `railpack.json`
  ↳ Using provider Python from config
  ↳ Using uv

  Steps
  ──────────
  ▸ install
    $ uv sync --locked --no-dev --no-install-project

  ▸ build
    $ uv sync --extra production --frozen
    $ mise exec -- node --version
    $ mise exec -- npm ci
    $ mise exec -- npm run build
    $ rm -rf node_modules

  Deploy
  ──────────
    $ python manage.py migrate && gunicorn backend.wsgi:application
```

Mise discovers Node from `.node-version`; `mise exec --` activates that
repository-owned version without duplicating the major in `railpack.json`. Use
`railpack prepare --plan-out out.json .` to inspect the effective plan.
