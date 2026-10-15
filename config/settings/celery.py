"""Shared Celery transport, routing, and execution policy; no task imports."""

from __future__ import annotations

from config.settings.environment import TIME_ZONE
from config.settings.environment import USE_TZ
from config.settings.environment import env

# Celery
# ------------------------------------------------------------------------------
if USE_TZ:
    # https://docs.celeryq.dev/en/stable/userguide/configuration.html#std:setting-timezone
    CELERY_TIMEZONE = TIME_ZONE
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#std:setting-broker_url
CELERY_BROKER_URL = env.str("CELERY_BROKER_URL", default="redis://localhost:6379/1")
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#std:setting-result_backend
CELERY_RESULT_BACKEND: str | None = "django-db"
CELERY_TASK_TRACK_STARTED = True
CELERY_RESULT_EXPIRES: int | None = 30 * 24 * 60 * 60
CELERY_BROKER_CONNECTION_TIMEOUT = 3
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
# Maximum broker retries after the initial connection attempt (six attempts).
CELERY_BROKER_CONNECTION_MAX_RETRIES = 5
# Worker connection retries double their delay, capped at the maximum below.
CELERY_BROKER_RETRY_BASE_DELAY_SECONDS = 1.0
CELERY_BROKER_RETRY_MAX_DELAY_SECONDS = 30.0
# Use Celery's supported consumer extension to replace Kombu's linear sleeps.
CELERY_WORKER_CONSUMER = "speleodb.background_jobs.consumer:ExponentialBackoffConsumer"
CELERY_BROKER_TRANSPORT_OPTIONS: dict[str, int | str] = {
    "visibility_timeout": 3600,
    "socket_connect_timeout": 3,
    "socket_timeout": 5,
}
CELERY_VISIBILITY_TIMEOUT = 3600
CELERY_TASK_DEFAULT_QUEUE = "background_control"
CELERY_TASK_ROUTES = {
    "speleodb.gis.tasks.*": {"queue": "background_control"},
    "speleodb.background_jobs.tasks.generate_export": {"queue": "exports"},
    "speleodb.background_jobs.tasks.*": {"queue": "background_control"},
    "celery.backend_cleanup": {"queue": "background_control"},
}

# https://docs.celeryq.dev/en/stable/userguide/configuration.html#result-extended
CELERY_RESULT_EXTENDED = True
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#result-backend-always-retry
# https://github.com/celery/celery/pull/6122
CELERY_RESULT_BACKEND_ALWAYS_RETRY = True
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#result-backend-max-retries
CELERY_RESULT_BACKEND_MAX_RETRIES = 10
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#std:setting-accept_content
CELERY_ACCEPT_CONTENT = ["json"]
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#std:setting-task_serializer
CELERY_TASK_SERIALIZER = "json"
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#std:setting-result_serializer
CELERY_RESULT_SERIALIZER = "json"
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#task-time-limit
# TODO: set to whatever value is adequate in your circumstances
CELERY_TASK_TIME_LIMIT = 5 * 60
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#task-soft-time-limit
# TODO: set to whatever value is adequate in your circumstances
CELERY_TASK_SOFT_TIME_LIMIT: int | None = 60

# https://docs.celeryq.dev/en/stable/userguide/configuration.html#beat-scheduler
CELERY_BEAT_SCHEDULER = (
    "speleodb.background_jobs.scheduler:ExponentialBackoffDatabaseScheduler"
)
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#worker-send-task-events
CELERY_WORKER_SEND_TASK_EVENTS = True
# https://docs.celeryq.dev/en/stable/userguide/configuration.html#std-setting-task_send_sent_event
CELERY_TASK_SEND_SENT_EVENT = True
