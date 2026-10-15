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

| Process   | Command                            | Queue                        |
| --------- | ---------------------------------- | ---------------------------- |
| Worker    | `bash compose/celery/worker/start` | `exports,background_control` |
| Scheduler | `bash compose/celery/beat/start`   | Publishes scheduled tasks    |

Each worker replica starts with `--queues exports,background_control`,
concurrency one, prefetch one, and task events enabled. Scale the same worker
service through replicas as demand grows. Maintenance and email tasks can wait
behind exports when every replica is occupied. The authenticated download
endpoint enforces artifact expiry independently of cleanup scheduling; expired
downloads become unavailable even when physical deletion is still queued.

Beat holds a PostgreSQL advisory lock for its lifetime, including during
deployment handover. Only `install_background_schedules` owns the feature's
periodic task installation. Run it after migrations. Celery result cleanup must
also route to `background_control`.

### Beat runtime and ownership

The start script execs `python -m speleodb.background_jobs.beat`. This launcher
forces `config.settings.beat`, even when the service inherits production Django
settings. Its only installed Django application is `django_celery_beat`. Shared
environment, database, timezone, broker, routing, serialization, and retry
settings live in lightweight configuration modules. Beat does not import the web
application's settings, models, admin, task implementations, scientific or media
libraries, or result-backend models. It publishes registered task names and
arguments from the schedule database; workers execute them.

One process and one OS thread perform lock acquisition, scheduling, and
publication synchronously. There is no supervisor process, heartbeat thread,
watchdog, or threaded database pool. Beat uses standard Django/Celery logging
and does not initialize Sentry or its background threads. Monitor its
Railway/container logs and process exits. Start Beat through
`compose/celery/beat/start` or its underlying Python module. There is no Django
management-command entrypoint: initializing the full application before Beat
would defeat the small startup-memory contract.

`SchedulerLease` owns a dedicated raw psycopg connection and the existing
PostgreSQL advisory lock `736735226`. Django's scheduler connections remain
separate, so connection cleanup cannot release ownership. Acquisition allows six
attempts with 5/10/20/40/80-second waits. Connection and statement timeouts are
five seconds; TCP keepalives and the TCP user timeout bound detection of a dead
lock connection. The lock session never reconnects or reacquires ownership.

The scheduler checks ownership before and after each tick, before publication,
during broker-connection backoff, and in Kombu's publication/declaration retry
and connection-revival callbacks. A failed check marks the lease permanently
lost. The outer tick rechecks ownership because Celery normally logs and catches
publication exceptions. Detecting lost ownership therefore stops this scheduler
with failure instead of allowing it to continue after a broker recovery. These
checks add small synchronous database queries, without scanning application data
or creating background work.

These checks do not form an atomic fence across the separate lease, Django ORM,
and broker connections. SQL writes or messages already in flight can complete
after the lock is lost, including after a replacement acquires it. The scheduler
starts no further work once it detects that loss, but duplicate delivery remains
possible; tasks must retain their idempotency and duplicate-handling
protections.

SIGTERM and SIGINT interrupt lock waits and scheduler execution. The scheduler
service performs its normal final synchronization while ownership is held; the
launcher then closes the lock connection. The signal handler never creates a
scheduler while another scheduler is still being initialized. Repeated close
calls, the banner's lazy scheduler, and exit finalizers skip persistence when
the scheduler is closed or ownership loss is detected. The same in-flight
operation limit applies during shutdown.

Beat's local result backend and automatic result-expiry schedule installation
are disabled. The stored `celery.backend_cleanup` schedule remains owned by
`install_background_schedules`, and workers retain result recording and the
30-day result-retention policy. Message `ignore_result` behavior is unchanged.
No task names, queues, database tables, or public APIs change with this runtime.

### Worker runtime and execution-slot memory

The worker start script first runs `python manage.py check` in a short-lived
process using the full application profile. A failed check prevents worker
startup. After success it exports `SPELEODB_CELERY_WORKER_RUNTIME=true` and
execs Celery with `--skip-checks`. This retains startup validation without
keeping the checks' URL/API import graph resident in the worker parent.

The worker profile uses Django's `SimpleAdminConfig` to avoid admin
autodiscovery, and excludes web-only debug toolbar, Silk, extensions, and
development instrumentation. Application models, signals, tasks, templates,
storage, email, result recording, and production observability remain available.
The worker keeps prefork, concurrency one, prefetch one, both queues, events,
and the existing task deadlines and recovery behavior.

Before either Python process starts, the script defaults `OPENBLAS_NUM_THREADS`,
`OMP_NUM_THREADS`, `MKL_NUM_THREADS`, `NUMEXPR_NUM_THREADS`,
`VECLIB_MAXIMUM_THREADS`, and `BLIS_NUM_THREADS` to one. An explicitly
configured value overrides that library's default. These limits avoid
multiplying native numerical-library threads and their memory per execution
slot. They do not change Celery's pool or impose a one-thread limit on all
worker internals. Benchmark representative conversion/export workloads before
increasing them. No arbitrary worker recycling threshold hides retained
application memory.

### Memory measurements

The October 2026 investigation found that the old Beat launcher kept two full
Django runtimes resident: its lock supervisor and the scheduler child. Eager
application imports loaded scientific/media libraries into both. Production
reported approximately 425 MB for Beat, with 95 and 97 threads in those two
Python processes. The minimal runtime removes both sources of overhead rather
than imposing a memory limit or periodically restarting the scheduler.

The new canonical Beat command completed a 15-minute run against a separate
PostgreSQL database and Redis queue, publishing a real five-second schedule.
Across 984 Linux process samples it had exactly one OS thread and no children:

| Beat endurance measurement   |                     Result |
| ---------------------------- | -------------------------: |
| Peak RSS, including startup  | 81,780,736 bytes (81.8 MB) |
| Peak PSS                     | 64,645,120 bytes (64.6 MB) |
| Final RSS                    |           81,780,736 bytes |
| Scheduled messages published |                        180 |
| SIGTERM exit code            |                          0 |

This meets the 100 MB **process RSS** regression budget in the local container.
It is not a production whole-service measurement: the shared application
container also hosted the test runner, and service accounting includes page
cache and container overhead. Confirm the whole Beat service stays below 100 MB
after releasing the code on Railway. Reproduce the endurance check with an
isolated migrated Beat database, a five-second `PeriodicTask` on a unique queue,
the canonical start script, and the `/proc` sampling described below; delete
only those test-owned resources afterward.

The worker comparison used the same ARM Linux application container, Python
3.14.7, dependencies, prefork concurrency one, and test settings. Baseline
configuration came from commit `6b1144c9`; the new profile skipped resident
system-check imports and admin autodiscovery and applied the native thread
defaults. Both registered the same nine application tasks. Decimal MB below
means 1,000,000 bytes. PSS apportions shared pages between processes; summing
RSS would double-count those pages.

| Worker measurement                     | Baseline MB | New MB |
| -------------------------------------- | ----------: | -----: |
| Idle parent RSS                        |       279.0 |  254.7 |
| Idle execution child RSS               |       209.2 |  184.9 |
| Idle combined PSS                      |       231.8 |  206.7 |
| After conversions: parent RSS          |       279.0 |  254.7 |
| After conversions: execution child RSS |       248.5 |  226.9 |
| After conversions: combined PSS        |       366.1 |  326.7 |

Each profile executed three real conversions of the checked-in `sample.mak`
Compass survey plus `gis_layers/us_states/us_states_5m.zip`, using
`Project.build_geojson()` and `compile_gis_layer_bytes()` in its prefork child.
Compass geometry, feature count, datum and UTM metadata matched, and the
2,197,492-byte shapefile conversion output matched byte for byte. Whole Compass
JSON includes varying generated metadata, so geometry was compared separately.
Median conversion time was 0.634 seconds before and 0.613 seconds after; three
runs establish no statistical throughput claim. Sampled combined peak PSS was
also 366.1 versus 326.7 MB, about 11% lower. Both profiles used one thread per
process in this ARM container; the production native-thread reduction still
requires deployment measurement.

These native conversion measurements exclude network export, email and storage
work; live integration tests cover those flows. They measure resident worker
processes, excluding the separate startup preflight and container page cache.
Production Sentry and workload size can change the footprint. Application code
must be released before these savings can be verified on Railway.

Container verification for this change passed the full local SQLite Python suite
with 5,227 tests passed and 208 skipped, plus 2,326 frontend tests. The
production asset build, development TypeScript/IaC check, Django system check,
changed-file Ruff/format checks, and whole-project mypy check (790 Python files)
passed. The full-suite GitLab audit recorded nine creations, ten creation
requests, zero violations and no unresolved outcomes. All nine created
repositories were confirmed marked for deletion by GitLab; asynchronous deletion
is not reported as immediate physical removal.

A separate PostgreSQL/isolated-Redis run passed all 74 focused checks, including
real lock handover, all eight prefork-worker tests,
archive/download/notification and expiry flows, Beat-published result recording,
soft-timeout recovery, hard timeout child replacement, and worker-death
recovery. This run created no GitLab repositories and recorded no audit
violations. Its temporary Redis server was stopped after verification; the
shared development Redis remained available.

These scheduler, consumer, runtime, and worker-startup checks use real framework
construction and supported configuration without mocks or monkeypatches. They
include real connection refusal/failover, Redis write timeouts, PostgreSQL
session loss, process signals, and the full 155-second lock-wait budget. A final
15-test PostgreSQL consumer run also passed after tightening fixture lifecycle
cleanup. The disabled-retry tests exposed and fixed an implicit Kombu retry that
mocked connection calls had not detected.

## One-shot GeoJSON rebuild

Superusers can open **Background jobs** in Django admin
(`/admin/background_jobs/backgroundjob/`) and use **Rebuild all GeoJSONs** in
the maintenance panel above the list. Each submission queues one full-history
rebuild and returns its Celery task ID. It creates no periodic schedule; monitor
the task in Celery results or Kanchi. This maintenance task does not create an
export-request row in the Background jobs list.

The panel uses the admin theme colors, keyboard focus styling and a stacked
layout on small screens. The endpoint requires a superuser, POST and a valid
CSRF token. See [GeoJSON rebuild operations](project-geojson-command.md) for
scope, worker readiness, time limits and regression coverage.

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

### Kanchi application versus database provisioning

**The Kanchi image contains the application; its PostgreSQL database is
external.** In this Compose configuration, `DATABASE_URL` points to
`postgres:5432/kanchi` on the same PostgreSQL server that hosts Django's
separate database. Redis is also an external service. Packaging Kanchi in its
own container does not create its database or login on that server.

| Component                                                  | Responsibility                                                                                                        |
| ---------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| Shared `postgres` service                                  | Runs PostgreSQL and persists both applications' separate databases in its existing volume.                            |
| Our `setup` service and `compose/setup_kanchi_database.py` | Create Kanchi's database and restricted login, check existing ownership, and manage its password and database access. |
| Upstream `getkanchi/kanchi` image                          | Runs Kanchi and manages its own schema/migrations inside the provisioned database.                                    |

Startup order is: PostgreSQL becomes healthy, our setup provisions the database
and role, then Kanchi starts against that database. The Django migrations run by
`compose/setup` belong to Django; they do not install Kanchi's tables. Keeping
provisioning in setup lets Kanchi use a restricted login rather than PostgreSQL
administrator credentials and supports existing development volumes without
recreating them.

New Kanchi databases explicitly clone PostgreSQL's pristine `template0` because
Kanchi migrations own the schema; local additions to `template1` must not leak
into it. This also avoids inheriting a recorded `template1` collation version
that the current container runtime cannot determine, as can happen when a
development volume moves from glibc to Alpine/musl. PostgreSQL records the new
database's current collation version during creation. See
[PostgreSQL template databases](https://www.postgresql.org/docs/16/manage-ag-templatedbs.html).
Provisioning does not repair cluster-wide collation metadata or rebuild existing
databases. Repeated setup preserves Kanchi history and only rotates its
dedicated role's password and reapplies database access restrictions. Template
selection adds no queries or ongoing runtime cost.

### What the Kanchi database tests cover

**`compose/tests/test_kanchi_database.py` tests our provisioning script, not the
Kanchi application.** It creates temporary databases and roles on real local
PostgreSQL and removes them afterward. It does not launch or call the Kanchi
container, run Kanchi migrations, or use Kanchi's existing database.

The tests verify database creation, ownership, restricted access, password
rotation, quoted identifiers, and CLI secret handling. The `kanchi_history`
table in these tests is a dummy table created by the test, not an assertion
about Kanchi's schema. It proves that repeating our setup preserves stored data.
Ownership and privilege checks prove that our setup refuses to take over an
unrelated database or reuse an unsafe role.

The collation regression checks that new database metadata matches the running
provider. Another test holds an active connection to `template1`, preventing
PostgreSQL from cloning it, and confirms that our provisioning still succeeds
using `template0`. This tests independence from the shared template without
changing its contents or metadata. Together these tests protect startup against
the provisioning failures that otherwise block Kanchi from starting.

A passing suite does **not** establish that Kanchi starts successfully, applies
its migrations, serves its UI, authenticates users, or observes Celery tasks.
The Compose `/api/health` check separately probes the running Kanchi service; it
is not an end-to-end task-monitoring test. Run the provisioning tests inside the
already-running application devcontainer:

```bash
pytest compose/tests/test_kanchi_database.py
```

### Local credentials and configuration

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

The `celery-worker` service uses the explicit container name
`${COMPOSE_INSTANCE_PREFIX:-speleodb}_local_celery_worker`, matching the other
local services and keeping its Docker Desktop display consistent. This limits
the local Compose service to one worker container; `--scale celery-worker=N`
cannot be used with multiple replicas while the fixed name is configured. Each
startup still adds a UUID to its Celery node name to avoid collisions when
workers share a hostname. The worker consumes both queues. Keep Beat at one
replica; its database lock also protects against scheduler overlap during
restarts. Naming does not change worker concurrency or task processing overhead.

Verify the resolved name with `docker compose -f local.yml config` and the live
container name with `docker ps` after applying the configuration.

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

Run Python, JavaScript, lint, type checks, and builds inside the Django
container:

```bash
docker compose -f local.yml exec -T django uv sync --frozen --extra local
docker compose -f local.yml exec -T django pytest compose/tests/
docker compose -f local.yml exec -T django bun run test:frontend
docker compose -f local.yml exec -T django bun run lint:frontend
docker compose -f local.yml exec -T django bun run build
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

PostgreSQL tests create their schema from the pristine `template0`, avoiding
developer objects and stale libc collation metadata in `template1`. SQLite test
configuration is unchanged. This does not alter either shared template or the
development database. A separate ephemeral Redis server on `redis:6381` is also
accepted for tests inside the existing container network; `redis:6379` remains
refused.

These tests start and stop their own Celery subprocess. They exercise real
request dispatch, an empty-account archive, a signed S3 download, notification
delivery state, expiry deletion, same-UUID duplicate delivery, and durable
request recovery after a real broker connection refusal. They also kill their
own actual worker process and verify bounded recovery into a new attempt without
a stale artifact. No Kanchi process observes the isolated test broker. The
worker's log is retained in pytest's temporary directory for failures.

The Compose tests launch the actual worker script and inspect its queues,
prefork concurrency, prefetch, unique node names, and native thread limits. An
invalid Django setting exercises a real failed startup check. The entrypoint
connects to pytest's PostgreSQL database and preserves the supplied broker URL.
Setup command order and fail-fast shell options are checked statically; these
checks do not execute provisioning or prove a migration failure at runtime.
Other Compose assertions cover default-service dependencies and network/storage
isolation. Runtime verification also checks migrations, task ingestion, restart
durability, authentication, and export completion while Kanchi is down.

Runtime-isolation regressions launch fresh interpreters, check the Beat import
graph, one OS thread and a 100,000,000-byte RSS high-water limit, and publish
through an in-memory broker without importing task implementations. Database
scheduler tests exercise due, disabled, and one-off entries, edited schedules,
timezone behavior, stored counters, queue routing, and unchanged managed result
cleanup. Lease tests use separate real PostgreSQL sessions for contention,
handover, and ownership loss. Signal and retry tests cover interrupted scheduler
construction, terminal failure propagation, and finalizer safety. Worker tests
cover its profile, failed preflight, explicit native-thread overrides, and
actual prefork timeouts/recovery.

Run the complete focused checks inside the already-running application
container, with the dedicated test broker available on `redis:6381`:

```bash
docker exec -e TEST_CELERY_BROKER_URL=redis://redis:6381/0 -w /app speleodb-monorepo-django python compose/run_live_worker_tests.py compose/tests/test_celery_runtime.py compose/tests/test_celery_result_backend.py compose/tests/test_runtime_settings.py compose/tests/test_background_services.py speleodb/background_jobs/tests/test_scheduler.py speleodb/background_jobs/tests/test_consumer.py -q
```

The runner configures PostgreSQL from the container credentials, enables real
worker tests, and includes the live-worker module automatically. Pytest creates
its isolated `test_` database. Bare pytest runs using SQLite skip lease tests;
they do not substitute for this integration run. Compare service memory and
per-process RSS/PSS, parent/child membership, thread count, and startup high
water in the same environment. For Linux subprocess probes, read
`/proc/<pid>/status` (`VmRSS`, `VmHWM`, `Threads`) and
`/proc/<pid>/smaps_rollup` (`Pss`). `getrusage().ru_maxrss` can retain the
launching process's high water across exec and misrepresent a fresh lightweight
runtime. Exercise at least 15 minutes of real scheduling, and sample worker
memory before, during, and after representative tasks. Keep startup-preflight
memory separate from the long-lived worker parent and its execution child.

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

The root JavaScript manifest and lockfile pin `railway@3.11.0`, TypeScript, and
the tool's type definitions. `bun run typecheck:development` validates the
authoring file and runs through pre-commit/CI. Its native IaC runner requires
Railway CLI 5.42.1 or newer; the read-only production plan was checked with CLI
5.57.1. The web service, worker, and Beat track the repository's `master`
release branch with GitHub check suites enabled. Worker and Beat sources have no
fixed commit SHA, and their empty watch-pattern lists allow every repository
change to trigger a rebuild after checks pass. This keeps application tasks
aligned with releases that update shared code, dependencies, or build
configuration. Kanchi follows its pinned image digest and upgrades independently
of application Git pushes. Check the live web service's source branch and
migration history before applying the prepared graph, and record the actual
commit on each resulting deployment. After service creation, read back the
worker and Beat source settings to confirm the `master` branch, absent commit
pin, and enabled GitHub check suites were retained.

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

Beat explicitly sets both `deploy.overlapSeconds: 0` and
`RAILWAY_DEPLOYMENT_OVERLAP_SECONDS=0`. The worker's deployment policy is
unchanged. Railway still starts the replacement before retiring the previous
deployment; zero overlap removes the extra coexistence delay after the
replacement starts. The advisory lock admits one owner while the replacement
waits for the previous owner to exit; the in-flight operation limits described
above still apply if ownership is lost. This is not a guarantee that two
container processes never briefly exist. Preserve the existing 120-second
termination grace so in-flight work can shut down cleanly. See
[Railway deployment teardown](https://docs.railway.com/deployments/deployment-teardown).

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

The lightweight runtime adds no migrations or task-message changes. Roll back
the worker and Beat code together with the start commands supported by that
revision, preserving the advisory-lock identifier and schedule records. The new
release removes the old management command. Coordinate a rollback's reviewed
source revision and matching start command in the same deployment; neither
revision may start with a command it does not support. Revert Railway
configuration through a reviewed IaC plan/apply when a rollback requires a
different start command or overlap policy.

### Production rollout verification

In October 2026, an isolated IaC plan applied only Beat's
`deploy.overlapSeconds=0` and `RAILWAY_DEPLOYMENT_OVERLAP_SECONDS=0`. Read-back
confirmed both values and an empty overlap-only plan. Beat's 120-second
termination grace and the worker's deployment policy were retained. The
lightweight application code and canonical Beat start-command change were not
deployed as part of that configuration update. Coordinate the reviewed source
revision and its matching Beat start command in the same deployment; do not
start the new release with the removed management command. Then verify the exact
deployment, whole-service memory, one Beat PID/thread, lease handover, scheduled
publication and worker results. Existing unrelated IaC drift must be reviewed
separately, especially any proposed change from Kanchi's pinned image digest to
a mutable tag.

The September 15, 2026 rollout verified successful worker, Beat, web, and pinned
Kanchi deployments. At that time one worker consumed both queues, one PostgreSQL
advisory-lock owner ran Beat, and scheduled maintenance/cleanup dispatch was
visible. Read-only application tasks completed in Django and appeared as
successful in Kanchi; normal web task dispatch also completed. Kanchi stored
30-day retention and daily cleanup, its first automatic cleanup succeeded, and
workflow automation was disabled.

HTTPS web/health/login-page availability and rejection of anonymous config API
requests were verified. This historical infrastructure check did not establish
successful operator login, retention persistence across a restart, real-account
export, notification email, authenticated download, or the full expiry/deletion
cycle. Verify those feature paths and the exact deployed revisions when
assessing a release; the historical result is not a current production health
check.

## Sources

- [Kanchi installation](https://kanchi.io/docs/getting-started/installation)
- [Kanchi authentication](https://kanchi.io/docs/configuration/authentication)
- [Kanchi workflow automation](https://kanchi.io/docs/core/workflow-automation)
- [Redis Pub/Sub database scoping](https://redis.io/docs/latest/develop/pubsub/)
- [Railway Infrastructure as Code](https://docs.railway.com/infrastructure-as-code)
- [Railway health checks](https://docs.railway.com/deployments/healthchecks)

## Survey GeoJSON generation

The managed schedules also include the per-commit GeoJSON dispatcher, running
every 60 seconds on `background_control`. It reads durable generation records
created only after successful source Git pushes and committed upload SQL
transactions. Generation uses the existing worker and read-only Git source
utility; upload requests never contact the broker. Apply the additive generation
migration and run `install_background_schedules` when enabling the new code.

Use generation administration to inspect failures or retry a recorded commit.
Monitor pending age, terminal failures, and worker timeouts; the single worker
can defer map jobs behind long maintenance/export work. See
[background survey maps](project-geojson-background.md) for limits, status API,
publication fencing, and source-versus-map recovery.
