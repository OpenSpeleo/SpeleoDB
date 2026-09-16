# Background jobs: local services and Railway operations

## Ownership and scheduling

SpeleoDB stores user requests, attempts, artifact availability, and notification
state in its application database. `django-celery-results` stores Celery's
technical execution records in that same PostgreSQL instance. Kanchi observes
Celery events and stores its own operational history in a separate database with
its own user on the existing PostgreSQL server. Cache and Celery share the
existing Redis server, using logical databases 0 and 1 respectively. This reuses
the application's infrastructure and keeps worker scaling straightforward. A
Kanchi outage must not prevent exports, retries, or artifact deletion.

**There is no Railway cron job or Railway cron schedule.** A continuously
running Celery Beat process uses `django-celery-beat`'s database scheduler. One
Celery worker service consumes both archive generation and scheduled
maintenance.

| Process   | Command                                | Queue                        |
| --------- | -------------------------------------- | ---------------------------- |
| Worker    | `bash compose/celery/worker/start`     | `exports,background_control` |
| Scheduler | `python manage.py run_background_beat` | Publishes scheduled tasks    |

Each worker replica starts with `--queues exports,background_control`,
concurrency one, prefetch one, and task events enabled. Scale the same worker
service through replicas as demand grows. Maintenance and email tasks can wait
behind exports when every replica is occupied. The authenticated download
endpoint enforces artifact expiry independently of cleanup scheduling; expired
downloads become unavailable even when physical deletion is still queued.

The Beat management command holds a PostgreSQL advisory lock for its lifetime,
including during deployment overlap. Only `install_background_schedules` owns
the feature's periodic task installation. Run it after migrations. Celery result
cleanup must also route to `background_control`.

## Bounded failure recovery

Generation has three attempts per automatic cycle. Broker publication failures
and publications left unclaimed for ten minutes consume that same budget.
Notification publication and delivery share five attempts; object cleanup has
five persisted attempts per object. Retries wait 60/120/240/... seconds, capped
at one hour, without sleeping in the worker between tasks. Due times and counts
live in PostgreSQL, so periodic sweeps and process restarts cannot reset them.
Cleanup records survive exhaustion; staff can explicitly restart cleanup in the
job admin, with an audit entry. Download expiry remains enforced even when
physical deletion fails.

Migration `0002_attempt_cleanup_budget` adds publication tracking and cleanup
counters, due times, errors, and ownership tokens. Apply it before starting the
updated worker/web application; no new service is required. Notifications carry
dispatch tokens, so drain old queued notification messages or deploy scheduler
and worker together to avoid old workers receiving the new task argument. See
[bounded retries](bounded-retries.md) for startup/transport limits and
verification status.

## Docker Compose and devcontainer

Start the full graph from the repository root:

```bash
docker compose -f local.yml up --build
```

Selecting only `django-webserver` does not start the worker, scheduler, and
dashboard. The devcontainer uses the same graph and forwards Django port 8000
and Kanchi port 8765.

| Service             | Reachable from host        | Persistent storage                                                  |
| ------------------- | -------------------------- | ------------------------------------------------------------------- |
| Existing PostgreSQL | `localhost:5432`           | Existing data/backups volumes; separate Django and Kanchi databases |
| Shared Redis        | `localhost:6379`           | `speleodb_local_redis_data`; cache DB0, Celery DB1                  |
| Kanchi              | `http://localhost:8765/ui` | Its database on the existing PostgreSQL server                      |

Shared Redis uses a persistent volume, AOF persistence, and `noeviction` so
cache pressure cannot evict queued tasks. The databases share process memory and
availability; monitor total memory and rejected writes on this server. The
host-networked Django services use `redis://localhost:6379/1` for Celery while
the existing cache URL remains `redis://localhost:6379/0`. Kanchi runs on the
Compose bridge and connects to `redis://redis:6379/1` and
`postgres:5432/kanchi`. Logical databases separate keys, not credentials or
Redis Pub/Sub channels. Do not give Kanchi the Django environment files, source
mount, S3 credentials, GitLab token, or email credentials.

The pinned Kanchi release uses synchronous SQLAlchemy sessions. Its PostgreSQL
URL therefore uses `postgresql+psycopg://`; the upstream installation page's
`postgresql+asyncpg://` example does not match this runtime execution model.

The worker and Beat wait for successful setup and Redis health. Setup runs
`compose/setup_kanchi_database.py` to provision Kanchi's database and user on
the existing PostgreSQL server, including when its volume already contains
Django data. It then runs application migrations and installs the periodic
schedules. Setup stops on failure. Kanchi also waits for this setup service and
the shared database/Redis health checks; there is no separate PostgreSQL
container for it.

The local username/password are `kanchi-local` / `kanchi-local-only`.
Authentication stays enabled. Override local credentials and token secrets in
the private root `.env`. These defaults are for loopback development only. If
overriding `KANCHI_POSTGRES_PASSWORD`, use a URL-safe random value because it
also appears in the database connection URL.

Compose resolves `.env` interpolation before starting setup. Every required
local Kanchi value therefore has a local default in the Compose file; setup does
not need to generate a new environment file before the graph can start. Existing
developer environment files remain intact. Recreate affected containers after
changing variables; a restart does not replace a container's environment.

The private root `.env` also owns `GITLAB_GROUP_NAME`. Compose passes that same
value to setup and all application services, with `speleodb` as the
fresh-install default. Keep an existing namespace such as `speleodb_surveys_dev`
when that is where the repositories live; a copied application database alone
does not move GitLab repositories. The tracked Django env file must not shadow
this choice. Bootstrap refreshes the token for the chosen group without moving
repositories.

`CELERY_BROKER_URL` belongs to the caller/Compose configuration. The Django
entrypoint must not replace it with the cache `REDIS_URL`. If using an external
local broker, set both `CELERY_BROKER_URL` and `KANCHI_CELERY_BROKER_URL` to the
appropriate address for each network namespace.

The worker intentionally has no source auto-reloader: editing a Python file must
not terminate an archive mid-generation. Restart it explicitly after code
changes. Compose gives it 120 seconds to stop gracefully; application attempt
recovery handles longer interrupted work.

The `celery-worker` service has no fixed `container_name`. Each startup adds a
UUID to its Celery node name because host-networked replicas share a hostname.
Scale the existing worker service locally with:

```bash
docker compose -f local.yml up -d --scale celery-worker=2 celery-worker
```

Every replica consumes both queues. Keep Beat at one replica; its database lock
also protects against scheduler overlap during restarts.

Exports are available to every authenticated active account using the normal
account and resource permissions in both local Compose and production. Exports
use ordinary ZIP files with no password and inherit the bucket's existing
storage configuration. The application does not add an export encryption policy
or encryption-specific environment variables. S3 checksum validation remains
enabled.

The default Celery queue is `background_control`, so existing application tasks
without a specific route run on the same worker. Export generation routes to
`exports`.

Named volumes are Compose-project scoped. `docker compose down` preserves them.
Do not use `down --volumes` to troubleshoot bootstrap or dependency failures.

## Container-only verification and isolated live tests

Run Python, Node, lint, type checks, and builds inside the Django container:

```bash
docker compose -f local.yml exec -T django uv sync --frozen --extra local
docker compose -f local.yml exec -T django pytest compose/tests/
docker compose -f local.yml exec -T django npm run test:js
docker compose -f local.yml exec -T django npm run lint:js
docker compose -f local.yml exec -T django npm run build
```

Enable the dedicated ephemeral broker for real-worker integration tests:

```bash
docker compose -f local.yml --profile integration-test up -d celery-test-redis
docker compose -f local.yml exec -T django python compose/run_live_worker_tests.py -q
```

`TEST_CELERY_BROKER_URL=redis://localhost:6381/0` identifies that broker to
host-networked integration test processes. Ordinary tests use in-memory
transport. Never point real-worker tests at the development broker. Redis
Pub/Sub spans logical databases, so a different database number is insufficient
isolation. Use an isolated PostgreSQL test database, test storage bucket, and
test GitLab resources alongside that broker. External worker connections cannot
share an in-memory SQLite test database or an uncommitted test transaction.

The runner builds the PostgreSQL connection URL from the container's existing
`POSTGRES_*` variables without printing credentials. Pytest creates its isolated
`test_` database; the worker receives that exact database address through
`TEST_DATABASE_URL`. The suite refuses the development broker, a non-test
database, a nonlocal storage endpoint, and any bucket other than
`speleodb-user-artifacts-test`. Run it without parallel test processes. The test
bucket must already exist with the local test credentials from `.envs/test.env`.

These tests start and stop their own Celery subprocess. They exercise real
request dispatch, an empty-account archive, a signed S3 download, notification
delivery state, expiry deletion, same-UUID duplicate delivery, and durable
request recovery after a real broker connection refusal. They also kill their
own actual worker process and verify bounded recovery into a new attempt without
a stale artifact. No Kanchi process observes the isolated test broker. The
worker's log is retained in pytest's temporary directory for failures.

The Compose tests exercise actual shell argument forwarding, broker
preservation, migration failure propagation, default-service dependencies, and
network/storage isolation. Runtime verification also checks migrations, task
ingestion, restart durability, authentication, and export completion while
Kanchi is down.

The CI pytest job supplies both Django's `DATABASE_URL` and the provisioner's
`POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, and
`POSTGRES_PASSWORD`, all targeting the same disposable PostgreSQL service.
Service-container environment variables are not inherited by runner processes.
The Kanchi tests use this administrator connection to create uniquely named
databases and restricted roles, then remove their own resources after each test.
Keep that explicit connection contract so CI exercises real provisioning.

The reloader subprocess loads `config.settings.local`, which requires an
explicit `DJANGO_SECRET_KEY`; the default in test settings is not an environment
variable. Its test supplies a dummy key and disables private dotenv loading.
When verifying CI environment changes, run the Compose tests from a checkout
without `.env` or `.envs/test.env`, using the workflow's environment. This
catches missing inputs that local credentials can hide. These settings affect
test setup only and add no application runtime work.

After consolidation and the archive-layout correction, container verification
passed 4,259 Python tests with 108 subtests (162 skipped). The final UI/API and
reloader updates passed 1,003 JavaScript tests and 54 focused backend checks.
All pre-commit hooks passed. Four isolated live-worker tests also passed,
including actual worker death and recovery. The PostgreSQL bootstrap passed 11
tests. Kanchi migration preserved all 21 tables and 321 rows; shared Redis data
survived a restart. Scaling to two worker replicas verified distinct node names
and both queues on each replica, then returned to one worker. A real local
export completed on the consolidated worker with a verified signed download;
generation and maintenance recorded the same worker identity.

A real archive containing a 4,294,967,313-byte member passed ZIP64 creation, S3
upload, download, and full SHA256 verification; peak process memory was
approximately 405 MiB. A local export also completed with Kanchi stopped. Those
large-archive and observer outage checks preceded consolidation. Production
email and the production expiry cycle remain rollout checks.

## Local development reloads

For local development, generated repositories and scratch files under `.workdir`
must not restart Django while exports or tests run. The local settings select
Werkzeug's stat reloader and exclude `.workdir` paths; normal application code
changes still reload. This also avoids watchdog/inotify directory-removal races
on Docker bind mounts. Do not restart/recreate Django to load worker changes;
reload only the Celery worker after its checks pass.

## Kanchi operating contract

Use one Kanchi instance and an immutable image digest. Give it a separate
database and restricted user on the existing PostgreSQL server. Its history is
independent of Django's Celery result records; both databases share server
capacity and availability. Verify the pinned image's own migrations during
upgrades.

After first startup, sign in and set task-history retention to 30 days with
daily automatic cleanup. Confirm the saved retention configuration survives a
restart. Do not invent environment switches for settings the pinned version only
exposes in its dashboard/API.

The persisted settings are `data_retention.task_successful_days=30`,
`data_retention.task_unsuccessful_days=30`, and the `data_retention.schedule`
settings `preset=daily`, `hour=3`, `minute=0`, `timezone=UTC`, and
`enabled=true`. The pinned release stores them through `AppConfigService`;
authenticated API updates use `PUT /api/config/settings/{key}`. Verify them
through the service or `GET /api/config` after saving. Configure the schedule
before enabling it.

Leave workflow automation rules disabled. Django admin is the supported export
retry interface; raw task replays from Kanchi do not create new application
attempts. Existing task-ID/attempt guards must make stale replays harmless.
Kanchi reports an operational view based on observed events. Application job
state remains authoritative when events are missed or the observer is offline.

Production requires password-hash authentication, independent random session and
token secrets, explicit allowed hosts/origins, and a username allowlist. Kanchi
access is limited initially to trusted superuser operators; it does not inherit
Django's permissions. Include `healthcheck.railway.app` in production allowed
hosts so Railway can probe `/api/health`, and set `PORT=8765`.

An HTTP health response is insufficient proof of task monitoring. Check broker
connection logs, worker heartbeats, and an actual application's task in the UI.

## Railway deployment

Use the Railway skill to inspect the actual production project/environment
before mutation. `.railway/railway.ts` is the sole Railway service configuration
for this repository. The deprecated `railway.toml` was removed to avoid
competing deployment settings. Preserve the existing named partial and its
current web service; do not recreate legacy TOML/JSON service configuration or
take ownership of unrelated services by importing/applying an incomplete
whole-project graph. `railpack.json` separately owns image construction,
including dependencies and frontend assets. Service configuration changes
require a reviewed `railway config plan` and `railway config apply`; application
Git pushes alone do not apply IaC edits. Consolidating these settings has no
application runtime or performance effect.

The root Node manifest and lockfile pin `railway@3.11.0`, TypeScript, and Node
type definitions. `npm run typecheck:railway` validates the authoring file and
runs through pre-commit/CI. Its native IaC runner requires Railway CLI 5.42.1 or
newer; the read-only production plan was checked with CLI 5.57.1. The web
service, worker, and Beat track the repository's `master` release branch with
GitHub check suites enabled. Worker and Beat sources have no fixed commit SHA,
and their empty watch-pattern lists allow every repository change to trigger a
rebuild after checks pass. This keeps application tasks aligned with releases
that update shared code, dependencies, or build configuration. Kanchi follows
its pinned image digest and upgrades independently of application Git pushes.
Check the live web service's source branch and migration history before applying
the prepared graph, and record the actual commit on each resulting deployment.
After service creation, read back the worker and Beat source settings to confirm
the `master` branch, absent commit pin, and enabled GitHub check suites were
retained.

Railway may normalize omitted fields to default restart-policy or watch-pattern
values on read-back. Compare any `null`-to-default plan differences with the
effective deployment manifest before applying again; correct runtime settings do
not require repeated deployments to chase representational differences.

The authorized rollout creates `Celery-Worker`, `Celery-Beat`, and `Kanchi` and
updates the web service's broker, dashboard link, and deployment
commands/settings. Generate a fresh plan before applying and reject unrelated
changes or removals. A plan does not provision services or validate missing
referenced values; verify those prerequisites against the target production
environment.

Before rollout, verify the existing Redis server has a persistent volume, AOF,
and `noeviction`. Provision a separate Kanchi database and restricted login on
the existing PostgreSQL server. Neither existing infrastructure service is
managed or replaced by this named IaC partial. Verify these prerequisites in
production; local setup does not provision production resources.

This topology needs no environment-wide shared variables. Redis owns its
connection settings, PostgreSQL owns its private hostname, and Kanchi owns its
dedicated database password and authentication secrets. Consumers use Railway
references so credential/address changes have one source of truth and Railway
can display service dependencies. Never copy a resolved infrastructure URL into
shared storage or a consumer's variables.

Set `CELERY_BROKER_URL=${{REDIS_URL}}/1` on `Redis-Prod`. Its existing
`REDIS_URL` already references Redis's own password and private domain and has
no database suffix. Web, worker, Beat, and Kanchi each set
`CELERY_BROKER_URL=${{Redis-Prod.CELERY_BROKER_URL}}`. This selects logical
database 1; the web cache continues using database 0. The Redis-owned variable
is a prerequisite managed on that existing service, outside this IaC partial.

When replacing copied values, inspect both raw reference expressions and
rendered connection URLs. Compare resolved values without printing secrets, then
verify a broker `PING` and database connection from a deployed consumer. Remove
the obsolete shared value only after checking every service for remaining
references. An equivalent reference-only correction does not require a restart.

Configure these native environment variables directly on the Kanchi service:

- `DATABASE_PASSWORD`, holding only Kanchi's dedicated database login password.
- `DATABASE_URL`:
  `postgresql+psycopg://kanchi:${{DATABASE_PASSWORD}}@${{Postgres-Prod.PGPRIVATEHOST}}:5432/kanchi`.
  The dedicated database/user remain separate from Django. `PGPRIVATEHOST`
  references PostgreSQL's private domain; its existing `PGHOST` and `PGPORT`
  describe the public proxy and must not be used for this private connection.
- `BASIC_AUTH_USERNAME` and `BASIC_AUTH_PASSWORD_HASH` (Django-compatible
  `pbkdf2_sha256` format). The username does not need to be an email address.
- Independent random `SESSION_SECRET_KEY` and `TOKEN_SECRET_KEY` values.
- `ALLOWED_EMAIL_PATTERNS`, referencing the same service's
  `${{BASIC_AUTH_USERNAME}}` variable to allow only that operator username.
- `ALLOWED_HOSTS`: `${{RAILWAY_PUBLIC_DOMAIN}},healthcheck.railway.app`.
- `ALLOWED_ORIGINS`: `https://${{RAILWAY_PUBLIC_DOMAIN}}`.

Set `KANCHI_URL=https://${{Kanchi.RAILWAY_PUBLIC_DOMAIN}}/ui/` on
`SpeleoDB-Prod`, which displays the dashboard link. Kanchi's public domain must
resolve to the configured custom hostname, `kanchi.speleodb.org`. Kanchi's
credentials, authentication settings, and hostname configuration have one
consumer, so they remain on Kanchi instead of shared environment scope. The IaC
file uses `preserve()` for its sensitive service-local values. When moving an
existing value, verify the destination before removing its shared copy, and
preserve any pending operator changes.

The IaC file references the existing web service's runtime variables for Django
worker and Beat. Inventory those variable names before applying; optional
deployment overrides such as a custom sender address or Sentry configuration
must be carried over explicitly when present. Existing web variables use
`preserve()` because declaring an IaC environment map owns the complete map.
Refresh that inventory before each plan so newly added settings cannot be
deleted. Web, worker, Beat, and Kanchi reference the same Redis-owned broker
URL. The application background services explicitly use
`https://www.speleodb.org` for notification links.

Deploy these continuously running services in `us-east4-eqdc4a`, alongside the
existing web service:

- `Celery-Worker`: one replica initially, consuming both queues with concurrency
  one; begin with 2 vCPU/4 GiB limits. Scale this service's replicas to add
  capacity; do not create separate services for task categories.
- Beat: one replica with the application advisory lock.
- Kanchi: one pinned-image replica and an authenticated HTTPS endpoint.

Provision secrets through Railway variables or references, never tracked source.
Workers need the existing Django runtime settings, including the shared database
and storage credentials. Kanchi receives only its own database and broker
credentials plus its authentication configuration. Keep export scratch files
ephemeral and validate available space against representative archives.

Deployment order:

1. Finish container tests, review, commit, and CI; record the release commit.
2. Inventory existing service configuration and preview the IaC plan. Reject
   unrelated deletions or secret replacements. Reconcile legacy web-config
   ownership before applying an IaC file that manages that service.
3. Validate durability and eviction settings on shared Redis; provision only the
   Kanchi database/user on existing PostgreSQL, then set the Redis-owned broker
   and service-local variables described above.
4. Verify storage configuration and signed/anonymous download behavior. Deploy
   additive application migrations, then install the intended periodic
   schedules.
5. Deploy the shared worker, Beat, and Kanchi. Confirm all application services
   use the intended commit and Kanchi uses the intended image digest.
6. Check each exact deployment ID reaches `SUCCESS`, then verify queue
   consumption from both queues, distinct replica node names, singleton Beat,
   authentication, and actual Kanchi task ingestion.
7. Verify complete and partial archives from an ordinary account, historical Git
   restoration, email, authenticated download, recovery, large-archive memory
   and disk usage, and a real 24-hour expiry/deletion cycle.

Set a 120-second deployment termination grace and verify forced interruption
recovery. Audit existing Beat schedules before enabling the scheduler; enabling
this feature must not silently start obsolete application tasks. Confirm worker
saturation only delays notification and physical cleanup; the download expiry
guard must continue rejecting expired artifacts immediately.

For rollback, return application services to a compatible release while
preserving additive tables and history. Keep artifact cleanup and published
downloads available where supported by that release. Roll back Kanchi
independently.

### Production rollout verification

The infrastructure rollout completed on September 15, 2026. The worker, Beat,
web, and pinned Kanchi deployments all reached `SUCCESS`. One worker consumes
both queues, one PostgreSQL advisory-lock owner runs Beat, and scheduled
maintenance/cleanup dispatch is visible. Read-only application tasks completed
in Django and appeared as successful in Kanchi; normal web task dispatch also
completed. Kanchi's 30-day retention and daily cleanup are stored, its first
automatic cleanup succeeded, and workflow automation remains disabled.

HTTPS web/health/login-page availability and rejection of anonymous config API
requests were verified. A successful session using the operator's sealed
password was not tested. Real-account export, notification email, authenticated
download, and the full expiry/deletion cycle remain separate future operator
smoke checks. Exact deployment IDs and runtime evidence are recorded in
[the rollout review](../tasks/todos/railway-background-rollout.md).

## Sources

- [Kanchi installation](https://kanchi.io/docs/getting-started/installation)
- [Kanchi authentication](https://kanchi.io/docs/configuration/authentication)
- [Kanchi workflow automation](https://kanchi.io/docs/core/workflow-automation)
- [Redis Pub/Sub database scoping](https://redis.io/docs/latest/develop/pubsub/)
- [Railway Infrastructure as Code](https://docs.railway.com/infrastructure-as-code)
- [Railway health checks](https://docs.railway.com/deployments/healthchecks)
