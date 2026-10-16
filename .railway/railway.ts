import {
  bucket,
  defineRailway,
  github,
  image,
  preserve,
  project,
  ref,
  service,
  volume,
} from "railway/iac";

// Sole configuration for all eight active production services, volumes and PITR.
// Keep this ownership name; only the resources declared below are managed here.
// Omit Railway defaults (no sleep, ON_FAILURE with 10 retries, unrestricted
// watch patterns): its API omits these values, so restating them creates drift.
export const partial = "SpeleoDB-Prod";

// Git subprocesses do not share Go's memory limit. Bound their expensive
// packing/delta buffers on both ends of a backup without disabling integrity checks.
const gitMemorySettings = {
  "pack.threads": "1",
  "pack.windowMemory": "16m",
  "pack.deltaCacheSize": "8m",
  "core.deltaBaseCacheLimit": "8m",
};
const gitEnvironment = {
  GIT_CONFIG_COUNT: String(Object.keys(gitMemorySettings).length),
  ...Object.fromEntries(
    Object.entries(gitMemorySettings).flatMap(([key, value], index) => [
      [`GIT_CONFIG_KEY_${index}`, key],
      [`GIT_CONFIG_VALUE_${index}`, value],
    ]),
  ),
};

const gogsSettings = {
  repository: { COMMITS_FETCH_CONCURRENCY: 1 },
  database: { MAX_OPEN_CONNS: 2, MAX_IDLE_CONNS: 1 },
};
const gogsOverrides = Object.entries(gogsSettings)
  .map(([section, settings]) =>
    [
      `[${section}]`,
      ...Object.entries(settings).map(([key, value]) => `${key} = ${value}`),
    ].join("\n"),
  )
  .join("\n\n");

// Gogs has no section/key environment overrides. Make an ephemeral config copy;
// its INI loader merges repeated sections and uses the last value of each key.
// Keep the persistent configuration and the image's entrypoint/s6 setup intact.
const gogsRun = "/app/gogs/docker/s6/gogs/run";
const gogsCommand = 'exec gosu "$USER" /app/gogs/gogs web';
const gogsRuntimeConfig = "/app/gogs/docker/s6/gogs/low-memory.ini";
const gogsRuntimeCommand = `${gogsCommand} --config ${gogsRuntimeConfig}`;
const gogsStart = [
  "set -eu",
  "original_umask=$(umask)",
  "umask 077",
  "test -s /data/gogs/conf/app.ini",
  `cat /data/gogs/conf/app.ini > ${gogsRuntimeConfig}`,
  `cat >> ${gogsRuntimeConfig} <<'GOGS_MEMORY_SETTINGS'`,
  "",
  gogsOverrides,
  "GOGS_MEMORY_SETTINGS",
  `chmod 600 ${gogsRuntimeConfig}`,
  `chown "\${PUID:-1000}:\${PGID:-1000}" ${gogsRuntimeConfig}`,
  `sed -i 's|^${gogsCommand}$|${gogsRuntimeCommand}|' ${gogsRun}`,
  // Fail before starting if a future image changes the expected launch command.
  `grep -Fxq '${gogsRuntimeCommand}' ${gogsRun}`,
  'umask "$original_umask"',
  "exec /app/gogs/docker/start.sh",
].join("\n");
const shellQuote = (value: string) => `'${value.replaceAll("'", "'\\''")}'`;

export default defineRailway(() => {
  const publicHostname = "www.speleodb.org";
  const publicOrigin = `https://${publicHostname}`;

  // Match the existing volume policy, including alerts and online resizing.
  const volumeSettings = {
    region: "us-east4-eqdc4a",
    allowOnlineResize: true,
    alerts: { usage: { "80": {}, "95": {}, "100": {} } },
  };
  const postgresDisk = volume("Postgres disk", {
    ...volumeSettings,
    sizeMB: 5000,
  });
  const postgresArchive = bucket("Postgres-Prod-PITR", { region: "iad" });

  // PITR requires the image's own entrypoint: never override its start command.
  // Memory tuning persists in PGDATA/postgresql.auto.conf; see the production
  // operations guide before moving or recreating this volume.
  // These database settings are NOT applied by railway.ts. They were saved with:
  //   ALTER SYSTEM SET shared_buffers = '16MB';
  //   ALTER SYSTEM SET temp_buffers = '1MB';
  //   ALTER SYSTEM SET work_mem = '1MB';
  //   ALTER SYSTEM SET hash_mem_multiplier = '1.0';
  // The file lives on "Postgres disk" at:
  //   /var/lib/postgresql/data/pgdata/postgresql.auto.conf
  // Staging "Postgres-Stage" uses the same values/path on "agreement-volume".
  // Its existing native PITR setup is retained; this production partial does
  // not manage staging services and must not be applied to staging.
  // Settings survive restarts/redeploys with this volume, but applying this IaC
  // to a new empty volume does not recreate them. If missing after replacement
  // or recovery, run each statement separately outside a transaction, restart
  // PostgreSQL and verify all four values in pg_settings.
  // Procedure: docs/railway-production.md#postgresql-pitr-and-memory-tuning
  const postgres = service("Postgres-Prod", {
    source: image("ghcr.io/railwayapp-templates/postgres-ssl:16"),
    build: { builder: "NIXPACKS", buildEnvironment: "V3" },
    replicas: { "us-east4-eqdc4a": 1 },
    env: {
      DATABASE_PRIVATE_URL: "postgresql://${{PGUSER}}:${{POSTGRES_PASSWORD}}@${{RAILWAY_PRIVATE_DOMAIN}}:5432/${{PGDATABASE}}",
      PGDATA: "/var/lib/postgresql/data/pgdata",
      PGDATABASE: "${{POSTGRES_DB}}",
      PGPASSWORD: "${{POSTGRES_PASSWORD}}",
      PGPRIVATEHOST: "${{RAILWAY_PRIVATE_DOMAIN}}",
      PGUSER: "${{POSTGRES_USER}}",
      POSTGRES_DB: "railway",
      POSTGRES_PASSWORD: preserve(),
      POSTGRES_USER: "postgres",
      SSL_CERT_DAYS: "820",
      WAL_ARCHIVE_BUCKET: ref(postgresArchive, "BUCKET"),
      WAL_ARCHIVE_ENDPOINT: ref(postgresArchive, "ENDPOINT"),
      WAL_ARCHIVE_KEY: ref(postgresArchive, "ACCESS_KEY_ID"),
      WAL_ARCHIVE_PATH: "/pgbackrest",
      WAL_ARCHIVE_REGION: ref(postgresArchive, "REGION"),
      WAL_ARCHIVE_S3_URI_STYLE: "host",
      WAL_ARCHIVE_SECRET: ref(postgresArchive, "SECRET_ACCESS_KEY"),
    },
    networking: { privateNetworkEndpoint: "postgres" },
    volumeMounts: { "/var/lib/postgresql/data": postgresDisk },
    deploy: {
      ipv6EgressEnabled: false,
      limitOverride: { containers: { cpu: 1, memoryBytes: 500000000 } },
      runtime: "V2",
      useLegacyStacker: false,
    },
  });

  const redisDisk = volume("rhythm-volume", {
    ...volumeSettings,
    sizeMB: 5000,
  });
  // Use the existing image service, not a database template that could replace
  // its image, variables, or persistent volume with template defaults.
  // Keep this a plain image service so IaC imports its builder and mount fully.
  // Qualify the registry so CLI 5.67.1 compares the exact tag, not just its major.
  const redis = service("Redis-Prod", {
    source: image("docker.io/railwayapp/redis:7.4.3"),
    build: { builder: "NIXPACKS", buildEnvironment: "V3" },
    replicas: { "us-east4-eqdc4a": 1 },
    env: {
      CELERY_BROKER_URL: "${{REDIS_URL}}/1",
      RAILWAY_RUN_AS_ROOT: "true",
      RAILWAY_RUN_UID: "0",
      REDISHOST: "${{RAILWAY_PRIVATE_DOMAIN}}",
      REDISPASSWORD: "${{REDIS_PASSWORD}}",
      REDISPORT: "6379",
      REDISUSER: "default",
      REDIS_AOF_ENABLED: "yes",
      REDIS_PASSWORD: preserve(),
      REDIS_PUBLIC_URL: "redis://default:${{REDIS_PASSWORD}}@${{RAILWAY_TCP_PROXY_DOMAIN}}:${{RAILWAY_TCP_PROXY_PORT}}",
      REDIS_RDB_POLICY: "3600#1 300#100 60#10000",
      REDIS_URL: "redis://default:${{REDIS_PASSWORD}}@${{RAILWAY_PRIVATE_DOMAIN}}:6379",
    },
    tcp: [6379],
    networking: { privateNetworkEndpoint: "redis-prod" },
    volumeMounts: { "/bitnami": redisDisk },
    deploy: {
      ipv6EgressEnabled: false,
      limitOverride: {
        containers: {
          cpu: 0.5,
          memoryBytes: 500000000,
          diskBytes: 100000000000,
        },
      },
      runtime: "V2",
      useLegacyStacker: false,
    },
  });
  const brokerUrl = ref(redis, "CELERY_BROKER_URL");

  // Own the full variable map: declare current settings/references explicitly
  // and retain production credentials with preserve(), never plaintext secrets.
  const SpeleoDB_Prod = service("SpeleoDB-Prod", {
    configFile: "",
    source: github("OpenSpeleo/SpeleoDB", { branch: "master", checkSuites: true }),
    build: { builder: "RAILPACK", buildCommand: "", buildEnvironment: "V3" },
    start: "gunicorn config.wsgi:application --workers ${GUNICORN_WORKERS} --threads ${GUNICORN_THREADS} --max-requests 128 --preload",
    replicas: { "us-east4-eqdc4a": 1 },
    preDeploy: "python /app/manage.py migrate && python /app/manage.py install_background_schedules && python /app/manage.py collectstatic --noinput --verbosity=3 --ignore=flags",
    env: {
      ALLOW_USER_DEBUG: "true",
      AWS_ACCESS_KEY_ID: preserve(),
      AWS_CLOUDFRONT_KEY_B64: preserve(),
      AWS_CLOUDFRONT_KEY_ID: "K3Q3L75WTA4NYC",
      AWS_S3_CUSTOM_DOMAIN: "static.speleodb.org",
      AWS_S3_REGION_NAME: "us-east-1",
      AWS_SECRET_ACCESS_KEY: preserve(),
      AWS_STORAGE_BUCKET_NAME: "static.speleodb.org",
      CELERY_BROKER_URL: brokerUrl,
      DATABASE_URL: ref(postgres, "DATABASE_PRIVATE_URL"),
      DJANGO_ACCOUNT_ALLOW_REGISTRATION: "True",
      DJANGO_ADMIN_URL: preserve(),
      DJANGO_ALLOWED_HOSTS: "www.speleodb.org",
      DJANGO_DEBUG: "False",
      DJANGO_FIELD_ENCRYPTION_KEY: preserve(),
      DJANGO_GIT_PROJECT_DIR: "/app/.workdir/git_projects/",
      DJANGO_HIJACK_URL: preserve(),
      DJANGO_SECRET_KEY: preserve(),
      DJANGO_SETTINGS_MODULE: "config.settings.production",
      DJANGO_SPECTALUR_SERVER: "https://www.speleodb.org",
      DJANGO_UPLOAD_INDIVIDUAL_FILESIZE_MB_LIMIT: "500",
      DJANGO_UPLOAD_TOTAL_FILESIZE_MB_LIMIT: "500",
      GITLAB_GROUP_ID: "86369638",
      GITLAB_GROUP_NAME: "speleodb_surveys",
      GITLAB_HOST_URL: "gitlab.com",
      GITLAB_TOKEN: preserve(),
      GUNICORN_THREADS: "2",
      GUNICORN_WORKERS: "2",
      MAILERSEND_API_TOKEN: preserve(),
      MAPBOX_API_TOKEN: preserve(),
      PYTHONHASHSEED: "random",
      RAILWAY_DEPLOYMENT_OVERLAP_SECONDS: "60",
      REDIS_URL: ref(redis, "REDIS_URL"),
      SENTRY_DSN: preserve(),
      SENTRY_ENVIRONMENT: "production",
      USE_DOCKER: "False",
      USE_S3: "True",
      WEB_CONCURRENCY: "2",
    },
    domains: [{ domain: publicHostname, port: 8080 }],
    networking: { privateNetworkEndpoint: "speleodb" },
    deploy: {
      drainingSeconds: 0,
      ipv6EgressEnabled: false,
      limitOverride: { containers: { cpu: 8, memoryBytes: 3000000000 } },
      overlapSeconds: 0,
      runtime: "V2",
      useLegacyStacker: false,
    },
  });

  // Preserve ownership of the web service's existing variables. References here
  // do not copy plaintext secrets into the source.
  const applicationVariables = [
    "DATABASE_URL",
    "DJANGO_SECRET_KEY",
    "DJANGO_ALLOWED_HOSTS",
    "DJANGO_ADMIN_URL",
    "REDIS_URL",
    "GITLAB_GROUP_ID",
    "GITLAB_GROUP_NAME",
    "GITLAB_HOST_URL",
    "GITLAB_TOKEN",
    "MAPBOX_API_TOKEN",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_STORAGE_BUCKET_NAME",
    "AWS_S3_REGION_NAME",
    "AWS_S3_CUSTOM_DOMAIN",
    "AWS_CLOUDFRONT_KEY_B64",
    "AWS_CLOUDFRONT_KEY_ID",
    "MAILERSEND_API_TOKEN",
    "DJANGO_GIT_PROJECT_DIR",
    "SENTRY_DSN",
    "SENTRY_ENVIRONMENT",
  ];
  const applicationEnvironment = {
    ...Object.fromEntries(applicationVariables.map((key) => [key, ref(SpeleoDB_Prod, key)])),
    DJANGO_SETTINGS_MODULE: "config.settings.production",
    DJANGO_READ_DOT_ENV_FILE: "False",
    USE_DOCKER: "False",
    CELERY_BROKER_URL: brokerUrl,
    EXPORTS_PUBLIC_BASE_URL: publicOrigin,
    RAILWAY_DEPLOYMENT_DRAINING_SECONDS: "120",
  };
  const applicationSource = github("OpenSpeleo/SpeleoDB", {
    branch: "master",
    checkSuites: true,
  });
  const workerDeployment = {
    drainingSeconds: 120,
    ipv6EgressEnabled: false,
    runtime: "V2",
    useLegacyStacker: false,
    // Keep the existing production caps for both background services.
    limitOverride: { containers: { cpu: 1, memoryBytes: 1000000000 } },
  };

  // Scale this shared worker through replicas; every replica consumes both
  // exports and background_control using the same start script.
  const worker = service("Celery-Worker", {
    source: applicationSource,
    build: { builder: "RAILPACK", buildEnvironment: "V3" },
    start: "bash compose/celery/worker/start",
    replicas: { "us-east4-eqdc4a": 1 },
    env: applicationEnvironment,
    networking: { privateNetworkEndpoint: "celery-worker" },
    deploy: workerDeployment,
  });
  const beat = service("Celery-Beat", {
    source: applicationSource,
    build: { builder: "RAILPACK", buildEnvironment: "V3" },
    start: "bash compose/celery/beat/start",
    replicas: { "us-east4-eqdc4a": 1 },
    env: {
      ...applicationEnvironment,
      RAILWAY_DEPLOYMENT_OVERLAP_SECONDS: "0",
    },
    networking: { privateNetworkEndpoint: "celery-beat" },
    // Railway starts the replacement before retiring the old container even at
    // zero overlap. The PostgreSQL advisory lock coordinates scheduler ownership.
    deploy: { ...workerDeployment, overlapSeconds: 0 },
  });

  const backupDisk = volume("speleodb-git backup cronjob-volume", {
    ...volumeSettings,
    sizeMB: 50000,
  });
  const gogsDisk = volume("beneficial-volume", {
    ...volumeSettings,
    sizeMB: 5000,
  });
  const gogs = service("Gogs", {
    source: image("gogs/gogs", {
      autoUpdates: {
        type: "minor",
        schedule: Array.from({ length: 7 }, (_, day) => ({
          day,
          startHour: 2,
          endHour: 8,
        })),
      },
    }),
    build: { builder: "RAILPACK" },
    start: `/bin/sh -c ${shellQuote(gogsStart)}`,
    replicas: { "us-east4-eqdc4a": 1 },
    env: {
      GOGS_ACCESS_TOKEN: preserve(),
      PORT: "3000",
      // This is a soft Go-runtime target, not a process/container or FS-cache cap.
      GOMEMLIMIT: "32MiB",
      GOGC: "25",
      GOMAXPROCS: "1",
      ...gitEnvironment,
    },
    domains: [{ domain: "gogs.speleodb.org", port: 3000 }],
    networking: { privateNetworkEndpoint: "gogs" },
    volumeMounts: { "/data": gogsDisk },
    deploy: {
      limitOverride: { containers: { cpu: 1, memoryBytes: 500000000 } },
      runtime: "V2",
      useLegacyStacker: false,
      ipv6EgressEnabled: false,
      drainingSeconds: 0,
      overlapSeconds: 0,
    },
  });

  const backup = service("SpeleoDB Git Backup CronJob", {
    configFile: "",
    source: github("OpenSpeleo/SpeleoDB_Git_Backup_CronJob", {
      branch: "master",
      checkSuites: true,
    }),
    build: {
      builder: "DOCKERFILE",
      buildEnvironment: "V3",
      dockerfilePath: "Dockerfile",
    },
    replicas: { "us-east4-eqdc4a": 1 },
    networking: { privateNetworkEndpoint: "git-backup-sdb" },
    volumeMounts: { "/data": backupDisk },
    deploy: {
      runtime: "V2",
      cronSchedule: "0/60 * * * *",
      useLegacyStacker: false,
      ipv6EgressEnabled: false,
      restartPolicyType: "NEVER",
      // Preserve the existing production resource limits.
      limitOverride: {
        containers: {
          cpu: 1,
          memoryBytes: 2_000_000_000,
        },
      },
    },
    // IaC treats omitted variables as deletions; retain their Railway values.
    env: {
      BACKUP_PARALLEL_THREADS: "1",
      ...gitEnvironment,
      FORCE_REBUILD_COUNTER: "1",
      GITLAB_GROUP_ID: ref(SpeleoDB_Prod, "GITLAB_GROUP_ID"),
      GITLAB_GROUP_NAME: ref(SpeleoDB_Prod, "GITLAB_GROUP_NAME"),
      GITLAB_HOST_URL: ref(SpeleoDB_Prod, "GITLAB_HOST_URL"),
      GITLAB_TOKEN: preserve(),
      GIT_PROJECT_DIR: "/data",
      GOGS_ACCESS_TOKEN: preserve(),
      GOGS_INSTANCE_URL: "http://${{Gogs.RAILWAY_PRIVATE_DOMAIN}}:${{Gogs.PORT}}",
      GOGS_ORG: "sdb_prod_backup",
      GOGS_USERNAME: "speleodb_admin",
    },
  });

  const postgresBackup = service("Database Backup CRON", {
    // Preserve the template's current commit pin and upstream relationship.
    source: github("railwayapp-templates/postgres-s3-backups", {
      branch: "main",
      commitSha: "5665c7d0aa0a4fd3ca8823050d4d2b0d0dc9e5fd",
      upstreamUrl: "https://github.com/railwayapp-templates/postgres-s3-backups",
    }),
    build: { builder: "RAILPACK" },
    replicas: { "us-east4-eqdc4a": 1 },
    env: {
      AWS_ACCESS_KEY_ID: preserve(),
      AWS_S3_BUCKET: "speleodb-db-backup",
      AWS_S3_ENDPOINT: "https://s3.amazonaws.com",
      AWS_S3_REGION: "us-east-1",
      AWS_SECRET_ACCESS_KEY: preserve(),
      BACKUP_DATABASE_URL: ref(postgres, "DATABASE_PRIVATE_URL"),
      ENABLE_ALPINE_PRIVATE_NETWORKING: "true",
      SINGLE_SHOT_MODE: "1",
    },
    networking: { privateNetworkEndpoint: "backup-cron-lde" },
    deploy: {
      cronSchedule: "0 */1 * * *",
      ipv6EgressEnabled: false,
      limitOverride: { containers: { cpu: 1, memoryBytes: 2000000000 } },
      restartPolicyType: "NEVER",
      runtime: "V2",
      useLegacyStacker: false,
    },
  });

  return project("speleoDB", {
    resources: [
      SpeleoDB_Prod,
      worker,
      beat,
      postgres,
      postgresDisk,
      postgresArchive,
      redis,
      redisDisk,
      postgresBackup,
      backup,
      gogs,
      backupDisk,
      gogsDisk,
    ],
  });
});
