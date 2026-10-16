# Production Railway configuration

[`.railway/railway.ts`](../.railway/railway.ts) is the single configuration for
all eight active services in `speleoDB` / `production`. Its stable named partial
is `SpeleoDB-Prod`. The backup applications retain their separate source
repositories. Offline Uptime Kuma and PgHero, their resources, and other
environments remain outside this partial.

## Managed resources

All eight services retain one replica in `us-east4-eqdc4a` and runtime `V2`.

| Service                     | Source                                             | Build          | Private hostname  | Persistent mount                                          |
| --------------------------- | -------------------------------------------------- | -------------- | ----------------- | --------------------------------------------------------- |
| SpeleoDB-Prod               | `OpenSpeleo/SpeleoDB`, `master`                    | Railpack, V3   | `speleodb`        | None                                                      |
| Celery-Worker               | `OpenSpeleo/SpeleoDB`, `master`                    | Railpack, V3   | `celery-worker`   | None                                                      |
| Celery-Beat                 | `OpenSpeleo/SpeleoDB`, `master`                    | Railpack, V3   | `celery-beat`     | None                                                      |
| Postgres-Prod               | `ghcr.io/railwayapp-templates/postgres-ssl:16`     | Nixpacks, V3   | `postgres`        | `Postgres disk`, 5000 MB at `/var/lib/postgresql/data`    |
| Redis-Prod                  | `docker.io/railwayapp/redis:7.4.3`                 | Nixpacks, V3   | `redis-prod`      | `rhythm-volume`, 5000 MB at `/bitnami`                    |
| Gogs                        | `gogs/gogs`                                        | Railpack       | `gogs`            | `beneficial-volume`, 5000 MB at `/data`                   |
| SpeleoDB Git Backup CronJob | `OpenSpeleo/SpeleoDB_Git_Backup_CronJob`, `master` | Dockerfile, V3 | `git-backup-sdb`  | `speleodb-git backup cronjob-volume`, 50000 MB at `/data` |
| Database Backup CRON        | `railwayapp-templates/postgres-s3-backups`, `main` | Railpack       | `backup-cron-lde` | None                                                      |

The PostgreSQL backup retains commit `5665c7d0aa0a4fd3ca8823050d4d2b0d0dc9e5fd`
and its template upstream URL. Do not replace this pin with the latest branch
revision during configuration adoption. It runs at `0 */1 * * *`; Git backup
retains `0/60 * * * *`. Both retain `NEVER` restart and 1 CPU /
2,000,000,000-byte memory limits. PostgreSQL backup retains
`SINGLE_SHOT_MODE=1`, Alpine private networking, its existing S3 destination,
and the reference to PostgreSQL's private URL.

Other existing limits remain: web 8 CPUs / 3,000,000,000 bytes, each Celery
service 1 CPU / 1,000,000,000 bytes, PostgreSQL 1 CPU / 500,000,000 bytes, and
Redis 0.5 CPU / 500,000,000 bytes with its existing 100,000,000,000-byte disk
limit. Gogs is capped at 1 CPU / 500,000,000 bytes, alongside its separate 32
MiB Go-runtime soft memory target.

The four volumes retain online resizing and usage alerts at 80%, 95%, and 100%.
Redis's existing TCP proxy targets port 6379. Its assigned proxy address and
port remain Railway-owned; URL expressions reference those platform variables.
Public web and Gogs domains retain their existing ports, and Gogs retains its
minor-image-update schedule.

Startup/predeploy commands, deployment overlap/draining settings, source check
suites, and private endpoints are declared in the file. PostgreSQL uses its
image's default startup for PITR, with memory tuning persisted on its volume as
described below. In particular, web's existing overlap environment variable is
`60`, while its configured deployment overlap is `0`; adoption does not
normalize this difference. See
[background jobs](background-jobs-operations.md#railway-deployment) and
[Git backup and Gogs](git-backup-operations.md) for application operations.

## Variables and platform defaults

The file owns all 164 service variable keys. Non-secret settings and references
are explicit; 18 credential values use `preserve()`. Never replace those with
placeholders or resolved secrets. Retain reference expressions, including
self-references in database URLs and service references in consumers. Declaring
an environment map owns the whole map: a missing existing key can become a
deletion. Update the inventory when adding variables.

Redis retains AOF and its existing RDB policy, without injecting settings into
its running process or changing its persisted application configuration.

Railway omits many default settings from its API. Leave those absent instead of
adding explicit default values that produce updates. Generated network
allocations, HA conversion/template UI metadata, and secret values remain
platform-managed. Empty legacy Config File settings are disabled; the SDK
normalizes the empty string away. Ordinary application deployment does not apply
this TypeScript file.

## PostgreSQL PITR and memory tuning

`Postgres-Prod-PITR` is the production archive bucket in `iad`. Its credentials,
endpoint and S3 signing region are referenced through `WAL_ARCHIVE_*` variables;
never copy resolved credentials into source. `WAL_ARCHIVE_PATH=/pgbackrest`
selects the archive prefix. `WAL_ARCHIVE_S3_URI_STYLE=host` matches the bucket's
virtual-host addressing requirement. The bucket's `REGION` output is the S3
signing region, not its infrastructure location. Older project-level backup
buckets remain outside this partial and must not be deleted during adoption.

Do not add a PostgreSQL startup override. Railway's PostgreSQL image entrypoint
configures WAL archiving, SSL, volume locking and the automatic pgBackRest
backup watcher. The watcher creates the initial full backup, then weekly full
and daily differential backups; the image retains four full backups. Recovery
coverage starts at the first completed backup and requires a continuous WAL
archive. PITR uses additional backup-process memory, bucket storage and network
egress; the service remains capped at 1 CPU and 500,000,000 bytes. The separate
hourly database backup cron job remains enabled.

The four PostgreSQL memory settings live in
`/var/lib/postgresql/data/pgdata/postgresql.auto.conf`, retained on
`Postgres disk`. They were migrated from startup flags before enabling PITR.
This is persistent database configuration, not a Railway service setting:
applying `railway.ts` to an empty replacement volume does not recreate it. When
provisioning or recovering a database, inspect the effective settings and, if
necessary, set each value as a separate administrative SQL statement outside a
transaction:

```sql
ALTER SYSTEM SET shared_buffers = '16MB';
ALTER SYSTEM SET temp_buffers = '1MB';
ALTER SYSTEM SET work_mem = '1MB';
ALTER SYSTEM SET hash_mem_multiplier = '1.0';
```

Staging's `Postgres-Stage` uses these same four persisted values and the same
`PGDATA` path on `agreement-volume`. It already uses the image's native startup
and has working PITR through its existing `Postgres-PITR` bucket. Applying the
memory tuning requires only the SQL statements and a database redeployment;
retain its archive history, credentials, image and existing resource limits.
Staging services remain outside this production partial: do not apply the
production graph to staging.

Check `pg_file_settings` for errors before restarting. A `shared_buffers` change
requires a restart; after restart verify all four values and their `sourcefile`
in `pg_settings`. These settings do not cap Linux filesystem cache. Keep the
image's generated PITR configuration under `PGDATA/conf.d`; do not disable its
archive settings through `ALTER SYSTEM`.

To enable PITR on an existing database, first preserve its memory settings and
review removal of any custom start command. Railway's native PITR flow creates a
bucket and archive references. Alternatively, declare the same bucket and
references directly in the single IaC file. Use a unique project-wide bucket
name, inspect its S3 URL style, review the exact plan, then apply and deploy. Do
not apply an older variable map that omits the archive references: IaC owns the
entire map. Native `pitr enable --no-deploy` commits the environment's whole
staged patch, so check for unrelated pending changes before using it.

After deployment, require all of the following before reporting PITR ready:

- `railway postgres pitr status --service Postgres-Prod --environment production`
  reports enabled. If its automatic SSH probe is unavailable, run the following
  database and backup checks through an authenticated `railway ssh` session.
- `pg_settings` retains the four memory values, SSL is enabled, and
  `archive_mode=on` with the image's pgBackRest archive command.
- `pg_stat_archiver` advances successfully and `pgbackrest --stanza=main info`
  shows a completed full base backup. Enabled variables alone are insufficient.
- Web, worker and Beat can connect to PostgreSQL, with no continuing archive
  errors or out-of-memory restarts.
- The final configuration plan has no effective changes, including the bucket.

Recovery creates a separate database service; selecting a restore point does not
roll back the running production database. Verify the restored data before
changing application connection strings. See
[Railway PITR](https://docs.railway.com/volumes/point-in-time-recovery) and
[PostgreSQL configuration](https://www.postgresql.org/docs/16/config-setting.html).

## Redis replacement operations

Redis runs as a plain image service. Its former template-origin service caused
Railway CLI 5.67.1 to omit the builder and volume mount when importing live
configuration. Recreating it without a template resolved those false changes;
ordinary `railway config plan/apply` now manages the complete definition.

The `docker.io/railwayapp/redis:7.4.3` image contains Bitnami's Redis packaging
and startup scripts. `/bitnami` is the persistent mount expected by that image;
the image's registry namespace does not change its data directory. Keep the
explicit `docker.io/` prefix: CLI 5.67.1 otherwise normalizes Railway database
image tags to their major version and can miss an intended minor or patch
upgrade.

Before a version upgrade, retain a protected backup made by the original Redis
version. Redis 7.4 writes a newer RDB format than 7.2; reverting only the image
after a snapshot or AOF rewrite can fail to load. A downgrade requires restoring
the compatible pre-upgrade backup, with any intervening writes reconciled.

Service replacement requires explicit authorization and a brief interruption.
Before replacement, inventory raw and rendered consumer variables, verify the
image is available, save Redis data, and take a protected backup outside the
checkout. Stop Redis gracefully before transferring its existing volume. Keep
the password, image, private hostname, persistence settings, and resource limits
unchanged. Retain `rhythm-volume`; do not delete or create a replacement volume.
Seed the preserved password securely on the new plain service before applying
the configuration. Never put credentials in the authoring file or tool output.

Deleting a service can rewrite consumer references to the deleted service's
tombstone name even when its replacement has the original name. Restore
`SpeleoDB-Prod.REDIS_URL` and the web, worker, and Beat `CELERY_BROKER_URL`
references from the evaluated file. Once Redis loads its existing data and
responds to `PING`, redeploy all three consumers and verify their deployed
connections. Check worker readiness and Beat's scheduler lock as well as web
health. A preserved private hostname does not update an existing process.

The public TCP proxy receives a new address when the service is recreated.
External consumers must refresh `REDIS_PUBLIC_URL`; application services use the
private hostname. Verify all original persistent data remains available,
allowing for normal cache expiry and live queue activity. Finish with a fresh
configuration plan showing no effective changes.

## Verification

Run `bun run typecheck:development` from `/app` in the existing application
container. Run Railway planning from the web repository, explicitly targeting
production. A plan alone does not prove complete coverage because omitted
settings may remain unmanaged; compare the full raw configuration as well. After
any authorized apply, verify the actual live settings and deployments.

```bash
railway config plan --environment production
railway config apply --environment production
railway config plan --environment production --detailed-exit-code
```

Review the plan before applying and reject unrelated changes. Verify all eight
services, four volumes, the PITR bucket, complete variable maps, and reference
expressions against raw live configuration. Keep secrets and snapshots outside
the checkout.

Relevant upstream implementation:
[import/compiler](https://github.com/railwayapp/cli/blob/v5.67.1/src/iac/compiler.rs),
[plan/apply and ownership](https://github.com/railwayapp/cli/blob/v5.67.1/src/iac/engine.rs),
[change-set comparison](https://github.com/railwayapp/cli/blob/v5.67.1/src/iac/change_set.rs).
