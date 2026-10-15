"""Run minimal Django and Beat in one process and one operating-system thread."""

from __future__ import annotations

import os
import signal
from functools import partial
from typing import TYPE_CHECKING
from typing import Any

import django
from celery.apps.beat import Beat
from celery.utils.imports import symbol_by_name
from django.conf import settings
from django.db import connection

from speleodb.background_jobs.lease import SchedulerLease

if TYPE_CHECKING:
    from types import FrameType

    from celery import Celery
    from celery.beat import Service


def _stop(signum: int, frame: FrameType | None) -> None:
    raise SystemExit(0)


class SynchronousBeat(Beat):
    def install_sync_handler(self, service: Service) -> None:
        # Service.start already synchronizes in its finally block. Celery's
        # default handler calls service.sync immediately, which constructs a
        # second scheduler if a signal interrupts the first one's constructor.
        signal.signal(signal.SIGTERM, _stop)
        signal.signal(signal.SIGINT, _stop)


def main() -> None:
    os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings.beat"
    os.environ["CELERY_SKIP_CHECKS"] = "true"
    previous_term = signal.signal(signal.SIGTERM, _stop)
    previous_int = signal.signal(signal.SIGINT, _stop)
    lease: SchedulerLease | None = None
    try:
        django.setup()
        if connection.vendor != "postgresql":
            raise RuntimeError("The background scheduler requires PostgreSQL.")
        lease = SchedulerLease(connection.get_connection_params())
        lease.acquire()
        app: Celery = symbol_by_name("config.celery_app:app")
        # The scheduler class comes from trusted application settings.
        scheduler_type: Any = symbol_by_name(settings.CELERY_BEAT_SCHEDULER)
        SynchronousBeat(
            app=app,
            # Celery resolves this with symbol_by_name, which accepts callables;
            # celery-stubs only describes the CLI's string form.
            scheduler=partial(scheduler_type, lease=lease),  # type: ignore[arg-type]
            loglevel="INFO",
            pidfile="",
        ).run()
    finally:
        if lease is not None:
            lease.close()
        signal.signal(signal.SIGTERM, previous_term)
        signal.signal(signal.SIGINT, previous_int)


if __name__ == "__main__":
    main()
