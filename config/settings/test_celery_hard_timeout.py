"""Live-worker test settings that isolate Celery's hard-timeout behavior."""

from __future__ import annotations

from config.settings.test import *  # noqa: F403

# Celery captures task timeout defaults when it creates request classes.
# Configure this test's task before startup so no soft signal can mask
# the hard timeout; runtime remote-control changes arrive too late.
# Django's namespaced setting also controls the pool's default timeout.
CELERY_TASK_SOFT_TIME_LIMIT = None
