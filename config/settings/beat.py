"""Scheduler-only Django settings: database schedules without application apps."""

from __future__ import annotations

from config.settings.celery import *  # noqa: F403
from config.settings.database import DATABASES
from config.settings.environment import TIME_ZONE  # noqa: F401 - Django setting export.
from config.settings.environment import USE_TZ  # noqa: F401 - Django setting export.
from config.settings.environment import env

SECRET_KEY: str = env.str("DJANGO_SECRET_KEY")
DEBUG: bool = False
INSTALLED_APPS: list[str] = ["django_celery_beat"]
DEFAULT_AUTO_FIELD: str = "django.db.models.BigAutoField"

# Preserve production connection lifetime without importing production's Sentry
# initialization or its web, storage, and email settings.
DATABASES["default"]["CONN_MAX_AGE"] = env.int(
    "CONN_MAX_AGE", default=0 if env.bool("USE_DOCKER", default=False) else 60
)

# Beat only publishes task names; workers own result recording and retention.
# Disabling expiry also prevents Celery installing its implicit cleanup schedule.
CELERY_RESULT_BACKEND = None
CELERY_RESULT_EXPIRES = None
