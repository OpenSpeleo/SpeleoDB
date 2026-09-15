# Railway background service rollout

- [x] Inspect repository service contracts, lessons, and live production
      inventory.
- [x] Report required variables and correct their scope to match actual
      consumers.
- [x] Move Kanchi settings and the web dashboard link to their owning services;
      replace the initial shared broker copy with a Redis-owned reference.
- [x] Verify Redis persistence/eviction, application migrations, and
      installation of background schedules.
- [x] Verify Beat dispatches the intended maintenance and artifact cleanup
      schedules.
- [x] Provision and verify an isolated Kanchi database/user on existing
      PostgreSQL.
- [x] Verify Kanchi's service-local runtime variables, enabled authentication,
      valid hash format, and distinct secrets.
- [x] Configure worker/Beat Git rebuilds and explicit placement for all three
      new services.
- [x] Create the empty Kanchi service and attach its custom hostname on
      port 8765.
- [x] Verify DNS, certificate, and HTTPS access for the Kanchi custom hostname.
- [x] Reconcile IaC with Git-triggered worker/Beat rebuilds and current web
      configuration.
- [x] Validate the configuration, review the production plan, and apply the
      authorized IaC changes.
- [x] Create Celery-Worker and Celery-Beat and verify their Git source settings.
- [x] Verify Kanchi deployment success, broker connectivity, and persisted
      retention settings.
- [x] Create/deploy Celery-Worker, Celery-Beat, and Kanchi; wire web
      broker/dashboard.
- [x] Verify exact deployments, queue consumers, singleton scheduler, anonymous
      API rejection, and Kanchi task ingestion.
- [x] Record results and separate future operator smoke checks in docs and
      tasks/todo.md.

## Scope and plan check-in

User authorized creation and deployment of the newly added background services
and rebuilds on Git updates. Production is project `speleoDB`, environment
`production`. Preserve the existing PostgreSQL/Redis servers and unrelated
services. Start one worker consuming both queues, one Beat scheduler, and one
pinned Kanchi image. Operator supplies login settings directly on Kanchi as
`BASIC_AUTH_USERNAME` and `BASIC_AUTH_PASSWORD_HASH`. The selected custom
hostname is `kanchi.speleodb.org`, targeting port 8765.

## Variable-scope correction

The user clarified that shared variables are only for values consumed by
multiple services. Initially only `CELERY_BROKER_URL` remained shared; the
subsequent reference correction removed that copy too. Kanchi owns its native
`DATABASE_URL`, `SESSION_SECRET_KEY`, `TOKEN_SECRET_KEY`, `ALLOWED_HOSTS`,
`ALLOWED_ORIGINS`, and basic authentication variables; the web service owns
`KANCHI_URL`. Existing values were moved to those service-local destinations,
and the six shared Kanchi-prefixed copies were removed. IaC preserves sensitive
Kanchi values and makes `ALLOWED_EMAIL_PATTERNS` reference the same service's
`BASIC_AUTH_USERNAME`. No environment-wide shared variables remain after the
reference correction. The operator-staged username was moved intact to Kanchi,
and the staged shared copy was cleared. The user supplied and sealed
`BASIC_AUTH_PASSWORD_HASH`, `SESSION_SECRET_KEY`, and `TOKEN_SECRET_KEY`,
updated settings/DNS, and explicitly authorized continuing deployment. Operator
credentials were preserved.

The corresponding rule is captured in
[the Railway variable-scope lesson](../lessons/railway-variable-scope.md).

## Review

The infrastructure rollout is complete. All four exact deployments reached
`SUCCESS`. Web, worker, and Beat track `master` with GitHub checks and no commit
pin; worker and Beat have no path filters. The three new services each use one
replica in `us-east4-eqdc4a`. Container Railway typechecking and
`git diff --check` pass. The reviewed IaC plan was applied, and live task
execution, monitoring, scheduler ownership, and effective deployment settings
were verified.

Verified production prerequisites:

- Existing Redis uses persistent `/bitnami` storage. Runtime settings are
  `appendonly yes`, `appendfsync everysec`, and `maxmemory-policy noeviction`.
  `redis.conf` and `REDIS_AOF_ENABLED=yes` also retain AOF configuration. Redis
  was not restarted; the saved variable change used `skipDeploys`.
- Kanchi has a dedicated `kanchi` database and login, with superuser, database
  creation, and role creation disabled. The new database used `template0`
  because `template1` has stale collation metadata; existing databases were
  preserved. Provisioning restricted access to the new database.
- Application migration `background_jobs.0001` was already applied, and the
  remote `install_background_schedules` command succeeded.
- Kanchi's `kanchi.speleodb.org` hostname targets port 8765, with CNAME target
  `pxt3era4.up.railway.app`. DNS is verified through the Cloudflare proxy, and
  Railway's certificate is valid. Public HTTPS `/api/health` returns 200;
  unauthenticated `/api/config` returns 401.

## Deployment and runtime verification

Kanchi deployment `175c8fd4-40cb-4055-bb43-16b6d15861a0` reached `SUCCESS`. Its
runtime broker uses private host `redis-prod.railway.internal`, database 1, and
a successful `PING`. Authentication is enabled, the configured password hash has
the supported format, and session/token secrets are distinct. The login UI
returns 200 and protected configuration rejects anonymous access with 401.
Successful login with the operator's sealed password was not tested.

Nested Redis references inside the initial shared broker variable resolved to
empty connection fields. Replacing them with a copied URL restored connectivity
but lost ownership and was rejected by the user. The final configuration puts
`CELERY_BROKER_URL=${{REDIS_URL}}/1` on Redis and uses direct service references
in all four consumers. Kanchi's database URL references PostgreSQL's private
hostname and its own dedicated password. Django's dashboard link references
Kanchi's public domain. See
[reference verification](railway-reference-wiring.md).

`AppConfigService` saved and read back 30-day successful/unsuccessful task
retention and daily cleanup at 03:00 UTC, enabled. The first automatic cleanup
succeeded at 16:18:39 UTC. Kanchi has zero enabled workflows. Persistence across
a future restart can be checked during routine operator maintenance.

| Service       | Deployment ID                          | Last observed status |
| ------------- | -------------------------------------- | -------------------- |
| Celery-Worker | `09585f2f-cd37-4816-bd6f-a4f25c0aa594` | `SUCCESS`            |
| Celery-Beat   | `15b6cea9-37f9-4320-b60e-82cb8056d7e6` | `SUCCESS`            |
| SpeleoDB-Prod | `8ef93121-39df-4ae1-8f9a-3c34d8b9a2d6` | `SUCCESS`            |
| Kanchi        | `175c8fd4-40cb-4055-bb43-16b6d15861a0` | `SUCCESS`            |

Worker and web runtime report commit `c752f5316209f572e7008d56920d689d237c3ec6`;
Beat deployment metadata records the same commit. Effective deployment service
manifests have the intended worker, Beat, and web commands, including the web
predeploy `install_background_schedules` command, with no legacy settings
metadata. Worker and Beat each have one replica, a 120-second draining period,
and the intended application environment settings.

Verified application runtime behavior:

- One worker consumes `exports` and `background_control`, with concurrency 1 and
  default queue `background_control`.
- Read-only `get_users_count` tasks `d91d452a-1123-444d-8dde-cac3aef66c6f` and
  `6219b44c-1273-4e00-aeb6-df056856c96a` both reached `SUCCESS` in Django's task
  results. Kanchi's `task_latest` records both as `task-succeeded`.
- A normal `.delay()` call from the web service dispatched task
  `8a40092d-5fff-46b6-a6da-f3f118a200c7`, which reached `SUCCESS` and returned
  an integer.
- Exactly one PostgreSQL advisory-lock owner holds scheduler lock `736735226`.
  Beat logged dispatch of maintenance and artifact cleanup.
- Web runtime uses private Redis database 1 for the broker and database 0 for
  cache; its dashboard link is `https://kanchi.speleodb.org/ui/`.
- Public web, Kanchi health, and Kanchi login UI each return HTTP 200.

Worker and Beat were created. Their initial creation did not retain GitHub
check-suite gating; reconciliation and read-back now confirm `checkSuites=true`,
branch `master`, and no fixed commit SHA on worker, Beat, and web. Future
Git-triggered releases retain that check gating.

The first manual web rollout was skipped because its GitHub checks were
cancelled. A direct `serviceInstanceDeploy` started the same application commit,
`c752f5316209f572e7008d56920d689d237c3ec6`, for this authorized rollout. It does
not change future Git-triggered check-suite settings.

Railway normalizes omitted fields to default policy/watch-pattern values, which
can produce harmless `null`-to-default differences in a fresh IaC plan. The
effective deployment manifests and live settings are correct; no repeat applies
were performed merely to chase those default differences.

## Future operator smoke checks

The requested service creation and infrastructure rollout are complete.
Successful operator login with the sealed password, retention read-back after a
routine restart, and broader feature checks remain separate operator work:
real-account exports, notification email, authenticated download, and the full
artifact expiry/deletion cycle. These checks were not claimed by the read-only
task smoke tests above.

The operator committed the rollout source during the reference correction;
subsequent documentation edits remain in the working tree.
