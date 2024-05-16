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

## B. Create the App and associate the domain
