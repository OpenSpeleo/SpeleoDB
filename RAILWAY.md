# Install the Railway CLI

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

Execute the following:

```bash
railpack build .
```

Verify
```bash
  ↳ Using config file `railpack.json`
  ↳ Using provider Python from config
  ↳ Using uv

  Packages
  ──────────
  pipx    │  1.7.1   │  railpack default (latest)
  python  │  3.13.3  │  custom config (3.13)

  Steps
  ──────────
  ▸ install
    $ pipx install uv
    $ uv sync --extra production --frozen

  Deploy
  ──────────
    $ python manage.py migrate && gunicorn backend.wsgi:application
```

The file `railpack.json` is generated using `railpack prepare --plan-out out.json .` to "inspect the default configuration".
