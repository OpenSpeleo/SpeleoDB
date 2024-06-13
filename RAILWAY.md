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
