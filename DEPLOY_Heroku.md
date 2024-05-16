# Deploy Instructions

## A. Create the App and associate the domain

```bash
heroku create --buildpack heroku/python
>>> Creating app... done, ⬢ <app_name>

heroku domains:add www.domain.com -a <app_name>
>>> Configure your app's DNS provider to point to the DNS Target <subdomain>.herokudns.com.
```

Now edit your DNS Zone: `CNAME  www  <subdomain>.herokudns.com.` (Note keep the `.` at the end)

Confirm it works with:

```bash
host www.domain.com
>>> www.domain.com is an alias for <subdomain>.herokudns.com
```

## B. Add PostgreSQL support

```bash
heroku addons:create heroku-postgresql:essential-0 -a <app_name>
>>> Created <db_name> as DATABASE_URL

# Creating automatic backups:
heroku pg:backups schedule --at '04:00 America/New_York' DATABASE_URL -a <app_name>

# Set as primary DB:
heroku pg:promote DATABASE_URL -a <app_name>
```

## C. Add Redis support

```bash
heroku addons:create heroku-redis:mini -a <app_name>
>>> Created <db_name> as DATABASE_URL

# Set CELERY_BROKER_URL to REDIS
heroku config:set CELERY_BROKER_URL=`heroku config:get REDIS_URL`
```

## D. Add mailgun support

```bash
heroku addons:create mailgun:starter -a <app_name>
```

## E. Set Environment Variable

```bash
heroku config:set PYTHONHASHSEED=random

heroku config:set WEB_CONCURRENCY=4

heroku config:set DJANGO_DEBUG=False
heroku config:set DJANGO_SETTINGS_MODULE=config.settings.production
heroku config:set DJANGO_SECRET_KEY="$(openssl rand -base64 64)"

# Generating a 32 character-long random string without any of the visually similar characters "IOl01":
heroku config:set DJANGO_ADMIN_URL="$(openssl rand -base64 4096 | tr -dc 'A-HJ-NP-Za-km-z2-9' | head -c 32)/"

# Set this to your Heroku app url, e.g. 'bionic-beaver-28392.herokuapp.com'
heroku config:set DJANGO_ALLOWED_HOSTS=www.speleodb.com

heroku config:set DJANGO_FIELD_ENCRYPTION_KEY="$(openssl rand -base64 32)"
```

## F. Publish to Heroku

```bash
git push heroku master

# Create superadmin
heroku run python manage.py createsuperuser

# Check deployment
```
