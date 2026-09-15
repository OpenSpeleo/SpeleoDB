import {
  defineRailway,
  github,
  image,
  preserve,
  project,
  ref,
  service,
} from "railway/iac";

// Last resort for a per-service CaC repo. Prefer one .railway file for the
// project and drop this if you later combine services into that file.
export const partial = "SpeleoDB-Prod";

export default defineRailway(() => {
  const publicHostname = "www.speleodb.org";
  const publicOrigin = `https://${publicHostname}`;

  // Redis owns CELERY_BROKER_URL=${{REDIS_URL}}/1. Reference that service
  // directly so credential/address changes propagate and Railway shows the
  // dependency. This partial does not manage the existing Redis server.
  const brokerUrl = "${{Redis-Prod.CELERY_BROKER_URL}}";

  // Declaring an env map gives IaC ownership of that map. Explicitly preserve
  // all existing application variables so adding broker references cannot delete
  // credentials or unrelated settings. This list comes from production inventory.
  const preservedWebVariables = [
    "ALLOW_USER_DEBUG",
    "AWS_ACCESS_KEY_ID",
    "AWS_CLOUDFRONT_KEY_B64",
    "AWS_CLOUDFRONT_KEY_ID",
    "AWS_S3_CUSTOM_DOMAIN",
    "AWS_S3_REGION_NAME",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_STORAGE_BUCKET_NAME",
    "DATABASE_URL",
    "DJANGO_ACCOUNT_ALLOW_REGISTRATION",
    "DJANGO_ADMIN_URL",
    "DJANGO_ALLOWED_HOSTS",
    "DJANGO_DEBUG",
    "DJANGO_FIELD_ENCRYPTION_KEY",
    "DJANGO_GIT_PROJECT_DIR",
    "DJANGO_HIJACK_URL",
    "DJANGO_SECRET_KEY",
    "DJANGO_SETTINGS_MODULE",
    "DJANGO_SPECTALUR_SERVER",
    "DJANGO_UPLOAD_INDIVIDUAL_FILESIZE_MB_LIMIT",
    "DJANGO_UPLOAD_TOTAL_FILESIZE_MB_LIMIT",
    "GITLAB_GROUP_ID",
    "GITLAB_GROUP_NAME",
    "GITLAB_HOST_URL",
    "GITLAB_TOKEN",
    "GUNICORN_THREADS",
    "GUNICORN_WORKERS",
    "MAILERSEND_API_TOKEN",
    "MAPBOX_API_TOKEN",
    "PYTHONHASHSEED",
    "RAILWAY_DEPLOYMENT_OVERLAP_SECONDS",
    "REDIS_URL",
    "SENTRY_DSN",
    "SENTRY_ENVIRONMENT",
    "USE_DOCKER",
    "USE_S3",
    "WEB_CONCURRENCY",
  ];
  const SpeleoDB_Prod = service("SpeleoDB-Prod", {
    source: github("OpenSpeleo/SpeleoDB", { branch: "master", checkSuites: true }),
    build: { builder: "RAILPACK", buildCommand: "", buildEnvironment: "V3" },
    start: "gunicorn config.wsgi:application --workers ${GUNICORN_WORKERS} --threads ${GUNICORN_THREADS} --max-requests 128 --preload",
    replicas: { "us-east4-eqdc4a": 1 },
    preDeploy: "python /app/manage.py migrate && python /app/manage.py install_background_schedules && python /app/manage.py collectstatic --noinput --verbosity=3 --ignore='django_countries/static/flags/*'",
    env: {
      ...Object.fromEntries(preservedWebVariables.map((key) => [key, preserve()])),
      CELERY_BROKER_URL: brokerUrl,
      KANCHI_URL: "https://${{Kanchi.RAILWAY_PUBLIC_DOMAIN}}/ui/",
    },
    domains: [{ domain: publicHostname, port: 8080 }],
    networking: { privateNetworkEndpoint: "speleodb" },
    deploy: {
      drainingSeconds: 0,
      ipv6EgressEnabled: false,
      limitOverride: { containers: { cpu: 8, memoryBytes: 3000000000 } },
      overlapSeconds: 0,
      runtime: "V2",
      sleepApplication: false,
      restartPolicyType: "ON_FAILURE",
      restartPolicyMaxRetries: 10,
      useLegacyStacker: false,
    },
  });

  // Preserve ownership of the web service's existing variables. References here
  // do not copy plaintext secrets into the source or Kanchi's environment.
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
    sleepApplication: false,
    restartPolicyType: "ON_FAILURE" as const,
    restartPolicyMaxRetries: 10,
    drainingSeconds: 120,
  };

  // Scale this shared worker through replicas; every replica consumes both
  // exports and background_control using the same start script.
  const worker = service("Celery-Worker", {
    source: applicationSource,
    build: { builder: "RAILPACK", watchPatterns: [] },
    start: "bash compose/celery/worker/start",
    replicas: { "us-east4-eqdc4a": 1 },
    env: applicationEnvironment,
    deploy: {
      ...workerDeployment,
      limitOverride: { containers: { cpu: 2, memoryBytes: 4 * 1024 ** 3 } },
    },
  });
  const beat = service("Celery-Beat", {
    source: applicationSource,
    build: { builder: "RAILPACK", watchPatterns: [] },
    start: "python manage.py run_background_beat",
    replicas: { "us-east4-eqdc4a": 1 },
    env: applicationEnvironment,
    deploy: workerDeployment,
  });

  const kanchi = service("Kanchi", {
    source: image("getkanchi/kanchi:2.0.1@sha256:96e799547cce75b9f23e11cde00823a5e2752bc9f4f4135933b392551d703e28"),
    replicas: { "us-east4-eqdc4a": 1 },
    domains: [{ domain: "kanchi.speleodb.org", port: 8765 }],
    healthcheck: "/api/health",
    env: {
      CELERY_BROKER_URL: brokerUrl,
      // Provision a separate database and restricted user on the existing
      // PostgreSQL server. Supply a synchronous SQLAlchemy connection URL
      // (postgresql+psycopg://), never Django's database credentials.
      DATABASE_PASSWORD: preserve(),
      DATABASE_URL: "postgresql+psycopg://kanchi:${{DATABASE_PASSWORD}}@${{Postgres-Prod.PGPRIVATEHOST}}:5432/kanchi",
      PORT: "8765",
      WS_PORT: "8765",
      WS_HOST: "0.0.0.0",
      AUTH_ENABLED: "true",
      AUTH_BASIC_ENABLED: "true",
      AUTH_GOOGLE_ENABLED: "false",
      AUTH_GITHUB_ENABLED: "false",
      BASIC_AUTH_USERNAME: preserve(),
      BASIC_AUTH_PASSWORD_HASH: preserve(),
      SESSION_SECRET_KEY: preserve(),
      TOKEN_SECRET_KEY: preserve(),
      ALLOWED_EMAIL_PATTERNS: "${{BASIC_AUTH_USERNAME}}",
      ALLOWED_HOSTS: "${{RAILWAY_PUBLIC_DOMAIN}},healthcheck.railway.app",
      ALLOWED_ORIGINS: "https://${{RAILWAY_PUBLIC_DOMAIN}}",
      ENABLE_PICKLE_SERIALIZATION: "false",
    },
    deploy: { sleepApplication: false, restartPolicyType: "ON_FAILURE" },
  });

  return project("speleoDB", {
    resources: [SpeleoDB_Prod, worker, beat, kanchi],
  });
});
