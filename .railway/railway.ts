import {
  defineRailway,
  github,
  preserve,
  project,
  ref,
  service,
} from "railway/iac";

// Sole Railway service configuration for this repository. Keep this existing
// ownership name: databases and other services remain managed outside this file.
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
    preDeploy: "python /app/manage.py migrate && python /app/manage.py install_background_schedules && python /app/manage.py collectstatic --noinput --verbosity=3 --ignore=flags",
    env: {
      ...Object.fromEntries(preservedWebVariables.map((key) => [key, preserve()])),
      CELERY_BROKER_URL: brokerUrl,
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
    start: "bash compose/celery/beat/start",
    replicas: { "us-east4-eqdc4a": 1 },
    env: {
      ...applicationEnvironment,
      RAILWAY_DEPLOYMENT_OVERLAP_SECONDS: "0",
    },
    // Railway starts the replacement before retiring the old container even at
    // zero overlap. The PostgreSQL advisory lock coordinates scheduler ownership.
    deploy: { ...workerDeployment, overlapSeconds: 0 },
  });

  return project("speleoDB", {
    resources: [SpeleoDB_Prod, worker, beat],
  });
});
