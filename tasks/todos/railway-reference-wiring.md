# Railway connection reference correction

- [x] Inspect current variables, source configuration, and deployment state.
- [x] Inventory raw reference expressions and verify the owning Redis/PostgreSQL
      variables.
- [x] Define the broker URL on Redis using its own credential/address
      references.
- [x] Point application services directly at the Redis-owned broker variable.
- [x] Compose Kanchi's database URL from its own credentials and PostgreSQL's
      private hostname reference and private port.
- [x] Replace the web dashboard URL with a reference to Kanchi's public
      hostname.
- [x] Verify raw references and exact rendered-value equivalence before removing
      copied shared data.
- [x] Update IaC, operations docs, and lessons; typecheck and verify live
      connections.

## Intent

The user rejected copied connection strings. Infrastructure owns its connection
settings; consumers reference those settings directly. Kanchi continues to own
its separate PostgreSQL database/user credentials. Preserve sealed auth secrets,
all running services, and unrelated staged repository changes.

## Review

Completed on September 15, 2026. The live raw configuration now contains:

- Redis: `CELERY_BROKER_URL=${{REDIS_URL}}/1`.
- Web, worker, Beat, and Kanchi:
  `CELERY_BROKER_URL=${{Redis-Prod.CELERY_BROKER_URL}}`.
- Kanchi:
  `DATABASE_URL=postgresql+psycopg://kanchi:${{DATABASE_PASSWORD}}@${{Postgres-Prod.PGPRIVATEHOST}}:5432/kanchi`.
- Web: `KANCHI_URL=https://${{Kanchi.RAILWAY_PUBLIC_DOMAIN}}/ui/`.
- Kanchi's allowed hosts and origins reference its own `RAILWAY_PUBLIC_DOMAIN`.

Kanchi's existing dedicated database password was moved intact into its own
`DATABASE_PASSWORD` variable; no credentials were rotated. Its sealed login,
session, and token secrets remain preserved. PostgreSQL's `PGPRIVATEHOST`
references its private domain, while `PGHOST` and `PGPORT` describe the public
proxy; the private connection deliberately uses port 5432.

Raw variable inventory across all 12 production services found zero remaining
consumers of `shared.CELERY_BROKER_URL`. The obsolete shared variable was then
deleted. Environment read-back shows zero shared variables and no staged
changes. Rendered broker, database, and dashboard URLs match their prior working
values exactly, both before and after deletion. Kanchi's hostname references
resolve to `kanchi.speleodb.org`. Variable writes used `skipDeploys`; this
equivalent reference correction required no restart.

Live Kanchi verification confirmed Redis `PING` on private database 1,
PostgreSQL database/user `kanchi`, and 40 persisted monitored tasks. Curl checks
returned 200 for web, Kanchi health, and Kanchi UI, and 401 for anonymous access
to Kanchi's protected configuration API. Python urllib requests were rejected
with 403; the successful curl responses included Railway origin headers.

`npm run typecheck:railway` passed in the Django container. A fresh production
IaC plan contains no variable drift, additions, or removals; only the previously
verified null-to-default restart/watch-pattern differences remain.
`git diff --check` passed. Documentation now describes owner-service references
and does not recommend copied connection strings.

The operator's new Git push queued deployments for web, worker, and Beat behind
GitHub checks while this correction was in progress. Existing deployments keep
serving; these new queued releases are separate from the verified rollout.
