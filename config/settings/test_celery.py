"""Child-worker settings for the default isolated Redis integration tests."""

from __future__ import annotations

import os

from config.settings.test import *  # noqa: F403
from config.settings.test import TEST_CELERY_BROKER_URL

CELERY_BROKER_URL = TEST_CELERY_BROKER_URL
# Celery prefers this environment variable over its namespaced Django setting.
os.environ["CELERY_BROKER_URL"] = CELERY_BROKER_URL
