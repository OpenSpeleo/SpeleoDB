# Background jobs: local services and Railway operations

## Ownership and scheduling

SpeleoDB stores user requests, attempts, artifact availability, and notification
state in its application database. The existing `django-celery-results`
`django-db` backend stores technical task execution records in that same
PostgreSQL database and exposes them through Django admin. No separate
monitoring service or database is required. Cache and Celery share the existing
Redis server, using logical databases 0 and 1 respectively. This reuses the
application's infrastructure and keeps worker scaling straightforward.

**There is no Railway cron job or Railway cron schedule.** A continuously
running Celery Beat process uses `django-celery-beat`'s database scheduler. One
Celery worker service consumes both archive generation and scheduled
maintenance.

| Process   | Command                            | Queue                        |
| --------- | ---------------------------------- | ---------------------------- |
| Worker    | `bash compose/celery/worker/start` | `exports,background_control` |
| Scheduler | `bash compose/celery/beat/start`   | Publishes scheduled tasks    |

Each worker replica starts with `--queues exports,background_control`,
concurrency one and prefetch one. Task-event publication is disabled; result
recording does not depend on events. Scale the same worker service through
replicas as demand grows. Maintenance and email tasks can wait behind exports
when every replica is occupied. The authenticated download endpoint enforces
artifact expiry independently of cleanup scheduling; expired downloads become
unavailable even when physical deletion is still queued.

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
30-day result-retention policy. The scheduler sets the message `ignore_result`
option from the same lightweight housekeeping policy as the worker, without
importing task implementations. Actual tasks keep results, including work
published by Beat. No database schema change is needed.

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
The worker keeps prefork, concurrency one, prefetch one, both queues, and the
existing task deadlines and recovery behavior. It no longer starts with
`--events`; normal worker control and heartbeats remain available.

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

Historical verification of the earlier October 2026 runtime optimization passed
the full local SQLite Python suite with 5,227 tests passed and 208 skipped, plus
2,326 frontend tests. These results predate the monitoring removal and
task-result policy changes; they are not validation of this release. The
production asset build, development TypeScript/IaC check, Django system check,
changed-file Ruff/format checks, and whole-project mypy check (790 Python files)
passed. The full-suite GitLab audit recorded nine creations, ten creation
requests, zero violations and no unresolved outcomes. All nine created
repositories were confirmed marked for deletion by GitLab; asynchronous deletion
is not reported as immediate physical removal.

That earlier verification also passed all 74 focused checks in a separate
PostgreSQL/isolated-Redis run, including real lock handover, all eight
prefork-worker tests, archive/download/notification and expiry flows,
Beat-published result recording, soft-timeout recovery, hard timeout child
replacement, and worker-death recovery. This run created no GitLab repositories
and recorded no audit violations. Its temporary Redis server was stopped after
verification; the shared development Redis remained available.

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
the task in Django admin under **Celery Results → Task results**. This
maintenance task does not create an export-request row in the Background jobs
list.

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

Selecting only `django-webserver` does not start the worker and scheduler. The
devcontainer uses the same service graph and exposes Django port 8000. Task
history is available through the application's authenticated Django admin.

| Service             | Reachable from host     | Persistent storage                                           |
| ------------------- | ----------------------- | ------------------------------------------------------------ |
| Existing PostgreSQL | `localhost:5432`        | Existing data/backups volumes, including Django task results |
| Shared Redis        | `localhost:6379`        | `speleodb_local_redis_data`; cache DB0, Celery DB1           |
| Django              | `http://localhost:8000` | Application records and task history in PostgreSQL           |

Shared Redis uses a persistent volume, AOF persistence, and `noeviction` so
cache pressure cannot evict queued tasks. The databases share process memory and
availability; monitor total memory and rejected writes on this server. The
host-networked Django services use `redis://localhost:6379/1` for Celery while
the cache URL remains `redis://localhost:6379/0`. The monorepo Compose override
uses `redis://redis:6379/1` and Compose networking. Logical databases separate
keys, not credentials or Redis Pub/Sub channels.

The worker and Beat wait for successful setup and Redis health. Setup retains
local GitLab/storage provisioning, application migrations, periodic schedule
installation, and the local superuser. It stops on failure. Running
`python manage.py migrate` installs the existing `django_celery_results` tables
on a fresh database; no new application migration or dependency is needed for
the task-history interface.

### Local configuration

Existing developer environment files remain intact. Recreate affected containers
after changing their environment when authorized; a restart does not replace a
container's environment.

Updating Compose configuration does not stop an already-running orphan
container. Identify its exact Compose project and ownership before explicitly
stopping or removing it. Preserve shared volumes, databases, roles, and private
credentials; removing stored data requires separate authorization after checking
that no other service uses it. Setup does not drop existing databases or task
history.

The private root `.env` owns `GITLAB_GROUP_NAME`. Compose passes that same value
to setup and all application services, with `speleodb` as the fresh-install
default. Keep an existing namespace such as `speleodb_surveys_dev` when that is
where the repositories live; a copied application database alone does not move
GitLab repositories. The tracked Django env file must not shadow this choice.
Bootstrap refreshes the token for the chosen group without moving repositories.

`CELERY_BROKER_URL` belongs to the caller/Compose configuration. The Django
entrypoint must not replace it with the cache `REDIS_URL`. If using an external
local broker, set `CELERY_BROKER_URL` to the appropriate address for the
application network namespace.

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
a stale artifact. The worker's log is retained in pytest's temporary directory
for failures.

The Compose tests launch the actual worker script and inspect its queues,
prefork concurrency, prefetch, unique node names, and native thread limits. An
invalid Django setting exercises a real failed startup check. The entrypoint
connects to pytest's PostgreSQL database and preserves the supplied broker URL.
Setup command order and fail-fast shell options are checked statically; these
checks do not execute provisioning or prove a migration failure at runtime.
Other Compose assertions cover default-service dependencies and network/storage
isolation, the expected service graph, and preserved shared PostgreSQL volumes.
Runtime verification also checks migrations, task results, restart durability,
authentication, and export completion through the application alone.

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

The CI pytest job supplies Django's `DATABASE_URL` and `POSTGRES_HOST`,
`POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, and `POSTGRES_PASSWORD`, all
targeting the same disposable PostgreSQL service. Service-container environment
variables are not inherited by runner processes. Keep explicit connection
settings for real entrypoint and isolated-worker tests.

The reloader subprocess loads `config.settings.local`, which requires an
explicit `DJANGO_SECRET_KEY`; the default in test settings is not an environment
variable. Its test supplies a dummy key and disables private dotenv loading.
When verifying CI environment changes, run the Compose tests from a checkout
without `.env` or `.envs/test.env`, using the workflow's environment. This
catches missing inputs that local credentials can hide. These settings affect
test setup only and add no application runtime work.

Earlier archive verification exercised a real ZIP containing a
4,294,967,313-byte member through creation, S3 upload, download, and full SHA256
verification, with approximately 405 MiB peak process memory. That historical
measurement does not establish the footprint of every workload or the health of
a new deployment. Production email and a real expiry cycle remain release
verification requirements.

## Local development reloads

For local development, generated repositories and scratch files under `.workdir`
must not restart Django while exports or tests run. The local settings select
Werkzeug's stat reloader and exclude `.workdir` paths; normal application code
changes still reload. This also avoids watchdog/inotify directory-removal races
on Docker bind mounts. Bind-mounted Python changes require restarting the
affected Celery worker or Beat after its checks pass; neither process reloads
that code automatically. Do not restart/recreate Django to load those changes.

The Docker image copies the worker and Beat launchers to `/start-celeryworker`
and `/start-celerybeat`. Changes to `compose/celery/worker/start` or
`compose/celery/beat/start` require an image rebuild through the normal approved
Compose/devcontainer lifecycle. Restarting an existing container retains its old
copied launcher. After rebuilding, verify that the worker is ready and its
startup banner reports task events **OFF**.

## Task history and scheduler health

Open **Celery Results → Task results** in Django admin to inspect task IDs,
names, status, start/update timestamps, workers, arguments, result payloads,
tracebacks, and the periodic task name when present. Group results retain their
existing diagnostic view. Both interfaces are read-only, including for
superusers: no manual create, status edit, delete, or arbitrary replay action is
available. Django's authenticated staff permissions protect this operational
data; do not put credentials or unnecessary personal data in task arguments or
return values. Application jobs and attempts link to their technical records.
The task list labels `date_done` as **Last updated** because Celery also updates
it during STARTED and RETRY; it is not exclusively a completion timestamp.

`CELERY_RESULT_BACKEND="django-db"`, `CELERY_RESULT_EXTENDED=True`, and STARTED
tracking retain useful execution metadata. Task state transitions update one row
per Celery task ID; this is a latest-state record, not a separate event row for
every transition. Task ID guards still protect export claims against duplicate
delivery. Export STARTED is written only after acquiring the application attempt
claim, so a stale delivery cannot replace a completed task's result. Ordinary
task execution failures remain visible with their tracebacks.

The shared `config.task_results` policy excludes routine successful runs and
STARTED records for exactly these housekeeping tasks:

| Task                                                      | Managed interval | Purpose                                               |
| --------------------------------------------------------- | ---------------- | ----------------------------------------------------- |
| `speleodb.gis.tasks.dispatch_project_geojsons`            | 60 seconds       | Dispatch durable pending generation work              |
| `speleodb.background_jobs.tasks.maintain_background_jobs` | 60 seconds       | Recover attempts and send due notifications           |
| `speleodb.background_jobs.tasks.delete_expired_artifacts` | 300 seconds      | Delete expired artifacts and eligible old job history |
| `celery.backend_cleanup`                                  | 86,400 seconds   | Expire old technical result records                   |

Workers use `ignore_result=True` and `store_errors_even_if_ignored=True` for
these task names. Beat applies the same policy when publishing, because Celery's
message option can override the worker's default. Unhandled housekeeping
failures are retained. Actual export generation, notification delivery, survey
GeoJSON generation, and explicit rebuilds keep results regardless of whether a
request, another task, or Beat publishes them. Suppression is based on the
task's purpose, not its publisher. Existing records are not hidden or deleted by
the policy change.

**A technical `SUCCESS` means the task returned normally.** It does not prove
that an archive is complete, email was delivered, or a GeoJSON artifact was
published. These tasks may catch a recoverable error, store it in a durable job
or generation record, and arrange a bounded retry before returning. Consult
Background jobs / Job attempts, notification fields, cleanup counters, and
GeoJSON generation administration for the business outcome. Use their authorized
retry/resend/rebuild actions; changing or replaying technical result records
bypasses domain ownership and is not a recovery procedure.

Results expire after 30 days. `install_background_schedules` owns the daily
`celery.backend_cleanup` entry on `background_control`; an available Beat and
worker must execute it for expiry to remove rows. Cleanup is not a migration or
an immediate purge of historical rows. Retained unsuccessful housekeeping
results follow the same expiry. Application export history has its separate
90-day policy and preserves records needed for pending cleanup.

Check Beat logs, process health, advisory-lock ownership, and the Periodic tasks
admin to diagnose scheduling. `last_run_at` and `total_run_count` indicate
scheduler dispatch, not successful worker execution. Successful housekeeping
runs deliberately have no result row. Check worker logs, queue consumption,
pending-work age, application progress and error records, and retained task
failures together. A missing result is not proof that a scheduled task did not
run, and a recent Beat counter is not proof that it succeeded.

Removing event consumers and task-event publication avoids maintaining another
indexed history database. Updating one result row per actual execution and
omitting frequent successful sweeps bounds routine writes; result retention
still needs monitoring. Neither change caps PostgreSQL RAM or changes its
resource limits. Existing worker heartbeats and control commands remain
available without the removed task event stream.

Regression coverage uses real Celery publication/execution and the existing
Django backend: actual tasks record STARTED/SUCCESS, retries and failures;
housekeeping records failures while omitting successful rows; Beat's minimal
runtime applies the same message policy without importing application tasks.
Admin tests check diagnostic metadata, permissions and rejected mutations;
retention tests remove expired results while preserving recent rows. These
checks complement the existing domain retry, artifact and worker-loss tests.

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
configuration. Check the live web service's source branch and migration history
before applying the prepared graph, and record the actual commit on each
resulting deployment. After service creation, read back the worker and Beat
source settings to confirm the `master` branch, absent commit pin, and enabled
GitHub check suites were retained.

Railway may normalize omitted fields to default restart-policy or watch-pattern
values on read-back. Compare any `null`-to-default plan differences with the
effective deployment manifest before applying again; correct runtime settings do
not require repeated deployments to chase representational differences.

The named partial manages the existing `SpeleoDB-Prod`, `Celery-Worker`, and
`Celery-Beat` services. Generate a fresh plan against `speleoDB` / `production`
before applying. Reject unrelated changes or removals. A plan does not provision
missing referenced values; verify prerequisites in the target environment.

Before rollout, verify the existing Redis server has a persistent volume, AOF,
and `noeviction`. Neither Redis nor PostgreSQL is managed or replaced by this
named IaC partial. The application database stores the result backend; do not
provision a separate monitoring database. This change does not alter PostgreSQL
memory settings, resource limits, roles, or stored application data.

This topology needs no environment-wide shared variables. Redis owns its
connection settings. Consumers use Railway references so credential/address
changes have one source of truth and Railway can display service dependencies.
Never copy a resolved infrastructure URL into shared storage or a consumer's
variables.

Set `CELERY_BROKER_URL=${{REDIS_URL}}/1` on `Redis-Prod`. Its existing
`REDIS_URL` already references Redis's own password and private domain and has
no database suffix. Web, worker, and Beat each set
`CELERY_BROKER_URL=${{Redis-Prod.CELERY_BROKER_URL}}`. This selects logical
database 1; the web cache continues using database 0. The Redis-owned variable
is a prerequisite managed on that existing service, outside this IaC partial.

When replacing copied values, inspect both raw reference expressions and
rendered connection URLs. Compare resolved values without printing secrets, then
verify a broker `PING` and database connection from a deployed consumer. Remove
the obsolete shared value only after checking every service for remaining
references. An equivalent reference-only correction does not require a restart.

The IaC file references the existing web service's runtime variables for Django
worker and Beat. Inventory those variable names before applying; optional
deployment overrides such as a custom sender address or Sentry configuration
must be carried over explicitly when present. Existing web variables use
`preserve()` because declaring an IaC environment map owns the complete map.
Refresh that inventory before each plan so newly added settings cannot be
deleted. Web, worker, and Beat reference the same Redis-owned broker URL. The
application background services explicitly use `https://www.speleodb.org` for
notification links.

Deploy these continuously running services in `us-east4-eqdc4a`, alongside the
existing web service:

- `Celery-Worker`: one replica initially, consuming both queues with concurrency
  one; begin with 2 vCPU/4 GiB limits. Scale this service's replicas to add
  capacity; do not create separate services for task categories.
- Beat: one replica with the application advisory lock.

Provision secrets through Railway variables or references, never tracked source.
Workers need the existing Django runtime settings, including the shared database
and storage credentials. Keep export scratch files ephemeral and validate
available space against representative archives.

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
3. Validate durability and eviction settings on shared Redis and verify the
   existing Redis-owned broker references. Preserve shared infrastructure and
   databases; task history uses the application database.
4. Verify storage configuration and signed/anonymous download behavior. Deploy
   additive application migrations, then install the intended periodic
   schedules.
5. Deploy web, the shared worker, and Beat together so publisher and worker
   result policies agree. Confirm all three use the intended commit; messages
   already queued by an older publisher may retain their old result policy.
6. Check each exact deployment ID reaches `SUCCESS`, then verify queue
   consumption from both queues, distinct replica node names, singleton Beat,
   authenticated read-only result administration, and actual task results. Check
   a successful housekeeping run produces no new row and an unhandled failure
   remains visible; Beat counters alone cannot establish execution.
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
downloads available where supported by that release. Review an older IaC file's
service graph before applying it.

The result-policy change adds no database migrations. Roll back the application
publishers, worker and Beat together, preserving the advisory-lock identifier
and schedule records. The canonical Beat launcher remains the lightweight Python
module, not the retired management command. Coordinate a rollback's reviewed
source revision and matching start command in the same deployment; neither
revision may start with a command it does not support. Revert Railway
configuration through a reviewed IaC plan/apply when a rollback requires a
different start command or overlap policy.

### Production rollout verification

Configuration apply does not deploy updated Python code. Read back the managed
service variables after configuration apply, and verify the exact new
application deployments and their real task results before claiming the release
is live. A Git push alone does not apply IaC changes.

Earlier runtime work verified Beat's zero-overlap settings and canonical worker
and Beat launch commands. Preserve the 120-second shutdown grace and advisory
lock. Recheck each deployment's process, queue consumption, scheduler ownership,
result policy and application behavior for this release; historical successful
deployments are not a current production health check. Review unrelated live
configuration drift independently instead of silently applying it with the
release.

## Sources

- [Celery task result policy](https://docs.celeryq.dev/en/stable/userguide/tasks.html#Task.store_errors_even_if_ignored)
- [django-celery-results](https://django-celery-results.readthedocs.io/)
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
