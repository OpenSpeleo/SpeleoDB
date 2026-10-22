"""Real worker startup tests isolate Redis keys and configure check failures."""

from __future__ import annotations

import os

from config.settings.test_celery import *  # noqa: F403
from config.settings.test_celery import CELERY_BROKER_TRANSPORT_OPTIONS

CELERY_BROKER_TRANSPORT_OPTIONS = {
    **CELERY_BROKER_TRANSPORT_OPTIONS,
    "global_keyprefix": os.environ["SPELEODB_TEST_BROKER_PREFIX"],
}

# Exercise Django's actual urls.E006 check before the worker exec boundary.
if os.environ.get("SPELEODB_TEST_INVALID_STATIC_URL") == "1":
    STATIC_URL = "/static"
