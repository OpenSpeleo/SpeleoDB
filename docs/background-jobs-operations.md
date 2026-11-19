# Background jobs: local services and Railway operations

## Ownership and scheduling

SpeleoDB stores user requests, attempts, artifact availability, and notification
state in its application database. The existing `django-celery-results`
`django-db` backend stores technical task execution records in that same
PostgreSQL database and exposes them through Django admin. No separate
monitoring service or database is required. Cache and Celery share the existing
Redis server, using logical databases 0 and 1 respectively. This reuses the
application's infrastructure and keeps worker scaling straightforward.

`DJANGO_CELERY_USE_IMMEDIATE_BACKEND` defaults to `false`. Enable it for the
workerless staging deployment to execute submitted tasks in the requesting
process after the database commit. Production leaves it disabled and continues
publishing to its worker and Beat services. Both deployments use the same code;
the setting is an explicit execution choice, independent of environment names.

Immediate execution uses Celery's native task execution and autodiscovery,
preserves task IDs and database-backed task results, and does not connect to a
broker. Upload generation, administrator operations, exports and export emails
share this dispatch behavior. Failed executions retain failed task results even
when the source upload remains successful. The setting does not start a
scheduler: periodic maintenance and discovery of pending export notifications
still require Beat or an explicit invocation. Work runs within the web request's
time and memory budget, without worker-pool task timeouts.

**Application background tasks use Celery Beat rather than Railway cron.** A
continuously running Beat process uses `django-celery-beat`'s database
scheduler. One Celery worker service consumes both archive generation and
scheduled maintenance. The separate Git and PostgreSQL backup services use
Railway cron schedules declared in the same infrastructure configuration.

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

The lightweight runtime's operational goal is a whole Beat service footprint
below 100 MB. The process RSS regression budget is separate: a passing local
process test does not establish that production service usage meets the goal.
Service accounting also includes page cache and container overhead, so verify
the deployed service under real scheduling. This goal is not the configured
Railway memory ceiling and does not call for periodic restarts to hide growth.

`SchedulerLease` owns a dedicated raw psycopg connection and the existing
PostgreSQL advisory lock identified in `speleodb/background_jobs/lease.py`.
Django's scheduler connections remain separate, so connection cleanup cannot
release ownership. Acquisition allows six attempts with 5/10/20/40/80-second
waits. Connection and statement timeouts are five seconds; TCP keepalives and
the TCP user timeout bound detection of a dead lock connection. The lock session
never reconnects or reacquires ownership.

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
importing task implementations. Housekeeping explicitly publishes `True`;
unregistered ordinary task names publish `None`, leaving result storage to the
worker's task policy. Actual tasks keep results, including work published by
Beat.

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
existing task deadlines and recovery behavior. Task-event publication is
disabled; normal worker control and heartbeats remain available.

Before either Python process starts, the script defaults `OPENBLAS_NUM_THREADS`,
`OMP_NUM_THREADS`, `MKL_NUM_THREADS`, `NUMEXPR_NUM_THREADS`,
`VECLIB_MAXIMUM_THREADS`, and `BLIS_NUM_THREADS` to one. An explicitly
configured value overrides that library's default. These limits avoid
multiplying native numerical-library threads and their memory per execution
slot. They do not change Celery's pool or impose a one-thread limit on all
worker internals. Benchmark representative conversion/export workloads before
increasing them. No arbitrary worker recycling threshold hides retained
application memory.

## GeoJSON rebuild

Active superusers use **Background operations → Operations** to submit immediate
history resets and GeoJSON recomputations. TaskResult records executions and
GroupResult records batch membership. Publication is direct after commit, with
one task per eligible project, and force defaults to off. See
[Operations](admin-operations.md) for destructive confirmation, uncertain
publication, manual reruns and deployment verification.

## Bounded failure recovery

Export generation has three attempts per automatic cycle. Broker publication
failures and publications left unclaimed for ten minutes consume that same
budget. Notification publication and delivery share five attempts; object
cleanup has five persisted attempts per object. Retries wait 60/120/240/...
seconds, capped at one hour, without sleeping in the worker between tasks. Due
times and counts live in PostgreSQL, so periodic sweeps and process restarts
cannot reset them. `maintain_background_jobs` runs every ten minutes; due
retries and recovery therefore wait until its next pass and available worker
capacity. Normal task publication still happens directly when work is requested.
Cleanup records survive exhaustion; staff can explicitly restart cleanup in the
job admin, with an audit entry. Download expiry remains enforced even when
physical deletion fails.

See [bounded retries](bounded-retries.md) for startup, transport and durable
recovery limits. Notification tasks carry dispatch tokens; deploy matching
publishers and workers when their task arguments change.

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
on a fresh database.

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

An absent `CELERY_BROKER_URL` uses the default in `config/settings/celery.py`.
When immediate execution is disabled, an explicitly empty or whitespace-only
value stops application startup with `ImproperlyConfigured`: accepting it would
let Celery select its AMQP transport instead of Redis. Immediate execution
permits a blank broker URL because submitted tasks do not use a broker. The
shared settings enforce this without changing worker or scheduler retry
policies.

When investigating publication failures, inspect the running Celery app's
effective transport and broker destination in both web and worker processes; do
not print credentials. A successful HTTP upload response alone does not prove
that a worker consumed its background task. Check the corresponding task result
and worker logs. A publication timeout can also follow a committed source
upload, so confirm persistence before resubmitting it.

`speleodb/common/tests/test_celery_settings.py` exercises fresh WSGI startup,
rejects blank values in broker mode, verifies Redis selection for configured and
default URLs, and allows brokerless immediate execution. It constructs
connections without contacting a broker. Real conversion and export regressions
verify immediate terminal results, stored artifacts and notification delivery;
these local tests do not establish deployed configuration or live connectivity.

Local Compose runs the worker and Beat through the development source watcher. A
Python edit requests warm shutdown and waits for the old process to finish
before starting its replacement. Active worker tasks can finish before the new
code loads. Explicit container shutdown retains Compose's 120-second grace
period; production services retain their ordinary launchers without a watcher.

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

Run Python, JavaScript, lint, type checks, and builds inside the already-running
Django container. `make test-py` runs the backend suite; `make test` runs
backend, frontend and browser targets as declared in `Makefile`. Focused
commands include:

```bash
docker exec -w /app speleodb-monorepo-django pytest compose/tests/
docker exec -w /app speleodb-monorepo-django bun run test:frontend
docker exec -w /app speleodb-monorepo-django bun run lint:frontend
```

For a production asset build, stop the local webserver and its watcher first,
then run `docker exec -w /app speleodb-monorepo-django bun run build`.

Real-worker integrations run by default in `make test-py`. The normal Compose
service graph includes the dedicated ephemeral `celery-test-redis` broker and
waits for its health during setup. A focused invocation needs no enable flag:

```bash
docker exec -w /app speleodb-monorepo-django pytest speleodb/background_jobs/tests/test_live_worker.py -q
```

`TEST_CELERY_BROKER_URL` configures the service address, not whether tests run.
Standalone host-networked execution defaults to `redis://localhost:6381/0`;
monorepo Compose uses `redis://celery-test-redis:6379/0`. Ordinary tests use
in-memory transport. Real-worker children use `config.settings.test_celery` to
select the dedicated broker. Never point these tests at the development broker:
Redis Pub/Sub spans logical databases, so another database number is
insufficient isolation. A separate ephemeral server on `redis:6381` is also
accepted.

The complete backend suite uses PostgreSQL. Test settings honor the test
environment's `DATABASE_URL` independently of the container's development
connection. Worker helpers require pytest's isolated `test_` database and pass
that exact address through `TEST_DATABASE_URL`. The suite refuses development
brokers, non-test worker databases, nonlocal storage endpoints, and buckets
other than `speleodb-user-artifacts-test`. Missing required services fail
clearly. Run serially; the configured test bucket must exist with the test
credentials.

Tests create their PostgreSQL schema from pristine `template0`, avoiding
developer objects and stale libc collation metadata. This changes neither shared
templates nor the development database. SQLite cannot exercise the retained
PostgreSQL advisory-lock and immediate-constraint contracts and is rejected at
settings load with a configuration error.

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
cleanup. Lease tests cover finite acquisition budgets and ownership loss. Signal
and retry tests cover interrupted scheduler construction, terminal failure
propagation, and finalizer safety. Worker tests cover its profile, failed
preflight, explicit native-thread overrides, and actual prefork
timeouts/recovery.

Run the complete focused checks inside the already-running application
container, with the configured dedicated test broker available:

```bash
docker exec -w /app speleodb-monorepo-django pytest speleodb/background_jobs/tests/test_live_worker.py compose/tests/test_celery_runtime.py compose/tests/test_celery_result_backend.py compose/tests/test_runtime_settings.py compose/tests/test_background_services.py speleodb/background_jobs/tests/test_scheduler.py speleodb/background_jobs/tests/test_consumer.py -q
```

The same tests are collected in the default backend suite; no opt-in runner is
required. Missing database or service prerequisites fail clearly; they never
change the configured connection or skip tests. For a deliberately partial
development run, `-m 'not live_services'` explicitly deselects real
worker/broker checks. Compare service memory and per-process RSS/PSS,
parent/child membership, thread count, and startup high water in the same
environment. For Linux subprocess probes, read `/proc/<pid>/status` (`VmRSS`,
`VmHWM`, `Threads`) and `/proc/<pid>/smaps_rollup` (`Pss`).
`getrusage().ru_maxrss` can retain the launching process's high water across
exec and misrepresent a fresh lightweight runtime. Exercise at least 15 minutes
of real scheduling, and sample worker memory before, during, and after
representative tasks. Keep startup-preflight memory separate from the long-lived
worker parent and its execution child.

The CI pytest job supplies Django's `DATABASE_URL` and `POSTGRES_HOST`,
`POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, and `POSTGRES_PASSWORD`, all
targeting the same disposable PostgreSQL service. Service-container environment
variables are not inherited by runner processes. Keep explicit connection
settings for real entrypoint and isolated-worker tests.

The reloader subprocess loads `config.settings.local`, which requires an
explicit `DJANGO_SECRET_KEY`; the default in test settings is not an environment
variable. Its test supplies a dummy key and disables private dotenv loading.
Live Beat publication probes likewise pass the parent test settings' resolved
secret explicitly and disable private dotenv loading. Child failures include
their captured stderr so a missing setting is visible in CI.

Subprocess probes that change into a temporary directory must also provide the
checkout root in their child `PYTHONPATH`. The devcontainer includes `/app`
globally; a standalone CI checkout does not. The temporary-directory settings
and pytest selection probes configure this path themselves. Reproduce the
standalone environment inside the existing container with:

```bash
docker exec -w /app speleodb-monorepo-django \
  env -u PYTHONPATH -u DJANGO_SECRET_KEY \
  pytest speleodb/common/tests/test_test_settings_service_endpoints.py \
  speleodb/testing/tests/test_pytest_selection.py -q

docker exec -w /app speleodb-monorepo-django \
  env -u PYTHONPATH -u DJANGO_SECRET_KEY DJANGO_READ_DOT_ENV_FILE=false \
  pytest speleodb/background_jobs/tests/test_live_worker.py::test_live_housekeeping_records_only_failures \
  speleodb/background_jobs/tests/test_live_worker.py::test_live_beat_publication_preserves_worker_result_recording -q
```

When verifying CI environment changes, run the Compose tests from a checkout
without `.env` or `.envs/test.env`, using the workflow's environment. This
catches missing inputs that local credentials can hide. These settings affect
test setup only and add no application runtime work.

## Local development reloads

For local development, generated repositories and scratch files under `.workdir`
must not restart Django while exports or tests run. The local settings select
Werkzeug's stat reloader and exclude `.workdir` paths; normal application code
changes still reload. This also avoids watchdog/inotify directory-removal races
on Docker bind mounts.

Both local Celery services use `python -m compose.celery.autoreload`, with
`worker` or `beat` as the final argument. The shared development launcher uses
the already-declared `watchfiles` dependency and starts the corresponding
`compose/celery/<service>/start` directly from the mounted checkout. It watches
application Python packages and source packages exposed by `PYTHONPATH`, which
includes the monorepo's shared survey-library overlays. Tests, `.workdir`,
`.artifacts`, bytecode, editor temporary files and non-Python edits are ignored.
The watcher avoids repository/build roots when selecting overlay packages.

Edits send SIGINT to the service's process group. Celery's prefork children
ignore that signal while the worker performs warm shutdown and joins its pool;
Beat synchronizes and releases its existing database lease. Replacement is
sequential, so two scheduler generations do not overlap. There is no forced
termination timeout for a code reload: a running task delays the reload until it
finishes. Container stop retains the existing Compose grace period. Unexpected
service exits propagate to Compose's existing restart policy.

Changing the local Compose command requires an initial normal Compose
reconciliation. From the standalone web checkout use
`docker compose -f local.yml up -d celery-worker celery-beat`. In the monorepo,
retain the existing project name and complete Compose file list recorded on the
running containers, including Dev Containers overlays, and run the same `up -d`
service selection. Do not use `--no-deps`: setup and dependency health gates
remain part of startup. A plain restart cannot apply a changed Compose command.
This command change needs no image rebuild and does not change Django's
launcher.

Python source edits then reload automatically. Shell launcher or watcher-module
changes still require restarting the affected local service; the source-mounted
launcher is read on startup. Native extensions still require their normal
rebuild before restarting the affected service. Production continues using the
copied ordinary launchers and requires its normal image/deployment workflow.

Verify readiness in each service's logs, a single Beat scheduler, and worker
task events **OFF**. `compose/tests/test_celery_autoreload.py` exercises real
filesystem notifications, ignored generated/test changes, application and shared
library edits, sequential warm replacement, and child-process cleanup without
using the development broker or database.

## Task history and scheduler health

Open **Celery Results → Task results** in Django admin to inspect task IDs,
names, status, start/update timestamps, workers, arguments, result payloads,
tracebacks, and the periodic task name when present. Group results retain their
existing diagnostic view. Both interfaces keep result fields read-only,
including for superusers: no manual create, status edit or delete is available.
Active superusers can use **RETRY** on a failed task's detail page or **RETRY
selected failed tasks** in the list action menu. Both submit immediately with no
confirmation page; successful and in-progress selections are excluded. Django's
authenticated staff permissions protect this operational data; do not put
credentials or unnecessary personal data in task arguments or return values.
Application jobs and attempts link to their technical records. The task list
labels `date_done` as **Last updated** because Celery also updates it during
STARTED and RETRY; it is not exclusively a completion timestamp.

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
| `speleodb.background_jobs.tasks.maintain_background_jobs` | 600 seconds      | Recover exports and send notifications                |
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
that an archive is complete or email was delivered. Export tasks may catch a
recoverable error, store it in their durable job, and arrange a bounded retry
before returning. Map conversion instead records aggregate failure in TaskResult
when any revision fails. Consult Background jobs / Job attempts, notification
fields, cleanup counters, and Operations receipts and task results for map
outcomes. Task-result **RETRY** requeues the same task ID and updates the same
TaskResult row in place. It clears the previous failure, traceback, worker and
start time before publication, preserves the row identity and original creation
time, and records the administrator's explicit retry in the permanent audit.
Ordinary task retries retain their arguments, force settings and required
operation metadata while resetting previous outcomes. Campaign email retries
instead fetch the current campaign template, subject and other content. They
retain the recipient user ID and use that user's current email, or retain the
explicit email address for direct recipients. Older account receipts first use
the user ID from intact stored arguments; only truncated receipts fall back to
their saved email. The recovered user ID is retained for later retries. A
missing linked user is reported rather than sending to an obsolete address. This
path does not need the old email snapshot, so existing failed campaigns with
truncated argument previews can retry. See
[campaign delivery](donation-campaign-backend.md). Other task argument
representations are decoded as data, never executed; complete representations
are retained on publication. Unavailable arguments are reported per task so
other selected failures can still be retried.

Export generation retries use `retry_export(task_id=...)` to requeue the current
failed domain attempt with its existing task ID. An older superseded attempt,
active artifact cleanup or a published archive prevents rearming that attempt.
The same object key is reused so a previous failed upload does not become
untracked. Ordinary export API retries continue creating new attempts.
Notification retries retain the task ID through the existing request/dispatch
lifecycle, which issues a fresh delivery token. The retry transaction claims
queued notification state and its token before commit; only broker publication
is deferred, so periodic maintenance cannot substitute a new task ID. Ordinary
notification dispatch keeps its existing behavior. Eligibility and expiry checks
still apply. Other failed results return to PENDING and are published after
commit through the existing operations publisher on `background_control`,
including guarded GeoJSON and campaign executions. Retrying can repeat completed
side effects such as email delivery; inspect the failure and correct its cause
first. Publication uncertainty remains visible in result metadata. No automatic
retry, scheduler or new persistent model is introduced.

Results expire after 30 days. `install_background_schedules` owns the daily
`celery.backend_cleanup` entry on `background_control`; an available Beat and
worker must execute it for expiry to remove rows. Cleanup is not a migration or
an immediate purge of historical rows. Retained unsuccessful housekeeping
results follow the same expiry. Application export history has its separate
90-day policy and preserves records needed for pending cleanup.

These limits do not apply to the permanent
[administrator audit](admin-audit-logging.md). An explicit administrator task
request is recorded once with an email snapshot and receipt identifiers; worker
execution and scheduler dispatch create no admin audit entries. Expired task
results may no longer be inspectable, but the original administrator action and
its recorded scope remain available.

Check Beat logs, process health, advisory-lock ownership, and the Periodic tasks
admin to diagnose scheduling. `last_run_at` and `total_run_count` indicate
scheduler dispatch, not successful worker execution. Successful housekeeping
runs deliberately have no result row. Check worker logs, queue consumption,
pending-work age, application progress and error records, and retained task
failures together. A missing result is not proof that a scheduled task did not
run, and a recent Beat counter is not proof that it succeeded.

Updating one result row per actual execution and omitting frequent successful
sweeps bounds routine writes; result retention still needs monitoring. This
policy does not cap PostgreSQL RAM or change its resource limits. Worker
heartbeats and control commands remain available with task-event publication
disabled.

Regression coverage uses real Celery publication/execution and the existing
Django backend: actual tasks record STARTED/SUCCESS, retries and failures;
housekeeping records failures while omitting successful rows; Beat's minimal
runtime applies the same message policy without importing application tasks.
Admin tests check diagnostic metadata, permissions, rejected mutations, manual
single/batch publication after real task failures and export attempt ownership;
retention tests remove expired results while preserving recent rows. These
checks complement the existing domain retry, artifact and worker-loss tests.

## Railway deployment

Inspect the actual production project/environment before mutation.
`.railway/railway.ts` is the sole Railway service configuration for all eight
active production services and their volumes. See
[production Railway configuration](railway-production.md) for the complete
inventory and Redis replacement operations. Gogs and the Git backup job are
declared in this same file; see
[Git backup and Gogs operations](git-backup-operations.md) for their settings.
Preserve the existing named partial and its current web service. Do not add
competing TOML/JSON service configuration or take ownership of unrelated
services by applying an incomplete whole-project graph. `railpack.json`
separately owns image construction, including dependencies and frontend assets.
Service configuration changes require a reviewed `railway config plan` and
`railway config apply`; application Git pushes alone do not apply IaC edits.

The same partial also owns the existing `Postgres-Prod` service configuration:
its image, build settings, region and replica count, private network endpoint,
existing 5000 MB volume and mount, resource limits, image startup, PITR archive
bucket, and variable map. Existing variable values and secrets are retained with
`preserve()`. The CPU limit remains 1 and the memory ceiling remains 500,000,000
bytes; memory reduction comes from persistent PostgreSQL settings.

PostgreSQL must use the image's own startup without an override so Railway can
enable PITR. The entrypoint handles SSL, volume locking, WAL archiving and
automatic base backups. `shared_buffers=16MB`, `temp_buffers=1MB`,
`work_mem=1MB`, and `hash_mem_multiplier=1.0` persist in
`PGDATA/postgresql.auto.conf`. These settings favor a smaller memory footprint
over cache hit rate and in-memory query execution. They do not limit Linux's
separate filesystem cache. Applying a shared-buffer change requires a database
restart; verify all four values in `pg_settings`, SSL, and runtime logs after
deployment, and confirm the next configuration plan has no effective changes.
See
[PostgreSQL PITR and memory tuning](railway-production.md#postgresql-pitr-and-memory-tuning)
for provisioning, recovery and backup verification requirements.

The root JavaScript manifest and lockfile declare the Railway IaC tooling and
TypeScript dependencies. `bun run typecheck:development` validates the authoring
file through pre-commit/CI. Use a Railway CLI that supports the repository's IaC
configuration. The web service, worker and Beat track the release branch
declared in `.railway/railway.ts`, with GitHub check suites enabled and no fixed
source commit pin. Their unrestricted watch patterns permit rebuilds after
repository changes pass checks. Read back source settings after applying
configuration and verify the actual source revision on each resulting
deployment.

Railway omits default values from its serialized configuration. The IaC source
therefore omits unrestricted watch patterns, disabled application sleeping, and
the default `ON_FAILURE` policy with ten retries. Verify these effective values
on the service instance when reviewing drift; explicitly repeating them in the
source creates `null`-to-default plan differences without changing behavior.

The `SpeleoDB-Prod` named partial manages the existing `SpeleoDB-Prod`,
`Celery-Worker`, `Celery-Beat`, `Postgres-Prod`, `Redis-Prod`, `Gogs`,
`Database Backup CRON`, and `SpeleoDB Git Backup CronJob` services, plus their
four persistent volumes. Generate a fresh plan against `speleoDB` / `production`
before applying. Reject unrelated changes or removals. A plan does not provision
missing referenced values; verify prerequisites in the target environment.

Before deployment, verify Redis has a persistent volume, AOF and `noeviction`.
Redis image, variables, resource limits, TCP endpoint and volume are managed in
`.railway/railway.ts`. PostgreSQL is managed with the settings described above.
The application database stores the result backend; do not provision a separate
monitoring database.

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
is declared on Redis in this same IaC file.

When replacing copied values, inspect both raw reference expressions and
rendered connection URLs. Compare resolved values without printing secrets, then
verify a broker `PING` and database connection from a deployed consumer. Remove
the obsolete shared value only after checking every service for remaining
references. An equivalent reference-only correction does not require a restart.

The IaC file references the existing web service's runtime variables for Django
worker and Beat. Inventory those variable names before applying; optional
deployment overrides such as a custom sender address or Sentry configuration
must be carried over explicitly when present. The complete variable maps are
declared: non-secret settings and references retain their existing values, while
credentials use `preserve()` to keep their values in Railway. Refresh that
inventory before each plan so newly added settings cannot be deleted. Web,
worker, and Beat reference the same Redis-owned broker URL. The application
background services explicitly use `https://www.speleodb.org` for notification
links.

Deploy these continuously running services in `us-east4-eqdc4a`, alongside the
existing web service:

- `Celery-Worker`: one replica initially, consuming both queues with concurrency
  one; retain the existing 1 vCPU/1 GB limits. Scale this service's replicas to
  add capacity; do not create separate services for task categories.
- Beat: one replica with the application advisory lock and the same 1 vCPU/1 GB
  limits. Both memory caps are explicitly set to 1,000,000,000 bytes in IaC.

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

1. Select the reviewed release after its required checks pass; record the
   release revision.
2. Inventory existing service configuration and preview the IaC plan. Reject
   unrelated deletions or secret replacements. Preserve the named partial and
   its service ownership.
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

Keep application publishers, worker and Beat compatible during rollback,
preserving the advisory-lock identifier, schedule records and audit history. The
canonical Beat launcher is the lightweight Python module. A rollback must use a
start command supported by its selected source revision. Review and apply
Railway configuration when a rollback changes a managed start command or overlap
policy.

### Production rollout verification

Configuration apply does not deploy updated Python code. Read back the managed
service variables after configuration apply, and verify the exact new
application deployments and their real task results before claiming the release
is live. A Git push alone does not apply IaC changes.

Preserve the configured shutdown grace and advisory lock. Check each
deployment's process, queue consumption, scheduler ownership, result policy and
application behavior. Review unrelated live configuration drift independently
instead of silently applying it with the release.

## Sources

- [Celery task result policy](https://docs.celeryq.dev/en/stable/userguide/tasks.html#Task.store_errors_even_if_ignored)
- [django-celery-results](https://django-celery-results.readthedocs.io/)
- [Redis Pub/Sub database scoping](https://redis.io/docs/latest/develop/pubsub/)
- [Railway Infrastructure as Code](https://docs.railway.com/infrastructure-as-code)
- [Railway health checks](https://docs.railway.com/deployments/healthchecks)

## Survey GeoJSON generation

Eligible source uploads schedule their exact revision after push and SQL commit.
Map scheduling failure does not reject a saved source. TaskResult is the sole
execution status; generation has no separate status API, journal or automatic
retry workflow. Hard-killed uploads may leave orphaned objects until the next
explicit full reset. See [background survey maps](project-geojson-background.md)
and [Operations](admin-operations.md) for cleanup and manual recovery.
