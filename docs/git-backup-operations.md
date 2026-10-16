# Git backup and Gogs operations

[`.railway/railway.ts`](../.railway/railway.ts) is the single Railway
configuration for the web application, Celery services, PostgreSQL, Redis, Gogs,
and both backup cron jobs. In the monorepo it lives at
`apps/web/.railway/railway.ts`. Keep all definitions in this file under the
existing `SpeleoDB-Prod` named partial; do not add a separate configuration or
SDK to the backup repository.

The file manages the existing `SpeleoDB Git Backup CronJob` and `Gogs` services
and their volumes in `speleoDB` / `production`. The backup application still
builds from its own `OpenSpeleo/SpeleoDB_Git_Backup_CronJob` repository. Moving
its infrastructure definition does not change that source or application code.
Offline services not declared in this file remain outside its ownership. See
[production Railway configuration](railway-production.md) for all eight active
services, the PostgreSQL backup job, and Redis replacement operations. See
[background job operations](background-jobs-operations.md#railway-deployment)
for the application services and PostgreSQL settings.

## Preserved settings

| Setting              | Value                        |
| -------------------- | ---------------------------- |
| Builder              | Dockerfile                   |
| Dockerfile path      | `Dockerfile`                 |
| Runtime              | `V2`                         |
| Replicas             | 1                            |
| Cron schedule        | `0/60 * * * *` (hourly, UTC) |
| Application sleeping | Disabled                     |
| Restart policy       | `NEVER`                      |

The backup's GitHub `master` source, check-suite requirement, 1 CPU/2 GB hard
limits, private hostname, and 50 GB `/data` volume are preserved. Gogs retains
its existing image auto-update policy, public/private hostnames, 5 GB `/data`
volume, and runs with hard limits of 1 CPU / 500,000,000 bytes. Both services
run in `us-east4-eqdc4a`.

Credentials use `preserve()`; their values remain in Railway. Other settings and
references are declared with their existing values. When adding a variable in
Railway, declare it here before the next apply, because omitted variables are
planned for deletion. Use `preserve()` for credentials.

## Memory settings

`railway.ts` is the source of truth for these settings:

| Scope               | Setting                     | Value   |
| ------------------- | --------------------------- | ------- |
| Backup job          | `BACKUP_PARALLEL_THREADS`   | `1`     |
| Gogs Go runtime     | `GOMEMLIMIT`                | `32MiB` |
| Gogs Go runtime     | `GOGC`                      | `25`    |
| Gogs Go runtime     | `GOMAXPROCS`                | `1`     |
| Gogs `[repository]` | `COMMITS_FETCH_CONCURRENCY` | `1`     |
| Gogs `[database]`   | `MAX_OPEN_CONNS`            | `2`     |
| Gogs `[database]`   | `MAX_IDLE_CONNS`            | `1`     |
| Git, both services  | `pack.threads`              | `1`     |
| Git, both services  | `pack.windowMemory`         | `16m`   |
| Git, both services  | `pack.deltaCacheSize`       | `8m`    |
| Git, both services  | `core.deltaBaseCacheLimit`  | `8m`    |

The shared Git settings use `GIT_CONFIG_COUNT` and indexed key/value environment
variables so Git subprocesses inherit them without modifying repository config
files. They bound selected buffers, not total Git process memory. Git integrity
checks, compression, and repository maintenance remain enabled.

Gogs does not map arbitrary environment variables to INI sections. Its startup
command therefore copies `/data/gogs/conf/app.ini` into an ephemeral, mode-600
file at `/app/gogs/docker/s6/gogs/low-memory.ini`, appends the managed INI
settings, and adds `--config` to the image's Gogs launch command. Gogs' INI
loader merges repeated sections and uses the last value for each key. The
original persistent configuration, credentials, repositories, entrypoint, and s6
supervision are retained. Startup fails if a future image changes the expected
Gogs launch command, rather than silently ignoring the overrides.

The 32 MiB value is a soft target for Go-managed memory, not a minimum or a cap
on Gogs RSS, Git subprocesses, or Linux filesystem cache. Go can exceed it to
avoid excessive garbage collection. Lower concurrency and smaller caches favor
memory over throughput; validate a complete backup after changing them. The
hourly schedule must leave enough time for the serial backup to finish.

After a deployment, check `/healthcheck`, the Gogs process arguments and
selected environment variables, the generated INI settings, and Git's effective
config. Confirm the backup reports one worker, completes all repositories
without failures, and exits. Compare Go/process memory separately from the
container's filesystem cache; a restart alone makes cache measurements
misleading.

To adjust or revert tuning, edit the settings in `railway.ts`, plan/apply, and
redeploy the affected services. The runtime INI is regenerated each start; do
not edit it manually. Gogs embeds its configuration path in newly created
repository hooks, so retain the startup wrapper and runtime config path when
reverting individual settings. Removing the wrapper requires first regenerating
repository hooks against the persistent configuration through Gogs' admin
maintenance tools.

## Validate and apply

Use the Railway SDK pinned in the web repository's root Bun manifest and
lockfile. Run web checks from `/app` in the existing application container:

```bash
bun run typecheck:development
```

Run Railway commands from the web repository root (`apps/web` in the monorepo),
linked to the existing `speleoDB` project. Target production explicitly:

```bash
railway config plan --environment production
```

Review the plan before applying. Reject unrelated updates, deletions, or secret
replacements. For a reviewed plan:

```bash
railway config apply --environment production
railway config plan --environment production --detailed-exit-code
```

Do not set a service's legacy Railway Config File field to this TypeScript file.
IaC is evaluated by `railway config plan/apply`, rather than loaded during
application deployments. Committing or deploying application code alone does not
apply configuration changes. Verify the resulting deployments and effective
runtime settings after applying; redeploy only affected services if needed. Gogs
uses its existing image; the backup retains its application build when only
runtime settings change.

When consolidating existing named partials, use `railway config partials list`
and `railway config partials transfer` (CLI 5.67.1 or newer). Verify the linked
environment, inspect `--dry-run`, and transfer only the intended service and
volume addresses. This updates ownership metadata without restarting or
recreating services. Remove the old authoring file so it cannot reclaim
ownership, then confirm the consolidated plan has no effective changes. A
source-only move with an empty plan requires no configuration apply or redeploy.

## Official references

- [Infrastructure as Code and migration](https://docs.railway.com/infrastructure-as-code#migrating-from-config-as-code)
- [TypeScript IaC reference](https://docs.railway.com/infrastructure-as-code/reference)
- [Go garbage collection and soft memory limits](https://go.dev/doc/gc-guide)
- [Gogs 0.14.3 configuration](https://github.com/gogs/gogs/blob/v0.14.3/conf/app.ini)
- [Git configuration](https://git-scm.com/docs/git-config)
